"""Synthetic 8-bit thermometer-coded array (codes 0-255) for the large-code examples. No device models.

* ``examples/thermo8_cq.json`` (committed): the array alone, for Capacitance mode
  (C, Q, C step, INL, DNL over 256 codes).
* ``examples/thermo8_tank.json`` (about 45 MB, generated on demand, not committed):
  the same array in an LC tank with a cross-coupled gm, for Resonance / tank mode
  (f0, Rp, startup margin and loop gain for every code).

Array: 255 unit cells switched on in order (code n = n cells on).  Each unit is a
series Cu (8.2 fF nominal, sigma 1.5 % random + 1 % linear gradient along the
array, fixed seed) and a switch resistance; an off cell leaves 15 % of Cu.
Fixed 0.6 pF, small ground shunts.  Tank: 0.5 nH + 1 ohm per inductor half,
gm 30 mS, gds 1.5 mS, Cg 0.15 pF per side.

Usage::

    python -m caplab.thermo_example            # examples/thermo8_cq.json
    python -m caplab.thermo_example --tank     # also examples/thermo8_tank.json
"""
import json
import math
import random
import sys
from pathlib import Path

from .backend import digest
from .model import new_project
from .registers import add_register
from .spectrum import resample
from .workbook import cache

N = 255
CU, C_FIX, R_ON_UNIT, OFF = 8.2e-15, 0.6e-12, 900.0, 0.15
_RNG = random.Random(20261115)
UNITS = [CU * (1 + 0.015 * _RNG.gauss(0, 1) + 0.01 * (k / (N - 1) - 0.5) * 2) for k in range(N)]
CG_SIDE, QG = 40e-15, 60.0
L_HALF, R_SER = 0.5e-9, 1.0
GM, GDS, CG = 30e-3, 1.5e-3, 0.15e-12


def array_y(f, code):
    """(coupling admittance P-N, ground shunt admittance per side)."""
    w = 2 * math.pi * f
    yc = 1j * w * C_FIX + 2e-5
    for k, cu in enumerate(UNITS):
        if k < code:
            yc += 1 / (R_ON_UNIT + 1 / (1j * w * cu))
        else:
            yc += 1j * w * cu * OFF
    cg = CG_SIDE + 0.08 * code * CU
    yg = 1 / (1 / (QG * 2 * math.pi * 3e9 * cg) + 1 / (1j * w * cg))
    return yc, yg


def symbol(cell, pins):
    n = len(pins)
    h = max(1.0, 0.5 * n)
    return {'library': 'GENERIC', 'cell': cell, 'bbox': [-1.6, -h, 1.6, h],
            'pins': [{'name': name, 'xy': [-1.6 if k % 2 == 0 else 1.6, h - (k // 2 + 1) * 2 * h / ((n + 1) // 2 + 1)]}
                     for k, name in enumerate(pins)],
            'shapes': [{'kind': 'rect', 'points': [-1.6, -h, 1.6, h]}]}


def project(cells, start, stop, points, obs, tank):
    p = new_project()
    p.update(workspace='', library='GENERIC', reference={'library': 'GENERIC', 'cell': 'thermo8'})
    p['settings'].update(frequencies=obs, simulation_start=start, simulation_stop=stop, simulation_points=str(points),
                         simulation_sweep='linear', decomposition=True, capture_loss=tank)
    if tank:
        p['settings']['tank_gm_ref'] = '10M'
    for ident, cell, pins, roles, x in cells:
        p['instances'].append({'id': ident, 'library': 'GENERIC', 'cell': cell, 'view': 'schematic', 'x': x, 'y': 300,
                               'symbol': symbol(cell, pins), 'roles': roles})
    add_register(p, 'BANK', 8, '0:255', x=850, y=750)
    return p


ARR_CELL = ('ARR', 'Thermometer C array 8b', ['P', 'N', 'VSS', 'BANK<7:0>'],
            dict({'P': 'P', 'N': 'N', 'VSS': 'VSS'}, **{'BANK<%d>' % b: 'BANK<%d>' % b for b in range(8)}), 850)


def ymat_rows(freqs, code, extra=None):
    rows = []
    for f in freqs:
        yc, yg = array_y(f, code)
        y = [[yc + yg, -yc], [-yc, yc + yg]]
        if extra:
            e = extra(f)
            y = [[y[i][j] + e[i][j] for j in range(2)] for i in range(2)]
        row = {'point': code, 'BANK': code, 'frequency_Hz': f}
        for (i, j), key in (((0, 0), '11'), ((0, 1), '12'), ((1, 0), '21'), ((1, 1), '22')):
            row['Y%s_G_S' % key], row['Y%s_B_S' % key] = y[i][j].real, y[i][j].imag
        yd = (y[0][0] - y[0][1] - y[1][0] + y[1][1]) / 4
        row.update(G_S=yd.real, B_S=yd.imag)
        rows.append(row)
    return rows


def rounded(v):
    if isinstance(v, float):
        return float('{:.10g}'.format(v))
    if isinstance(v, list):
        return [rounded(x) for x in v]
    if isinstance(v, dict):
        return {k: rounded(x) for k, x in v.items()}
    return v


def workbook(page):
    return {'kind': 'caplab-workbook', 'version': 3, 'active_page': page['id'], 'pages': [page],
            'appearance': {'canvas': 'black', 'plot': 'neon', 'ui': 'dark'}}


def make_cq(out):
    p = project([ARR_CELL], '1G', '6G', 51, '2G, 3G, 4G', False)
    freqs = [1e9 + 5e9 * i / 50 for i in range(51)]
    rows = [r for code in range(256) for r in ymat_rows(freqs, code)]
    p['private'] = {'spectrum': {'version': 2, 'rows': rows}}
    res = resample(p['private']['spectrum'], '2G, 3G, 4G')
    page = {'id': 'thermo8_cq', 'name': '8-bit thermometer array C/Q', 'project': p, 'measurement_view': 'Capacitance',
            'result': dict(cache(res, digest(p), 'cartesian'), analysis='sp'), 'axis': 'BANK', 'editor': {'tab': 'results'}}
    wb = rounded(workbook(page))
    from .workbook import rows_hash
    wb['pages'][0]['result']['sha256'] = rows_hash(wb['pages'][0]['result']['rows'])  # hash of the stored (rounded) rows
    wb['pages'][0]['result']['digest'] = digest(wb['pages'][0]['project'])  # identity of the stored (rounded) setup
    (out / 'thermo8_cq.json').write_text(json.dumps(wb, separators=(',', ':')))


def tank_currents(f, vp, vn, code):
    w = 2 * math.pi * f
    yl = 1 / (R_SER + 1j * w * L_HALF)
    yc, yg = array_y(f, code)
    return {
        'IND': [('A', 'CAL_P', vp, yl * vp), ('B', 'CAL_N', vn, yl * vn), ('CT', 'CAL_VDD', 0j, -yl * (vp + vn))],
        'ARR': [('P', 'CAL_P', vp, yc * (vp - vn) + yg * vp), ('N', 'CAL_N', vn, yc * (vn - vp) + yg * vn),
                ('VSS', 'CAL_VSS', 0j, -yg * (vp + vn))],
        'GM': [('D1', 'CAL_P', vp, GM * vn + GDS * vp), ('D2', 'CAL_N', vn, GM * vp + GDS * vn),
               ('G1', 'CAL_N', vn, 1j * w * CG * vn), ('G2', 'CAL_P', vp, 1j * w * CG * vp),
               ('S', 'CAL_VSS', 0j, -(GM * vn + GDS * vp) - (GM * vp + GDS * vn) - 1j * w * CG * (vp + vn))],
    }


def tank_records(freqs, code):
    probes, order = [], []
    for inst, pins in tank_currents(1e9, 1, 0, code).items():
        for pin, net, _, _ in pins:
            probes.append({'instance': inst, 'pin': pin, 'net': net})
            order.append((inst, pin))
    plan = {'probes': probes, 'port_fixture': 'ground_50ohm_each',
            'instances': [{'id': 'IND', 'kind': None, 'cell': 'ind'}, {'id': 'ARR', 'kind': None, 'cell': 'array'},
                          {'id': 'GM', 'kind': None, 'cell': 'pair'}]}
    loss, spectrum = [], []
    for f in freqs:
        cols = []
        for vp, vn in ((1, 0), (0, 1)):
            cur = tank_currents(f, vp, vn, code)
            cols.append((sum(i for ps in cur.values() for _, n, _, i in ps if n == 'CAL_P'),
                         sum(i for ps in cur.values() for _, n, _, i in ps if n == 'CAL_N')))
        y = [[cols[0][0], cols[1][0]], [cols[0][1], cols[1][1]]]
        a = [[y[0][0] + 1 / 50, y[0][1]], [y[1][0], y[1][1] + 1 / 50]]
        det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
        item = {'frequency_Hz': f}
        for tag, (jp, jn) in (('', (1, -1)), ('cm_', (1, 0))):
            vp, vn = (jp * a[1][1] - a[0][1] * jn) / det, (a[0][0] * jn - a[1][0] * jp) / det
            cur = tank_currents(f, vp, vn, code)
            pins = {}
            for idx, (inst, pin) in enumerate(order):
                _, _, v, i = next(x for x in cur[inst] if x[0] == pin)
                pins[str(idx)] = [v.real, v.imag, i.real, i.imag]
            item[tag + 'input'] = [vp.real, vp.imag, vn.real, vn.imag]
            item[tag + 'pins'] = pins
        loss.append(item)
        row = {'point': code, 'BANK': code, 'frequency_Hz': f}
        for (i, j), key in (((0, 0), '11'), ((0, 1), '12'), ((1, 0), '21'), ((1, 1), '22')):
            row['Y%s_G_S' % key], row['Y%s_B_S' % key] = y[i][j].real, y[i][j].imag
        yd = (y[0][0] - y[0][1] - y[1][0] + y[1][1]) / 4
        row.update(G_S=yd.real, B_S=yd.imag)
        spectrum.append(row)
    return plan, loss, spectrum


def make_tank(out, points=111):
    cells = [('IND', 'Ideal centre-tapped L', ['A', 'B', 'CT'], {'A': 'P', 'B': 'N', 'CT': 'VDD'}, 350), ARR_CELL,
             ('GM', 'Ideal cross-coupled gm', ['D1', 'D2', 'G1', 'G2', 'S'],
              {'D1': 'P', 'D2': 'N', 'G1': 'N', 'G2': 'P', 'S': 'VSS'}, 1350)]
    p = project(cells, '2.85G', '5.25G', points, '4G', True)
    grid = [10e6] + [2.85e9 + 2.4e9 * i / (points - 1) for i in range(points)]
    loss, rows, plan = {}, [], None
    for code in range(256):
        plan, samples, spectrum = tank_records(grid, code)
        loss[str(code)] = samples
        rows += spectrum
    p['private'] = {'spectrum': {'version': 2, 'rows': rows}, 'loss_spectrum': loss, 'loss_plan': plan}
    page = {'id': 'thermo8_tank', 'name': '8-bit thermometer tank', 'project': p, 'result': None,
            'measurement_view': 'Resonance / tank', 'editor': {'tab': 'results'},
            'tank': {'roles': {'IND': 'inductor', 'ARR': 'array', 'GM': 'gm'},
                     'contains': {'inductor': True, 'array': True, 'gm': True}, 'gm_ref': '10M'}}
    (out / 'thermo8_tank.json').write_text(json.dumps(rounded(workbook(page)), separators=(',', ':')))


def main(argv=None):
    from .model import ROOT
    args = list(sys.argv[1:] if argv is None else argv)
    tank = '--tank' in args
    args = [a for a in args if a != '--tank']
    out = Path(args[0]) if args else Path(ROOT) / 'examples'
    out.mkdir(parents=True, exist_ok=True)
    make_cq(out)
    names = ['thermo8_cq.json']
    if tank:
        make_tank(out)
        names.append('thermo8_tank.json')
    for name in names:
        print(out / name, (out / name).stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main()
