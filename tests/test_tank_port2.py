"""Port 2 (P2/N2) and a transformer-coupled (Lim-type) gm core, against an analytic network.

The synthetic records use the native format: four raw excitations (P->N, into P,
P2->N2, into P2), every module terminal probed, 50-ohm ground ports on all four
nets, and the 4-port SP matrix.  Expected values follow the VCO design system's
tank-scan: gm cancelled -> Z_off; G_loss = Re(1/Z11_off), G_neg = G_loss - Re(1/Z11_on),
gain = gm * Re(Z21_off) at f0.
"""
import cmath
import math
import unittest

from caplab import tank_scan, twoport
from caplab.linalg import inverse, solve

L1, L2, K, R_SER = 0.5e-9, 1.0e-9, 0.7, 1.2      # primary / secondary halves, coupling, series R
C1, G1 = 1.0e-12, 0.4e-3                          # drain-side array (P-N)
C2, G2 = 0.3e-12, 0.2e-3                          # gate-side array (P2-N2)
GM, GDS, CG, GG = 20e-3, 1.5e-3, 0.15e-12, 0.2e-3  # per side; gate C and loss to ground
NETS = ('CAL_P', 'CAL_N', 'CAL_P2', 'CAL_N2')


def modules(f, v, gm=GM, gates=(3, 2)):
    """instance -> [(pin, net, voltage, current INTO the terminal)] for node voltages v (P, N, P2, N2)."""
    w = 2 * math.pi * f
    m = K * math.sqrt(L1 * L2)
    # windings A: P-VDD, B: N-VDD (primary), C: P2-VB, D: N2-VB (secondary); A-C and B-D coupled
    z = [[R_SER + 1j * w * L1, 0, 1j * w * m, 0], [0, R_SER + 1j * w * L1, 0, 1j * w * m],
         [1j * w * m, 0, R_SER + 1j * w * L2, 0], [0, 1j * w * m, 0, R_SER + 1j * w * L2]]
    iw = solve(z, list(v))
    xf = [('A', 'CAL_P', v[0], iw[0]), ('B', 'CAL_N', v[1], iw[1]), ('C', 'CAL_P2', v[2], iw[2]), ('D', 'CAL_N2', v[3], iw[3]),
          ('CT1', 'CAL_VDD', 0j, -iw[0] - iw[1]), ('CT2', 'CAL_VB', 0j, -iw[2] - iw[3])]
    y1, y2 = G1 + 1j * w * C1, G2 + 1j * w * C2
    yg = GG + 1j * w * CG
    d1 = gm * v[gates[0]] + GDS * v[0]   # M1: drain P, gate N2 (Lim) or N (gates on the drains)
    d2 = gm * v[gates[1]] + GDS * v[1]   # M2: drain N, gate P2 or P
    gnet = [NETS[gates[1]], NETS[gates[0]]]
    return {
        'XF': xf,
        'ARR': [('P', 'CAL_P', v[0], y1 * (v[0] - v[1])), ('N', 'CAL_N', v[1], y1 * (v[1] - v[0]))],
        'ARR2': [('P', 'CAL_P2', v[2], y2 * (v[2] - v[3])), ('N', 'CAL_N2', v[3], y2 * (v[3] - v[2]))],
        'GM': [('DP', 'CAL_P', v[0], d1), ('DN', 'CAL_N', v[1], d2),
               ('GP', gnet[0], v[gates[1]], yg * v[gates[1]]), ('GN', gnet[1], v[gates[0]], yg * v[gates[0]]),
               ('S', 'CAL_VSS', 0j, -d1 - d2 - yg * (v[gates[0]] + v[gates[1]]))],
    }


def matrix(f, gm=GM, gates=(3, 2)):
    cols = []
    for k in range(4):
        v = [1.0 if i == k else 0.0 for i in range(4)]
        cur = modules(f, v, gm, gates)
        cols.append([sum(i for pins in cur.values() for _, net, _, i in pins if net == n) for n in NETS])
    return [[cols[j][i] for j in range(4)] for i in range(4)]


def records(freqs, gm=GM, gates=(3, 2)):
    probes, order = [], []
    for inst, pins in modules(1e9, [1, 0, 0, 0], gm, gates).items():
        for pin, net, _, _ in pins:
            probes.append({'instance': inst, 'pin': pin, 'net': net})
            order.append((inst, pin))
    plan = {'probes': probes, 'port_fixture': 'ground_50ohm_each', 'port2': True,
            'instances': [{'id': i, 'kind': None, 'cell': c} for i, c in
                          (('XF', 'xfmr'), ('ARR', 'array'), ('ARR2', 'array'), ('GM', 'lim_pair'))]}
    from caplab.loss_native import SOURCES, STATE_KEYS
    loss, spectrum = [], []
    for f in freqs:
        y = matrix(f, gm, gates)
        a = [[y[i][j] + (1 / 50 if i == j else 0) for j in range(4)] for i in range(4)]
        item = {'frequency_Hz': f}
        for mode, keys in enumerate(STATE_KEYS):
            v = solve(a, list(SOURCES[mode]))
            cur = modules(f, v, gm, gates)
            pins = {}
            for idx, (inst, pin) in enumerate(order):
                _, _, vv, ii = next(x for x in cur[inst] if x[0] == pin)
                pins[str(idx)] = [vv.real, vv.imag, ii.real, ii.imag]
            item[keys[0]] = [v[0].real, v[0].imag, v[1].real, v[1].imag]
            item[keys[1]] = [v[2].real, v[2].imag, v[3].real, v[3].imag]
            item[keys[2]] = pins
        loss.append(item)
        row = {'code': 0, 'frequency_Hz': f}
        row.update(twoport.row_fields(y))
        red = [[complex(row['Y{}{}_G_S'.format(i, j)], row['Y{}{}_B_S'.format(i, j)]) for j in (1, 2)] for i in (1, 2)]
        yd = (red[0][0] - red[0][1] - red[1][0] + red[1][1]) / 4
        row.update(G_S=yd.real, B_S=yd.imag)
        spectrum.append(row)
    return plan, loss, spectrum


def z_on_off(f, gates=(3, 2)):
    y = matrix(f, GM, gates)
    off = [row[:] for row in y]
    off[0][gates[0]] -= GM
    off[1][gates[1]] -= GM
    return twoport.z_pair(y), twoport.z_pair(off)


def resonances(gates=(3, 2)):
    """Im Z11_on = 0 crossings (port 2 open), 1-20 GHz."""
    out, fs = [], [1e9 + k * 5e6 for k in range(3801)]
    prev = None
    for f in fs:
        im = z_on_off(f, gates)[0][0].imag
        if prev is not None and (prev[1] > 0) != (im > 0):
            lo, hi = prev[0], f
            for _ in range(80):
                mid = (lo + hi) / 2
                if (z_on_off(mid, gates)[0][0].imag > 0) == (prev[1] > 0):
                    lo = mid
                else:
                    hi = mid
            out.append((lo + hi) / 2)
        prev = (f, im)
    return out


ROLES = {'XF': 'inductor', 'ARR': 'array', 'ARR2': 'array', 'GM': 'gm'}


class LimCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modes = resonances()
        freqs = [10e6] + [1e9 + k * 5e6 for k in range(3801)]
        cls.plan, cls.loss, cls.spectrum = records(freqs)

    def test_startup_matches_gm_cancelled_tank(self):
        r = tank_scan.analyze_point(self.spectrum, self.loss, self.plan, ROLES, 'active', sweep_start=1e9)
        self.assertTrue(r['available'], r.get('reason'))
        # f0 = the crossing with the largest margin; check against the analytic crossing
        f0 = min(self.modes, key=lambda f: abs(f - r['f0_Hz']))
        self.assertLess(abs(r['f0_Hz'] / f0 - 1), 1e-5)
        (z11_on, _), (z11_off, z21_off) = z_on_off(f0)
        g_loss = (1 / z11_off).real
        g_neg = g_loss - (1 / z11_on).real
        self.assertAlmostEqual(r['G_loss_S'] / g_loss, 1, places=3)
        self.assertAlmostEqual(r['G_neg_S'] / g_neg, 1, places=3)
        self.assertAlmostEqual(r['margin'] / (g_neg / g_loss), 1, places=3)
        # loop gain gm * Z21 of the gm-cancelled tank, terminal gm from the 10 MHz reference
        self.assertAlmostEqual(r['gm_ref_S'] / GM, 1, places=6)
        self.assertEqual(r['gain_kind'], 'gm*Z21')
        self.assertAlmostEqual(r['gain'] / (GM * z21_off.real), 1, places=3)
        self.assertGreater(r['gain'], 0)
        # gate-side losses are part of G_loss: secondary array and gate input show up as shares
        shares = {c['module']: c['share_pct'] for c in r['contributions']}
        self.assertAlmostEqual(sum(shares.values()), 100, places=5)
        self.assertGreater(shares['ARR2'], 1)
        self.assertLess(r['module_sum_error'], 1e-9)
        self.assertEqual(len(r['modes']), 2)  # the two parallel resonances of the transformer tank
        self.assertEqual(r['margin'], max(m['margin'] for m in r['modes']))

    def test_one_port_results_use_port2_open(self):
        data = tank_scan.tank_data({'private': {'spectrum': {'rows': self.spectrum}}, 'instances': [{'id': k} for k in ROLES],
                                    'settings': {}, 'registers': []},
                                   {'roles': dict(ROLES), 'contains': {'inductor': True, 'array': True, 'gm': True}, 'loss_split': False})
        row = data['rows'][0]
        self.assertTrue(row['z21'])
        f, re21, im21 = row['z21'][len(row['z21']) // 2]
        z11, z21 = twoport.z_pair(matrix(f))
        self.assertAlmostEqual(abs(complex(re21, im21) / z21), 1, places=9)
        f, re11, im11 = row['z11'][len(row['z11']) // 2]
        self.assertAlmostEqual(abs(complex(re11, im11) / twoport.z_pair(matrix(f))[0]), 1, places=7)

    def test_packaged_core_with_gates_on_drains(self):
        """Gates tied to the opposite drains inside the cell; port 2 still present (e.g. an output)."""
        gates = (1, 0)
        plan, loss, spectrum = records([10e6] + [1e9 + k * 10e6 for k in range(1901)], gates=gates)
        r = tank_scan.analyze_point(spectrum, loss, plan, ROLES, 'active', sweep_start=1e9)
        self.assertTrue(r['available'], r.get('reason'))
        self.assertEqual(r['gain_kind'], 'gm*Z11')
        (z11_on, _), (z11_off, _) = z_on_off(r['f0_Hz'], gates)
        g_loss = (1 / z11_off).real
        self.assertAlmostEqual(r['G_loss_S'] / g_loss, 1, places=3)
        self.assertAlmostEqual(r['margin'] / ((g_loss - (1 / z11_on).real) / g_loss), 1, places=3)
        self.assertAlmostEqual(r['gain'] / (GM * r['Rp_loaded_ohm']), 1, places=9)
        self.assertAlmostEqual(r['gm_ref_S'] / GM, 1, places=6)

if __name__ == '__main__':
    unittest.main()
