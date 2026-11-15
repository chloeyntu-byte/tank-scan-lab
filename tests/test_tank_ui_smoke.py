import os
import time
import unittest
from unittest import mock

from caplab import product_theme
from caplab.model import ROOT, load_project


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Tk display required')
class TankUISmokeTest(unittest.TestCase):
    def setUp(self):
        from caplab.ui import App
        self.native = mock.patch('caplab.backend.Backend.native', side_effect=AssertionError('Offline UI must not start native tools'))
        self.native.start()
        self.app = App(project=load_project(str(ROOT / 'examples' / 'ideal_tank.json')), tank=True)
        self.errors = []
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.app.geometry('1280x800+0+0')
        self.pump(.2)

    def tearDown(self):
        self.app.destroy()
        self.native.stop()
        self.assertEqual(self.errors, [])

    def pump(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.update()
            time.sleep(.01)

    def wait_rows(self):
        end = time.monotonic() + 20
        while time.monotonic() < end and not self.app.tank_view.rows:
            self.app.update()
            time.sleep(.02)
        return self.app.tank_view.rows

    def test_merged_mode_plots_and_theme_switch(self):
        app = self.app
        self.assertEqual(app.measurement_view.get(), 'Resonance / tank')
        app.tabs.select(app.resultpage)
        app.update_measurement_view()
        self.assertEqual(len(self.wait_rows()), 4)
        view = app.tank_view
        self.assertGreaterEqual(len(view.panels), 1)
        self.pump(.3)
        app.set_ui_theme('light')
        self.pump(.2)
        self.assertEqual(app.plot_theme.get().lower(), 'light')
        self.assertEqual(app.canvas_theme.get(), 'White')
        self.assertEqual(view.colors['PANEL'], product_theme.LIGHT['PANEL'])
        self.assertEqual(str(view.kpi.cget('background')).lower(), product_theme.LIGHT['PANEL'].lower())
        app.set_ui_theme('dark')
        self.pump(.2)
        self.assertEqual(app.plot_theme.get().lower(), 'neon')
        self.assertEqual(str(view.kpi.cget('background')).lower(), product_theme.DARK['PANEL'].lower())
        view.add_plot()
        self.pump(.2)
        self.assertEqual(len(view.panels), len(app.page()['tank']['plots']))

    def test_legacy_view_names_map_to_merged_mode(self):
        from caplab.ui import canonical_view
        self.assertEqual(canonical_view('Tank scan'), 'Resonance / tank')
        self.assertEqual(canonical_view('Resonance'), 'Resonance / tank')
        self.assertEqual(canonical_view('Capacitance'), 'Capacitance')




@unittest.skipUnless(os.environ.get('DISPLAY'), 'Tk display required')
class LinearityViewSmokeTest(unittest.TestCase):
    def test_c_step_and_inl_dnl_views(self):
        from caplab.ui import App
        with mock.patch('caplab.backend.Backend.native', side_effect=AssertionError('offline')):
            app = App(project=load_project(str(ROOT / 'examples' / 'ideal_array.json')))
            errors = []
            app.report_callback_exception = lambda *args: errors.append(args)
            try:
                app.geometry('1280x800+0+0')
                end = time.monotonic() + 5
                while time.monotonic() < end and not app.rows:
                    app.update()
                    time.sleep(.02)
                self.assertTrue(app.rows)
                for view in ('C step', 'INL / DNL', 'C / Q'):
                    app.cq_view.set(view)
                    app.draw_plots()
                    app.update()
                    if view == 'INL / DNL':
                        self.assertIn('max |DNL|', app.linearity_note.get())
            finally:
                app.destroy()
            self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
