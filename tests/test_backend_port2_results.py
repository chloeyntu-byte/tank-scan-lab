"""read_results with port 2: register values are still checked although no per-frequency scalars exist."""
import json
import tempfile
import unittest
from pathlib import Path

from caplab.backend import Backend


def results_file(folder, reg_value):
    run = Path(folder) / 'run'
    (run / 'psf').mkdir(parents=True)
    (run / 'psf' / 'spectre.out').write_text('spectre completes with 0 errors, 0 warnings\n')
    lines = ['HISTORY\tInteractive.0',
             'TEST\t1\t{}\t{}\tdone\tnil\t{}'.format(json.dumps('nominal'), json.dumps('CAP_SP'), json.dumps(str(run))),
             'OUT\t"CODE_VALUE"\t"expr"\t0', 'OUT\t"VDD_VALUE"\t"expr"\t1', 'OUT\t"VCM_VALUE"\t"expr"\t0.5']
    if reg_value is not None:
        lines.append('OUT\t"REG_R1"\t"expr"\t{}'.format(reg_value))
    path = Path(folder) / 'results.tsv'
    path.write_text('\n'.join(lines) + '\n')
    return path


CFG = {'analysis': 'sp', 'decomposition': True, 'port2': True, 'explicit': True, 'codes': [0], 'frequencies': [5e9],
       'vdd': 1.0, 'vcm': 0.5, 'registers': [{'id': 'R1', 'name': 'BANK'}], 'scan_points': [{'BANK': 3}]}


class Port2Registers(unittest.TestCase):
    def test_actual_register_value_is_checked(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(Backend.read_results(results_file(d, 3), CFG), [])
        for bad in (7, None):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(RuntimeError, 'register BANK'):
                    Backend.read_results(results_file(d, bad), CFG)

    def test_two_port_rows_keep_register_identity(self):
        cfg = dict(CFG, port2=False, decomposition=False)
        with tempfile.TemporaryDirectory() as d:
            path = results_file(d, 7)
            text = path.read_text() + 'OUT\t"C_0"\t"expr"\t1e-12\nOUT\t"G_0"\t"expr"\t0.001\nOUT\t"B_0"\t"expr"\t0.0314159\nOUT\t"Q_0"\t"expr"\t31.4159\n'
            path.write_text(text)
            with self.assertRaisesRegex(RuntimeError, 'register BANK'):
                Backend.read_results(path, cfg)


if __name__ == '__main__':
    unittest.main()
