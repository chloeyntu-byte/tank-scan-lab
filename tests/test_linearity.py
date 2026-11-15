import unittest
from caplab.linearity import linearity_rows, summary


class Linearity(unittest.TestCase):
    def rows(self, cs, f=1e9):
        return [{'code': k, 'frequency_Hz': f, 'C_F': c} for k, c in enumerate(cs)]

    def test_ideal_and_bowed(self):
        lsb = 2e-15
        ideal = linearity_rows(self.rows([1e-12 - k * lsb for k in range(8)]), 'code', [], 'cartesian')
        self.assertTrue(all(abs(r['INL_LSB']) < 1e-9 for r in ideal))
        self.assertTrue(all(abs(r['DNL_LSB']) < 1e-9 for r in ideal if r['DNL_LSB'] is not None))
        self.assertAlmostEqual(ideal[3]['C_step_F'], -lsb)
        self.assertIsNone(ideal[0]['C_step_F'])
        # one oversized step at code 4: DNL(4)=+1, INL rises then returns at the endpoint
        cs = [0, 1, 2, 3, 5, 6, 7, 8]
        r = linearity_rows(self.rows([c * 1e-15 for c in cs]), 'code', [], 'cartesian')
        l8 = 8 / 7.0
        self.assertAlmostEqual(r[4]['DNL_LSB'], 2 / l8 - 1)
        self.assertAlmostEqual(r[3]['INL_LSB'], (3 - 3 * l8) / l8)
        self.assertAlmostEqual(r[-1]['INL_LSB'], 0)
        self.assertAlmostEqual(summary(r)['max_abs_DNL_LSB'], abs(2 / l8 - 1))

    def test_frequencies_are_separate_curves(self):
        rows = self.rows([0, 1, 2], 1e9) + self.rows([0, 2, 4], 2e9)
        out = linearity_rows(rows, 'code', [], 'cartesian')
        self.assertEqual(len(out), 6)
        self.assertTrue(all(abs(r['INL_LSB']) < 1e-12 for r in out))


if __name__ == '__main__':
    unittest.main()
