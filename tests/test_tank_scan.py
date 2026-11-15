"""Tank scan analysis against an analytic cross-coupled LC network.

The synthetic records use the exact native format (two raw excitations, all
module terminals probed, 50-ohm ground-referenced ports), so the floating
reconstruction, module admittances and gm split are checked end to end.
"""
import cmath
import math
import unittest

from caplab import tank_scan

from caplab.tank_example import (module_currents, records as _records, analytic as _analytic,
                                  exact_f0 as _exact_f0, GM, GDS, CG, G_ARR, C_UNIT)

C_ARR = C_UNIT * 4      # code 2


def records(freqs, gm=GM, currents=module_currents):
    return _records(freqs, 2, gm, currents)


def analytic(f):
    return _analytic(f, 2)


def exact_f0(gm_present=True):
    return _exact_f0(2, gm_present)


ROLES = {'IND': 'inductor', 'ARR': 'array', 'GM': 'gm'}


class TankScanAnalytic(unittest.TestCase):
    def setUp(self):
        self.f0 = exact_f0()
        freqs = [10e6] + [self.f0 * (0.9 + 0.2 * k / 400) for k in range(401)]
        self.plan, self.loss, self.spectrum = records(freqs)

    def test_active_startup_values(self):
        r = tank_scan.analyze_point(self.spectrum, self.loss, self.plan, ROLES, 'active')
        self.assertTrue(r['available'], r.get('reason'))
        a = analytic(self.f0)
        self.assertAlmostEqual(r['f0_Hz'] / self.f0, 1, places=6)
        self.assertAlmostEqual(r['G_neg_S'] / (GM / 2), 1, places=5)
        self.assertAlmostEqual(r['G_core_load_S'] / (GDS / 2), 1, places=5)
        g_lc = a['ind'].real + a['arr'].real
        self.assertAlmostEqual(r['Rp_LC_ohm'] * g_lc, 1, places=5)
        g_loss = g_lc + GDS / 2
        self.assertAlmostEqual(r['Rp_loaded_ohm'] * g_loss, 1, places=5)
        self.assertAlmostEqual(r['margin'] / ((GM / 2) / g_loss), 1, places=5)
        self.assertAlmostEqual(r['gm_ref_S'] / GM, 1, places=9)
        self.assertAlmostEqual(r['gds_ref_S'] / GDS, 1, places=9)
        self.assertAlmostEqual(r['gmRp'] / (GM / g_loss), 1, places=5)
        self.assertLess(abs(r['net_check_S']), 1e-6 * g_loss)
        self.assertLess(r['module_sum_error'], 1e-9)
        # LC-only resonance excludes the gate capacitance of the core.
        self.assertAlmostEqual(r['f0_LC_Hz'] / exact_f0(False), 1, places=5)
        self.assertGreater(r['f0_LC_Hz'], r['f0_Hz'])
        shares = {c['module']: c['share_pct'] for c in r['contributions']}
        self.assertAlmostEqual(sum(shares.values()), 100, places=6)
        self.assertAlmostEqual(shares['GM'], 100 * (GDS / 2) / g_loss, places=4)
        self.assertTrue(r['shares_valid'])
        # Effective C and Q of the loaded tank.
        c_total = C_ARR + CG / 2
        self.assertAlmostEqual(r['C_eff_F'] / c_total, 1, delta=0.03)

    def test_gain_curve_matches_margin_at_f0(self):
        r = tank_scan.analyze_point(self.spectrum, self.loss, self.plan, ROLES, 'active', sweep_start=self.f0 * 0.9)
        curve = r['gain_curve']
        self.assertEqual(len(curve), 401)  # reference sample excluded
        f = [c[0] for c in curve]
        i = next(k for k in range(len(f) - 1) if f[k] <= r['f0_Hz'] <= f[k + 1])
        t = (r['f0_Hz'] - f[i]) / (f[i + 1] - f[i])
        mag = [abs(complex(c[1], c[2])) for c in curve]
        self.assertAlmostEqual((mag[i] + t * (mag[i + 1] - mag[i])) / r['margin'], 1, places=5)
        # Phase of T passes through zero at f0 (falls with frequency for a parallel tank).
        self.assertGreater(curve[i - 3][2], 0)
        self.assertLess(curve[i + 4][2], 0)
        # |T| peaks near, not exactly at, f0 (Re Y_loss varies); startup uses phase-zero.
        self.assertLess(abs(f[max(range(len(mag)), key=mag.__getitem__)] / r["f0_Hz"] - 1), 0.01)

    def test_passive_mode_matches_re_z(self):
        roles = dict(ROLES, GM='load')
        r = tank_scan.analyze_point(self.spectrum, self.loss, self.plan, roles, 'passive')
        self.assertTrue(r['available'], r.get('reason'))
        # Without the gm split the core enters as a net (negative) load.
        a = analytic(self.f0)
        self.assertAlmostEqual(r['G_loss_S'] / (a['ind'].real + a['arr'].real + (GDS - GM) / 2), 1, places=5)
        self.assertNotIn('margin', r)

    def test_passive_lc_only(self):
        plan, loss, spectrum = records([1e9 + k * 0.1e9 for k in range(400)], gm=0.0)
        r = tank_scan.analyze_point(spectrum, loss, plan, {'IND': 'inductor', 'ARR': 'array', 'GM': 'load'}, 'passive')
        self.assertTrue(r['available'], r.get('reason'))
        self.assertAlmostEqual(r['Rp_loaded_ohm'] / r['Z_real_ohm'], 1, places=4)

    def test_roles_and_mode(self):
        project = {'registers': [{'roles': {'B<0>': 'BANK<0>', 'VSS': 'VSS'}}],
                   'instances': [{'id': 'I0', 'kind': 'snp'}, {'id': 'I1', 'cell': 'CT_x', 'roles': {'SW<0>': 'BANK<0>'}},
                                 {'id': 'I2', 'cell': 'XCOUPLED_GM', 'roles': {'OUTP': 'P'}},
                                 {'id': 'I3', 'kind': 'passive', 'cell': 'capq'}]}
        page = {}
        s = tank_scan.tank_settings(page, project)
        self.assertEqual(s['roles'], {'I0': 'inductor', 'I1': 'array', 'I2': 'gm', 'I3': 'load'})
        self.assertEqual(tank_scan.backend_mode(s), 'active')
        page['tank']['contains']['gm'] = False
        s = tank_scan.tank_settings(page, project)
        self.assertEqual(tank_scan.backend_mode(s), 'passive')
        self.assertEqual(tank_scan.effective_roles(s)['I2'], 'load')
        page['tank']['contains']['gm'] = True
        page['tank']['roles']['I2'] = 'load'
        self.assertTrue(tank_scan.check_roles(tank_scan.tank_settings(page, project)))

    def test_tank_data_rows(self):
        project = {'private': {'spectrum': {'rows': self.spectrum}, 'loss_spectrum': {'2': self.loss},
                               'loss_plan': self.plan},
                   'instances': [{'id': k} for k in ROLES], 'registers': []}
        settings = {'roles': dict(ROLES), 'contains': {'inductor': True, 'array': True, 'gm': True}}
        data = tank_scan.tank_data(project, settings)
        self.assertEqual(data['mode'], 'active')
        self.assertTrue(data['rows'][0]['tank']['available'], data['rows'][0]['tank'].get('reason'))
        z = data['rows'][0]['z11']
        self.assertEqual(len(z), len(self.spectrum))
        peak = max(z, key=lambda c: abs(complex(c[1], c[2])))
        self.assertLess(abs(peak[0] / self.f0 - 1), 0.01)
        project['settings'] = {'tank_gm_ref': '10M', 'simulation_start': self.f0 * 0.9}
        self.assertEqual(len(tank_scan.tank_data(project, settings)['rows'][0]['z11']), len(self.spectrum) - 1)
        self.assertTrue(tank_scan.needs_module_currents(dict(settings, loss_split=False)))
        passive = {'roles': dict(ROLES), 'contains': {'inductor': True, 'array': True, 'gm': False}, 'loss_split': False}
        self.assertFalse(tank_scan.needs_module_currents(passive))
        r = tank_scan.tank_data(dict(project, private={'spectrum': {'rows': self.spectrum}}), passive)['rows'][0]['tank']
        self.assertTrue(r['available'] and r['partial'], r.get('reason'))
        sweep = tank_scan.suggested_sweep(data['rows'])
        self.assertLess(sweep['simulation_start'], self.f0)
        self.assertGreater(sweep['simulation_stop'], self.f0)


class TankScanDefinition(unittest.TestCase):
    """gm rolls off with frequency: primary values follow tank-scan (DC gm cancelled)."""
    def test_rolloff(self):
        fp = 20e9
        def rolled(f, vp, vn, code=2, gm=GM):
            return module_currents(f, vp, vn, code, GM / (1 + 1j * f / fp))
        f0 = exact_f0()
        plan, loss, spectrum = records([10e6] + [f0 * (0.8 + 0.4 * k / 800) for k in range(801)], currents=rolled)
        r = tank_scan.analyze_point(spectrum, loss, plan, ROLES, 'active')
        self.assertTrue(r['available'], r.get('reason'))
        f = r['f0_Hz']
        gmf = GM / (1 + 1j * f / fp)
        a = analytic(f)
        g_net = a['ind'].real + a['arr'].real + (GDS - gmf.real) / 2
        dc_gm = GM / (1 + 1j * 10e6 / fp)
        self.assertAlmostEqual(r['G_neg_S'] / (dc_gm.real / 2), 1, places=4)
        self.assertAlmostEqual((r['G_loss_S'] - r['G_neg_S']) / g_net, 1, places=4)
        self.assertAlmostEqual(r['G_neg_f0_S'] / (gmf.real / 2), 1, places=3)
        self.assertGreater(r['G_loss_S'], r['G_loss_f0_S'])
        self.assertIn('tank-scan', r['definition'])


class TankExample(unittest.TestCase):
    def test_bundled_example_analyzes(self):
        import json
        from pathlib import Path
        from caplab.workbook import workbook
        path = Path(__file__).resolve().parents[1] / 'examples' / 'ideal_tank.json'
        page = workbook(json.loads(path.read_text(encoding='utf-8')))['pages'][0]
        settings = tank_scan.tank_settings(page, page['project'])
        data = tank_scan.tank_data(page['project'], settings)
        self.assertEqual(len(data['rows']), 4)
        for row in data['rows']:
            t = row['tank']
            self.assertTrue(t['available'], t.get('reason'))
            self.assertAlmostEqual(t['G_neg_S'] / (GM / 2), 1, places=5)
            self.assertGreater(t['margin'], 1)


class EdgeCases(unittest.TestCase):
    """Regression cases from the v1.1.0 review."""
    def test_reference_point_not_a_resonance_bracket(self):
        f0 = exact_f0()
        plan, loss, spectrum = records([10e6] + [6e9 + 2e9 * k / 200 for k in range(201)])
        r = tank_scan.analyze_point(spectrum, loss, plan, ROLES, 'active', sweep_start=6e9)
        self.assertFalse(r['available'])
        plan, loss, spectrum = records([10e6] + [4e9 + 4e9 * k / 400 for k in range(401)])
        r = tank_scan.analyze_point(spectrum, loss, plan, ROLES, 'active', sweep_start=4e9)
        self.assertTrue(r['available'], r.get('reason'))
        self.assertAlmostEqual(r['f0_Hz'] / f0, 1, places=4)
        self.assertAlmostEqual(r['gm_ref_S'] / GM, 1, places=9)

    def test_f0_on_first_sweep_sample(self):
        plan, loss, spectrum = records([10e6] + [4e9 + 4e9 * k / 400 for k in range(401)])
        orig = tank_scan.find_first_resonance
        tank_scan.find_first_resonance = lambda samples: {'available': True, 'frequency_Hz': 4e9, 'Z_real_ohm': 100.0,
                                                          'Z_imag_ohm': 0.0, 'bracket_Hz': [4e9, 4.01e9]}
        try:
            r = tank_scan.analyze_point(spectrum, loss, plan, ROLES, 'active', sweep_start=4e9)
        finally:
            tank_scan.find_first_resonance = orig
        self.assertTrue(r['available'], r.get('reason'))

    def test_exact_zero_crossings(self):
        self.assertEqual(tank_scan._crossing([1, 2, 3], [0, 1, 2]), (1, 0, 1))
        self.assertEqual(tank_scan._crossing([1, 2, 3], [-2, -1, 0]), (3, 1, 2))
        self.assertIsNone(tank_scan._crossing([1, 2, 3], [1, 2, 3]))


class ReferenceGrid(unittest.TestCase):
    def test_reference_point_prepended(self):
        from caplab.spectrum import simulation_grid
        s = {'frequencies': '5G', 'simulation_start': '4G', 'simulation_stop': '6G', 'simulation_points': 3,
             'simulation_sweep': 'linear', 'tank_gm_ref': '10M'}
        self.assertEqual(simulation_grid(s), [1e7, 4e9, 5e9, 6e9])
        s['tank_gm_ref'] = ''
        self.assertEqual(simulation_grid(s), [4e9, 5e9, 6e9])


if __name__ == '__main__':
    unittest.main()


class Refinement(unittest.TestCase):
    def test_grid_keeps_base_and_adds_clusters(self):
        from caplab.spectrum import simulation_grid
        base = {'frequencies': '5G', 'simulation_start': '1G', 'simulation_stop': '20G', 'simulation_points': 101,
                'simulation_sweep': 'log', 'tank_gm_ref': '10M'}
        g0 = simulation_grid(base)
        g1 = simulation_grid(dict(base, tank_refine=[3.0e9, 7.5e9, 19.99e9]))
        self.assertTrue(set(g0) <= set(g1))
        self.assertEqual(g1[0], 10e6)
        self.assertEqual(g1, sorted(g1))
        for f0 in (3.0e9, 7.5e9):
            near = [f for f in g1 if abs(f / f0 - 1) <= 0.006 + 1e-12]
            self.assertGreaterEqual(len(near), 13)
            step = max(b - a for a, b in zip(near, near[1:]))
            self.assertLessEqual(step / f0, 0.0011)
        self.assertLessEqual(max(g1), 20e9)

    def test_refined_bracket_is_tight(self):
        f0 = exact_f0()
        base = [10e6] + [f0 * (0.7 + 0.6 * k / 30) for k in range(31)]
        from caplab.spectrum import refinement_points
        grid = sorted(set(base) | set(refinement_points([f0 * 1.0003], base[1], base[-1])))
        plan, loss, spectrum = records(grid)
        r = tank_scan.analyze_point(spectrum, loss, plan, ROLES, 'active', sweep_start=base[1])
        self.assertTrue(r['available'], r.get('reason'))
        self.assertLess(r['bracket_rel'], 0.0011)
        self.assertNotIn('bracket', r.get('warning') or '')
        self.assertAlmostEqual(r['f0_Hz'] / f0, 1, places=6)
        self.assertEqual(tank_scan.refine_centers([{'tank': r}]), [round(r['f0_Hz'], 3)])


class ReviewFixes(unittest.TestCase):
    def test_refinement_keeps_base_endpoints(self):
        from caplab.spectrum import simulation_grid
        g = simulation_grid({'frequencies': '2G', 'simulation_start': '1G', 'simulation_stop': '2G', 'simulation_points': 2,
                             'simulation_sweep': 'linear', 'tank_refine': [2e9 / 1.006 * (1 - 1e-10)]})
        self.assertEqual(g[-1], 2e9)
        self.assertEqual(g[0], 1e9)
        self.assertEqual(g, sorted(set(g)))

    def test_resonance_on_a_sample_counted_once(self):
        from caplab.resonance import find_resonances
        rows = []
        for f, b in ((1e9, -0.001), (2e9, 0.0), (3e9, 0.001)):
            row = {'frequency_Hz': f}
            for key, v in (('11', complex(0.001, b)), ('12', -0.0005), ('21', -0.0005), ('22', complex(0.001, b))):
                v = complex(v)
                row['Y%s_G_S' % key], row['Y%s_B_S' % key] = v.real, v.imag
            rows.append(row)
        found = [r for r in find_resonances(rows) if r.get('available')]
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0]['frequency_Hz'], 2e9)
