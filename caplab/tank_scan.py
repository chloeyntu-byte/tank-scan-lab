"""Tank scan: startup frequency, tank Rp, core loading and gain from one native run.

Definitions (differential P-N admittance, Y_d = I_d / (V_P - V_N)):

* Every enabled canvas instance is measured through 0 V series probes on all of
  its terminals (see loss_native).  Two independent native AC excitations are
  combined into a floating 1 A drive across P/N.  By Tellegen's theorem the
  complex power of every module adds up to the input power, so each module has
  an exact in-circuit differential admittance  Y_k = 2 conj(S_k) / |V_d|^2  and
  sum(Y_k) is the total Y_d seen by the measurement port.
* A gm-core module's own 2x2 effective admittance on the P/N nets is identified
  from the two raw excitations.  Its cross terms carry the transconductance:
  gm = Re(Y12 + Y21) / 2 and its self terms the loading: g_load = Re(Y11 + Y22) / 2
  (per side, at the device terminals; for an ideal cross-coupled pair gm is the
  terminal gm and g_load is gds plus gate-input loss).
* G_neg follows the usual gm-cancellation tank scan: the low-frequency terminal gm
  (real cross terms at the lowest simulated frequency, e.g. the 10 MHz reference
  point) is cancelled under the actual floating state at f0 (= gm/2 for a
  symmetric pair).  Everything else the core absorbs, including the RF roll-off
  of gm, is core loading.  The alternative split with the cross terms at f0
  itself is reported as *_f0 values.  Both give the same net Re(Y) at f0.
* Startup values at f0 (Im Y_d = 0 of the complete circuit):
  G_LC = inductor + cap-array conductance, G_loss = G_LC + other loads + core
  loading, Rp(LC) = 1/G_LC, Rp(LC+loading) = 1/G_loss, margin = G_neg / G_loss
  (> 1 starts), gm*Rp = gm(f_ref) * Rp(LC+loading) with f_ref the lowest
  simulated frequency (the DC-like terminal gm used by tank-scan).

All values at f0 are linear interpolations between the two native samples that
bracket the resonance; narrow the sweep around f0 for tank-scan-like accuracy.
"""
import cmath
import hashlib
import json
import math

from .loss_native import reconstruct_sample
from .resonance import find_first_resonance, find_resonances

ROLES = ('inductor', 'array', 'gm', 'load', 'ignore')
ROLE_LABELS = {'inductor': 'Inductor / N-port', 'array': 'Cap array', 'gm': 'gm core',
               'load': 'Other load', 'ignore': 'Excluded from tank'}
CONTENT_KEYS = ('inductor', 'array', 'gm')
P_NET, N_NET = 'CAL_P', 'CAL_N'
PORT_NETS = ('CAL_P', 'CAL_N', 'CAL_P2', 'CAL_N2')


# ---------------------------------------------------------------- roles / mode

def auto_role(inst, project=None):
    """Best guess of an instance's tank role; the user can override it."""
    kind, cell = inst.get('kind'), str(inst.get('cell') or '').lower()
    if kind == 'snp':
        return 'inductor'
    if kind == 'passive':
        return 'inductor' if cell in ('indq', 'mind', 'ind') else 'load'
    roles = {str(v) for v in (inst.get('roles') or {}).values()}
    if project is not None:
        outputs = {str(v) for r in project.get('registers', [])
                   for k, v in (r.get('roles') or {}).items() if k.startswith('B<') and v}
        if any(v in outputs for v in roles if v):
            return 'array'
    if any(k in cell for k in ('ind', 'transformer', 'balun')):
        return 'inductor'
    if any(k in cell for k in ('cap', 'array', 'bank', 'ct_', 'mom', 'mim', 'var')):
        return 'array'
    return 'gm'


def tank_settings(page, project):
    """Normalized analysis-only settings stored on the page (never in the digest)."""
    stored = page.setdefault('tank', {}) if page is not None else {}
    nodes = [n for n in project.get('instances', []) if n.get('enabled', True)]
    roles = dict(stored.get('roles') or {})
    for node in nodes:
        if roles.get(node['id']) not in ROLES:
            roles[node['id']] = auto_role(node, project)
    roles = {k: v for k, v in roles.items() if any(n['id'] == k for n in nodes)}
    contains = dict(stored.get('contains') or {})
    for key in CONTENT_KEYS:
        if key not in contains:
            contains[key] = any(v == key for v in roles.values())
    stored.update(roles=roles, contains=contains)
    return {'roles': dict(roles), 'contains': dict(contains), 'loss_split': stored.get('loss_split', True) is not False}


def has_port2(project):
    """True when canvas pins carry the optional port-2 roles P2/N2."""
    return any(v in ('P2', 'N2') for n in project.get('instances', []) if n.get('enabled', True)
               for v in (n.get('roles') or {}).values())


def needs_module_currents(settings):
    """Native module currents are captured for the loss split, and always with a gm core."""
    return bool(settings.get('loss_split', True)) or backend_mode(settings) == 'active'


def effective_roles(settings):
    """Apply the user's 'canvas contains' choice to the per-instance roles."""
    contains, out = settings['contains'], {}
    for ident, role in settings['roles'].items():
        if role in CONTENT_KEYS and not contains.get(role):
            role = 'load'
        out[ident] = role
    return out


def backend_mode(settings):
    return 'active' if settings['contains'].get('gm') else 'passive'


def check_roles(settings):
    """Return a list of problems that block the analysis (empty when usable)."""
    roles, contains, issues = effective_roles(settings), settings['contains'], []
    for key in CONTENT_KEYS:
        if contains.get(key) and not any(v == key for v in roles.values()):
            issues.append('"{}" is checked but no canvas instance has that role.'.format(ROLE_LABELS[key]))
    if not any(contains.get(k) for k in CONTENT_KEYS):
        issues.append('Select at least one item that the canvas contains.')
    return issues


# ------------------------------------------------------------- native algebra

def _solve2(a, b):
    """Solve X @ a = b for 2x2 complex matrices given as nested lists (X = b a^-1)."""
    det = a[0][0]*a[1][1] - a[0][1]*a[1][0]
    scale = max(abs(a[0][0]*a[1][1]), abs(a[0][1]*a[1][0]), 1e-300)
    if abs(det) <= 1e-13 * scale:
        return None
    inv = [[a[1][1]/det, -a[0][1]/det], [-a[1][0]/det, a[0][0]/det]]
    return [[b[i][0]*inv[0][j] + b[i][1]*inv[1][j] for j in range(2)] for i in range(2)]


def module_groups(plan, roles):
    """Instance -> module label; mutually coupled windings form one group."""
    instances = {n['id']: n for n in plan.get('instances', [])}
    parent = {}

    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for node in instances.values():
        if node.get('kind') == 'passive' and node.get('cell') == 'mind':
            props = node.get('props') or {}
            for other in (props.get('ind1'), props.get('ind2')):
                if other:
                    parent[root(other)] = root(node['id'])
    members = {}
    for name in list(parent):
        members.setdefault(root(name), []).append(name)
    label = {ident: ident for ident in instances}
    group_role = {}
    for names in members.values():
        if len(names) < 2:
            continue
        name = 'Coupled: ' + ', '.join(sorted(names))
        kinds = {roles.get(n) for n in names if instances.get(n, {}).get('cell') != 'mind'} - {None}
        if len(kinds) > 1:
            raise ValueError('Mutually coupled elements {} have different tank roles; give them one role.'.format(', '.join(sorted(names))))
        for n in names:
            label[n] = name
        group_role[name] = next(iter(kinds), 'inductor')
    role_of = {}
    for ident, name in label.items():
        role_of[name] = group_role.get(name, roles.get(ident, 'load'))
    return label, role_of


def sample_admittances(sample, plan, roles):
    """Module admittances and the gm-core split for one native frequency sample."""
    f = sample['frequency_Hz']
    rec = reconstruct_sample(dict(sample), plan, f)
    if not rec['available']:
        return {'available': False, 'reason': rec.get('reason', 'Floating reconstruction failed.'), 'frequency_Hz': f}
    vd = rec['vp'] - rec['vn']
    if abs(vd) == 0:
        return {'available': False, 'reason': 'Zero differential voltage.', 'frequency_Hz': f}
    label, role_of = module_groups(plan, roles)
    probes = plan['probes']
    power = {}
    for index, probe in enumerate(probes):
        p = rec['sample']['pins'][str(index)]
        name = label.get(probe['instance'], probe['instance'])
        power[name] = power.get(name, 0j) + 0.5 * complex(p[0], p[1]) * complex(p[2], p[3]).conjugate()
    norm = abs(vd) ** 2
    modules = {name: 2 * s.conjugate() / norm for name, s in power.items()}
    out = {'available': True, 'frequency_Hz': f, 'modules': modules, 'module_role': role_of, 'vp': rec['vp'], 'vn': rec['vn'],
           'total': sum(modules.values()), 'input_total': 1 / vd, 'gm': {}}
    # gm cores: effective admittance on the measurement nets (P, N and, with port 2, P2, N2),
    # identified from the raw native excitations (two, or four with port 2).
    from .loss_native import port_states
    from .linalg import solve
    gm_names = sorted({label[pr['instance']] for pr in probes if role_of.get(label.get(pr['instance'])) == 'gm'})
    states = port_states(sample)
    n = len(states[0][0]) if states else 0
    if gm_names and (len(states) < 2 or len(states) != n):
        return {'available': False, 'frequency_Hz': f,
                'reason': 'gm-core analysis needs every native excitation (run with two-port separation).'}
    v_now = [rec['vp'], rec['vn']] + list(rec.get('v2') or ())
    out['v'] = v_now
    for name in gm_names:
        vmat_t = [list(v) for v, pins, src in states]                      # states x nets
        imat_t = []
        for v, pins, src in states:
            cur = [0j] * n
            for index, probe in enumerate(probes):
                if label.get(probe['instance']) == name and probe['net'] in PORT_NETS[:n]:
                    cur[PORT_NETS.index(probe['net'])] += complex(*pins[str(index)][2:4])
            imat_t.append(cur)
        yt = solve(vmat_t, imat_t)                                        # V^T Y^T = I^T
        if yt is None:
            return {'available': False, 'frequency_Hz': f,
                    'reason': 'The native excitations do not identify the gm core admittance (singular node states).'}
        y = [[yt[j][i] for j in range(n)] for i in range(n)]
        touched = {PORT_NETS.index(pr['net']) for pr in probes
                   if label.get(pr['instance']) == name and pr['net'] in PORT_NETS[:n]}
        ctrl = (2, 3) if n == 4 and touched & {2, 3} else (0, 1)
        g_neg = cross_conductance_matrix(off_diagonal(y), v_now)
        out['gm'][name] = {'Y': y, 'ctrl': ctrl, 'gm_S': transconductance(y, ctrl).real,
                           'gload_S': (y[0][0] + y[1][1]).real / 2,
                           'G_neg_S': g_neg, 'G_load_S': modules[name].real + g_neg,
                           'touches_PN': bool(touched & {0, 1})}
    return out


def off_diagonal(y, real=False):
    return [[0j if i == j else (complex(y[i][j].real) if real else y[i][j]) for j in range(len(y))] for i in range(len(y))]


def transconductance(y, ctrl):
    """Per-side differential transconductance from the control nets to the drain nets (P, N).

    gm = -(u_D^T Y u_C) / 2 with u = (+1, -1); self terms are excluded when the
    control nets are the drains themselves (gates on the opposite drains).
    """
    yx = off_diagonal(y) if ctrl == (0, 1) else y
    (a, b), (c, d) = ctrl, (0, 1)
    return -(yx[0][a] - yx[0][b] - yx[1][a] + yx[1][b]) / 2


def cross_conductance_matrix(yx, v):
    """Negative conductance delivered by the cross terms yx under node voltages v (port-1 normalized)."""
    n = len(yx)
    p_cross = 0.5 * sum((v[i].conjugate() * yx[i][j] * v[j]).real for i in range(n) for j in range(n))
    return -2 * p_cross / abs(v[0] - v[1]) ** 2


def cross_conductance(y12, y21, vp, vn):
    """Negative conductance delivered by transconductance cross terms under (vp, vn)."""
    p_cross = 0.5 * (vp.conjugate() * y12 * vn + vn.conjugate() * y21 * vp).real
    return -2 * p_cross / abs(vp - vn) ** 2


def apply_reference_gm(per):
    """Tank-scan definition: cancel the low-frequency terminal gm (real cross terms of the
    lowest sample) at every frequency.  RF roll-off of gm then counts as core loading."""
    ref = per[0]['gm']
    for sa in per:
        for name, item in sa['gm'].items():
            neg = cross_conductance_matrix(off_diagonal(ref[name]['Y'], real=True), sa['v'])
            item['G_neg_ref_S'] = neg
            item['G_load_ref_S'] = sa['modules'][name].real + neg


# --------------------------------------------------------------- aggregation

def _sums(sa, ref=False):
    roles = sa['module_role']
    g = {'inductor': 0.0, 'array': 0.0, 'load': 0.0, 'ignore': 0.0, 'gm_load': 0.0, 'gm_neg': 0.0, 'gm_total': 0.0,
         'gm_load_f0': 0.0, 'gm_neg_f0': 0.0}
    b = {'LC': 0.0, 'all': 0.0}
    for name, y in sa['modules'].items():
        role = roles.get(name, 'load')
        b['all'] += y.imag
        if role in ('inductor', 'array'):
            g[role] += y.real
            b['LC'] += y.imag
        elif role == 'gm':
            item = sa['gm'][name]
            g['gm_total'] += y.real
            g['gm_load_f0'] += item['G_load_S']
            g['gm_neg_f0'] += item['G_neg_S']
            g['gm_load'] += item['G_load_ref_S'] if ref else item['G_load_S']
            g['gm_neg'] += item['G_neg_ref_S'] if ref else item['G_neg_S']
        else:
            g[role if role in g else 'load'] += y.real
    gm = sum(v['gm_S'] for v in sa['gm'].values())
    gload = sum(v['gload_S'] for v in sa['gm'].values())
    return g, b, gm, gload


def _interp(a, b, t):
    return a + t * (b - a)


def _crossing(xs, ys):
    """First zero crossing of a sampled function; linear between samples."""
    for i in range(len(xs) - 1):
        a, b = ys[i], ys[i + 1]
        if a == 0:
            return xs[i], i, i + 1
        if a * b < 0:
            t = a / (a - b)
            return xs[i] + t * (xs[i + 1] - xs[i]), i, i + 1
    if len(xs) >= 2 and ys[-1] == 0:
        return xs[-1], len(xs) - 2, len(xs) - 1
    return None


def sweep_samples(samples, sweep_start):
    """Samples of the requested sweep; the gm reference point below it is excluded."""
    if sweep_start is None:
        return list(samples)
    return [s for s in samples if s['frequency_Hz'] >= sweep_start * (1 - 1e-9)]


def analyze_point(spectrum_samples, loss_samples, plan, roles, mode, sweep_start=None):
    """Tank-scan results for one register point.

    sweep_start excludes the low gm reference sample from the resonance search,
    the f0 bracket and the LC-only crossing; it is still used for gm/gds(f_ref).
    With a gm core and several resonances (e.g. the two modes of a transformer
    tank) f0 is the crossing with the largest startup margin; all are listed.
    """
    search = sweep_samples(spectrum_samples or [], sweep_start)
    if mode != 'active' or not loss_samples or not plan or len(search) < 2:
        return _analyze_at(None, spectrum_samples, loss_samples, plan, roles, mode, sweep_start)
    found = [r for r in find_resonances(search) if r.get('available')]
    parallel = [r for r in found if r.get('kind') == 'parallel-like']
    found = parallel or found
    if len(found) <= 1:
        return _analyze_at(found[0] if found else None, spectrum_samples, loss_samples, plan, roles, mode, sweep_start)
    results = [_analyze_at(r, spectrum_samples, loss_samples, plan, roles, mode, sweep_start) for r in found]
    scored = [r for r in results if r.get('available') and r.get('margin') is not None]
    best = max(scored, key=lambda r: r['margin']) if scored else results[0]
    best['modes'] = [{'f0_Hz': r.get('f0_Hz'), 'margin': r.get('margin')} for r in results]
    if len(results) > 1:
        note = '{} resonances; f0 = the one with the largest margin ({}).'.format(
            len(results), ', '.join('{:.4g} GHz{}'.format(m['f0_Hz'] / 1e9, '' if m['margin'] is None else ' m={:.3g}'.format(m['margin']))
                                   for m in best['modes'] if m['f0_Hz']))
        best['warning'] = (best.get('warning', '') + ' ' + note).strip()
    return best


def _analyze_at(found, spectrum_samples, loss_samples, plan, roles, mode, sweep_start=None):
    res = {'available': False, 'mode': mode}
    search = sweep_samples(spectrum_samples or [], sweep_start)
    if found is None:
        found = find_first_resonance(search) if len(search) >= 2 else {'available': False, 'reason': 'No saved SP spectrum.'}
    if not found.get('available'):
        res['reason'] = found.get('reason', 'No resonance in the simulated range.')
        return res
    f0 = found['frequency_Hz']
    res.update(f0_Hz=f0, bracket_Hz=found['bracket_Hz'], Z_real_ohm=found['Z_real_ohm'],
               G_net_S=(1 / found['Z_real_ohm']) if found['Z_real_ohm'] else None)
    if not loss_samples or not plan:
        if mode == 'active':
            res['reason'] = 'gm analysis needs native module currents: run in Tank scan mode.'
            return res
        res.update(available=True, partial=True, Rp_loaded_ohm=found['Z_real_ohm'],
                   reason='Module split unavailable (no native module currents); Rp is Re(Z) at f0.')
        return res
    rows = sorted(loss_samples, key=lambda r: r['frequency_Hz'])
    xs = [r['frequency_Hz'] for r in rows]
    per = []
    for sample in rows:
        sa = sample_admittances(sample, plan, roles)
        if not sa['available']:
            res['reason'] = '{} (at {:.6g} GHz)'.format(sa['reason'], sa['frequency_Hz'] / 1e9)
            return res
        per.append(sa)
    if mode == 'active' and not per[0]['gm']:
        res['reason'] = 'No gm-core module was measured; assign the gm role to the core instance.'
        return res
    # Consistency: module admittances must add up to the port admittance.
    worst = max(abs(sa['total'] - sa['input_total']) / max(abs(sa['input_total']), 1e-300) for sa in per)
    res['module_sum_error'] = worst
    if worst > 1e-6:
        res['reason'] = 'Module admittances do not add up to the port admittance (rel. error {:.2g}).'.format(worst)
        return res
    use_ref = mode == 'active' and xs[0] <= f0 / 5
    if use_ref:
        apply_reference_gm(per)
    res['definition'] = ('tank-scan: low-frequency terminal gm cancelled (gm roll-off at f0 counts as core loading)'
                         if use_ref else 'gm split at f0 (no low-frequency reference sample)')
    sums = [_sums(sa, use_ref) for sa in per]
    # Bracket of f0 on the native loss grid (same grid as SP).
    import bisect
    k0 = len(xs) - len(sweep_samples(rows, sweep_start))
    i = bisect.bisect_left(xs, f0)
    if i == k0 and i < len(xs) and xs[i] == f0:
        i += 1
    if i <= k0 or i >= len(xs):
        res['reason'] = 'f0 lies outside the native module-current sweep.'
        return res
    lo, hi = i - 1, i
    t = (f0 - xs[lo]) / (xs[hi] - xs[lo])
    g = {k: _interp(sums[lo][0][k], sums[hi][0][k], t) for k in sums[lo][0]}
    gm_f0 = _interp(sums[lo][2], sums[hi][2], t)
    gload_f0 = _interp(sums[lo][3], sums[hi][3], t)
    b_all = [s[1]['all'] for s in sums]
    b_lc = [s[1]['LC'] for s in sums]
    slope_all = (b_all[hi] - b_all[lo]) / (2 * math.pi * (xs[hi] - xs[lo]))  # dB/domega
    g_lc = g['inductor'] + g['array']
    g_loss = g_lc + g['load'] + g['ignore'] + g['gm_load']
    g_neg = g['gm_neg']
    res.update(available=True, partial=False,
               G_inductor_S=g['inductor'], G_array_S=g['array'], G_other_S=g['load'] + g['ignore'],
               G_LC_S=g_lc, G_core_load_S=g['gm_load'], G_neg_S=g_neg, G_loss_S=g_loss,
               Rp_LC_ohm=(1 / g_lc) if g_lc > 0 else None,
               Rp_loaded_ohm=(1 / g_loss) if g_loss > 0 else None,
               C_eff_F=slope_all / 2 if slope_all > 0 else None,
               net_check_S=(g_loss - g_neg) - (res['G_net_S'] or 0))
    if res['C_eff_F']:
        res['L_eff_H'] = 1 / ((2 * math.pi * f0) ** 2 * res['C_eff_F'])
        if g_loss > 0:
            res['Q_loaded'] = 2 * math.pi * f0 * res['C_eff_F'] / g_loss
    lc = _crossing(xs[k0:], b_lc[k0:])
    if lc:
        flc, a, b2 = lc[0], lc[1] + k0, lc[2] + k0
        u = (flc - xs[a]) / (xs[b2] - xs[a])
        glc_at = _interp(sums[a][0]['inductor'] + sums[a][0]['array'], sums[b2][0]['inductor'] + sums[b2][0]['array'], u)
        slope_lc = (b_lc[b2] - b_lc[a]) / (2 * math.pi * (xs[b2] - xs[a]))
        res['f0_LC_Hz'] = flc
        if slope_lc and slope_lc > 0 and glc_at > 0:
            res['Q_LC'] = 2 * math.pi * flc * (slope_lc / 2) / glc_at
            res['Rp_LC_at_f0LC_ohm'] = 1 / glc_at
    if mode == 'active':
        g_loss_f0 = g_lc + g['load'] + g['ignore'] + g['gm_load_f0']
        res.update(G_neg_f0_S=g['gm_neg_f0'], G_loss_f0_S=g_loss_f0,
                   Rp_loaded_f0_ohm=(1 / g_loss_f0) if g_loss_f0 > 0 else None,
                   margin_f0=(g['gm_neg_f0'] / g_loss_f0) if g_loss_f0 > 0 else None)
        res.update(gm_ref_S=sums[0][2], gds_ref_S=sums[0][3], f_ref_Hz=xs[0],
                   gm_f0_S=gm_f0, gload_f0_S=gload_f0,
                   margin=(g_neg / g_loss) if g_loss > 0 else None,
                   gmRp=(sums[0][2] / g_loss) if g_loss > 0 else None,
                   gmRp_f0=(gm_f0 / g_loss) if g_loss > 0 else None)
        if xs[0] > f0 / 5:
            res['warning'] = 'Lowest simulated frequency is above f0/5; gm(f_ref) is not a low-frequency value.'
        res['gain_curve'] = gain_curve(xs[k0:], per[k0:], sums[k0:])
        res.update(loop_gain(spectrum_samples, per, xs, lo, hi, t, sums[0][2], res))
    # Per-module contributions at f0.
    names = sorted(per[lo]['modules'])
    contrib = []
    for name in names:
        role = per[lo]['module_role'].get(name, 'load')
        gk = _interp(per[lo]['modules'][name].real, per[hi]['modules'][name].real, t)
        bk = _interp(per[lo]['modules'][name].imag, per[hi]['modules'][name].imag, t)
        item = {'module': name, 'role': role, 'G_S': gk, 'B_S': bk}
        if role == 'gm':
            key = 'G_neg_ref_S' if use_ref else 'G_neg_S'
            neg = _interp(per[lo]['gm'][name][key], per[hi]['gm'][name][key], t)
            item.update(G_S=gk + neg, G_neg_S=neg, gm_S=_interp(per[lo]['gm'][name]['gm_S'], per[hi]['gm'][name]['gm_S'], t),
                        gload_S=_interp(per[lo]['gm'][name]['gload_S'], per[hi]['gm'][name]['gload_S'], t))
        item['share_pct'] = 100 * item['G_S'] / g_loss if g_loss > 0 else None
        contrib.append(item)
    res['contributions'] = contrib
    res['shares_valid'] = g_loss > 0 and all(c['G_S'] >= -1e-6 * g_loss for c in contrib)
    width = (xs[hi] - xs[lo]) / f0
    res['bracket_rel'] = width
    if width > 0.01 and 'warning' not in res:
        res['warning'] = 'f0 bracket is {:.1%} wide; narrow the sweep around f0 for tank-scan accuracy.'.format(width)
    return res


def loop_gain(spectrum_samples, per, xs, lo, hi, t, gm_ref, res):
    """Startup loop gain gm * Z, as in the VCO design system's tank scan.

    Each gm module adds its own feedback path: gates on the opposite drains ->
    gm * Z11 of the gm-cancelled tank = gm * Rp(LC+loading); gates on port 2
    (transformer-coupled core) -> gm * Re Z21 of the gm-cancelled tank (drain
    current -> gate voltage), from the saved 4-port Y with every core's
    low-frequency cross terms removed.  Mixed cores are summed path by path.
    """
    mods = per[0]['gm']
    local = sum(item['gm_S'] for item in mods.values() if item['ctrl'] != (2, 3))
    remote = sum(item['gm_S'] for item in mods.values() if item['ctrl'] == (2, 3))
    rp = res.get('Rp_loaded_ohm')
    if not any(item['ctrl'] == (2, 3) for item in mods.values()):
        return {'gain': gm_ref * rp if rp else None, 'gain_kind': 'gm*Z11', 'core_gates': 'on P/N'}
    from .twoport import has_port2, full_matrix, z_pair
    kind = 'gm*Z21' if not local else 'gm*Z11 + gm*Z21'
    gates = 'on port 2' if not local else 'on P/N and on port 2'
    pairs = []
    for k in (lo, hi):
        s = min(spectrum_samples or [{}], key=lambda r: abs(r.get('frequency_Hz', 0) - xs[k]))
        if abs(s.get('frequency_Hz', 0) - xs[k]) > 1e-9 * xs[k] or not has_port2(s):
            return {'gain_kind': kind, 'core_gates': gates,
                    'gain_reason': 'Saved spectrum has no port-2 matrix at the f0 bracket.'}
        y = full_matrix(s)
        for item in mods.values():
            yx = off_diagonal(item['Y'], real=True)
            for i in range(len(yx)):
                for j in range(len(yx)):
                    y[i][j] -= yx[i][j]
        z = z_pair(y)
        if z is None:
            return {'gain_kind': kind, 'core_gates': gates, 'gain_reason': 'gm-cancelled 4-port is singular.'}
        pairs.append(z)
    z11 = _interp(pairs[0][0], pairs[1][0], t)
    z21 = _interp(pairs[0][1], pairs[1][1], t)
    gain = remote * z21.real + local * z11.real   # each path through the same gm-cancelled tank
    return {'gain': gain, 'gain_kind': kind, 'core_gates': gates,
            'Z11_off_ohm': [z11.real, z11.imag], 'Z21_off_ohm': [z21.real, z21.imag],
            'gate_ratio': z21.real / z11.real if z11.real else None}


def gain_curve(xs, per, sums):
    """Small-signal loop gain T(f) = G_neg(f) / Y_loss(f) on the sweep samples.

    Y_loss = Y_d + G_neg is the tank admittance with the core's negative
    conductance removed (same G_neg definition as at f0).  At f0, where
    Im Y_d = 0, |T| equals the startup margin and the phase of T is zero.
    """
    out = []
    for f, sa, sm in zip(xs, per, sums):
        g_neg = sm[0]['gm_neg']
        y_loss = sa['total'] + g_neg
        if abs(y_loss) > 0:
            t = g_neg / y_loss
            out.append((f, t.real, t.imag))
    return out


def z11_curve(samples):
    """(f, Re Z11, Im Z11) of the complete circuit from the saved two-port sweep."""
    from .resonance import _impedance, _KEYS
    out = []
    for sample in sorted(samples, key=lambda r: r['frequency_Hz']):
        try:
            f = float(sample['frequency_Hz'])
            z = _impedance(f, [float(sample[k]) for k in _KEYS])
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        if z is not None:
            out.append((f, z.real, z.imag))
    return out


def sweep_start(project):
    """Start of the requested sweep when a gm reference point was added below it."""
    from .model import number
    s = project.get('settings') or {}
    if not str(s.get('tank_gm_ref') or '').strip():
        return None
    try:
        return number(s['simulation_start'])
    except (KeyError, ValueError):
        return None


def tank_data(project, page_settings):
    """Analyze a completed run for all register points (no simulation)."""
    private = project.get('private') or {}
    spectrum = private.get('spectrum') or {}
    raw = spectrum.get('rows') or []
    settings = page_settings
    mode = backend_mode(settings)
    issues = check_roles(settings)
    if not raw:
        return {'rows': [], 'names': [], 'mode': mode, 'issues': issues,
                'message': 'Run the tank scan to measure this circuit.'}
    expected = private.get('spectrum_data_sha256')
    if expected and hashlib.sha256(json.dumps(spectrum, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest() != expected:
        raise ValueError('Saved SP spectrum checksum does not match; reload intact data or run again.')
    expected = private.get('loss_data_sha256')
    if expected:
        payload = {'plan': private.get('loss_plan'), 'spectrum': private.get('loss_spectrum')}
        if hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest() != expected:
            raise ValueError('Saved native module-current data checksum does not match; run again.')
    from .decomposition import result_names
    names = result_names(raw[0])
    groups = {}
    for sample in raw:
        groups.setdefault(sample.get('point', sample.get('code', 0)), []).append(sample)
    roles = effective_roles(settings)
    plan = private.get('loss_plan')
    rows = []
    for key, samples in sorted(groups.items()):
        identity = {name: samples[0][name] for name in names}
        identity.update({'point': key} if 'point' in samples[0] else {'code': key})
        if issues:
            # Roles only matter for the split; f0 and Re Z at f0 are still reported.
            try:
                result = analyze_point(samples, None, None, roles, 'passive', sweep_start(project))
            except (ValueError, KeyError, TypeError, ZeroDivisionError) as ex:
                result = {'available': False, 'reason': str(ex)}
            if result.get('available'):
                result['reason'] = 'Module split unavailable: ' + ' '.join(issues)
            else:
                result['reason'] = '{} {}'.format(result.get('reason', ''), ' '.join(issues)).strip()
        else:
            loss = (private.get('loss_spectrum') or {}).get(str(key))
            try:
                result = analyze_point(samples, loss, plan, roles, mode, sweep_start(project))
            except (ValueError, KeyError, TypeError, ZeroDivisionError) as ex:
                result = {'available': False, 'reason': str(ex)}
        row = dict(identity)
        row['tank'] = result
        row['z11'] = z11_curve(sweep_samples(samples, sweep_start(project)))
        from .twoport import z21_curve as _z21
        z2 = _z21(sweep_samples(samples, sweep_start(project)))
        if z2:
            row['z21'] = [(f, z21.real, z21.imag) for f, z11, z21 in z2]
        rows.append(row)
    message = ('Startup analysis at Im(Z11)=0 of the complete circuit (port 2 open). margin = G_neg / G_loss (> 1 starts); '
               'loop gain gm*Z uses the terminal gm at the lowest simulated frequency (Z21 when the core gates are on port 2).') if mode == 'active' else \
              'Passive tank: resonance, Rp and per-module loss at the first Im(Z)=0 crossing.'
    return {'rows': rows, 'names': names, 'mode': mode, 'issues': issues, 'message': message}


def refine_centers(rows):
    """f0 of every resolved code: the centers for per-code sweep refinement."""
    return sorted({round(r['tank']['f0_Hz'], 3) for r in rows if (r.get('tank') or {}).get('f0_Hz')})


def suggested_sweep(rows, points=201):
    """A linear sweep around all resolved f0 values (with a low gm reference point kept by Start)."""
    f0 = [r['tank']['f0_Hz'] for r in rows if (r.get('tank') or {}).get('f0_Hz')]
    if not f0:
        return None
    lo, hi = min(f0), max(f0)
    span = max(hi - lo, 0.02 * hi)
    return {'simulation_start': lo - 0.6 * span, 'simulation_stop': hi + 0.6 * span,
            'simulation_points': points, 'simulation_sweep': 'linear'}
