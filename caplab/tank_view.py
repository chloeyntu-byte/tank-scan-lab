"""Tank scan view: choose what the canvas contains, assign roles, read startup results.

Changing roles or the 'contains' selection only re-analyzes saved native data;
it never launches a simulation.
"""
import csv
import math
import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog

from . import tank_scan
from .plotview import CQPlot
from .freqplot import FreqPlot
from .tableview import ResultsTable

ROLE_CHOICES = [tank_scan.ROLE_LABELS[r] for r in tank_scan.ROLES]
ROLE_FROM_LABEL = {v: k for k, v in tank_scan.ROLE_LABELS.items()}

COLUMNS = [
    ('f0_GHz', 'f0 (GHz)'), ('f0_LC_GHz', 'f0 LC only (GHz)'),
    ('Rp_LC_ohm', 'Rp(LC) (ohm)'), ('Rp_loaded_ohm', 'Rp(LC+loading) (ohm)'),
    ('margin', 'Startup margin G_neg/G_loss'), ('gain', 'Loop gain gm*Z'), ('core_gates', 'gm gates'),
    ('Z21_off_ohm', 'Re Z21 @f0, gm off (ohm)'), ('gate_ratio', 'V_gate / V_drain'),
    ('Rp_loaded_f0_ohm', 'Rp(LC+loading), gm@f0 split (ohm)'), ('margin_f0', 'Margin, gm@f0 split'),
    ('gm_ref_mS', 'gm @f_ref (mS)'), ('gds_ref_mS', 'gds @f_ref (mS)'),
    ('gm_f0_mS', 'gm @f0 (mS)'), ('gload_f0_mS', 'g_load @f0 (mS)'),
    ('G_neg_mS', 'G_neg (mS)'), ('G_LC_mS', 'G_LC (mS)'), ('G_core_mS', 'Core loading (mS)'),
    ('G_other_mS', 'Other loads (mS)'), ('G_loss_mS', 'G_loss (mS)'),
    ('Q_LC', 'Q LC'), ('Q_loaded', 'Q loaded'), ('C_eff_fF', 'C_eff (fF)'), ('L_eff_nH', 'L_eff (nH)'),
    ('bracket_pct', 'f0 bracket (%)'), ('status', 'Status')]
PORT2_ONLY = {'Z21_off_ohm', 'gate_ratio'}
PASSIVE_HIDE = {'margin', 'gain', 'core_gates', 'Z21_off_ohm', 'gate_ratio', 'Rp_loaded_f0_ohm', 'margin_f0', 'gm_ref_mS', 'gds_ref_mS', 'gm_f0_mS', 'gload_f0_mS', 'G_neg_mS', 'G_core_mS'}


# Plot manager catalog: key -> (menu label, kind, needs, spec)
#   kind 'point': one value per scan point (spec = display-row key, title, unit)
#   kind 'freq' : one curve per scan point vs frequency
#   kind 'share': loss share of each module vs scan point
# needs: None, 'split' (module loss split or gm core), 'active' (gm core)
QUANTITIES = [
    ('f0', 'f0', 'point', None, ('f0_GHz', 'f0 (GHz)', 'GHz')),
    ('f0lc', 'f0 LC only', 'point', 'split', ('f0_LC_GHz', 'f0 LC only (GHz)', 'GHz')),
    ('rpload', 'Rp(LC+loading)', 'point', None, ('Rp_loaded_ohm', 'Rp(LC+loading) at f0 (ohm)', 'ohm')),
    ('rplc', 'Rp(LC)', 'point', 'split', ('Rp_LC_ohm', 'Rp(LC) at f0 (ohm)', 'ohm')),
    ('margin', 'Startup margin', 'point', 'active', ('margin', 'Startup margin G_neg/G_loss', '')),
    ('gain', 'Loop gain gm·Z', 'point', 'active', ('gain', 'Loop gain gm*Z (Z21 with gates on port 2)', '')),
    ('gmrp', 'gm·Rp', 'point', 'active', ('gmRp', 'gm*Rp', '')),
    ('gm', 'gm @f_ref', 'point', 'active', ('gm_ref_mS', 'gm @f_ref per side (mS)', 'mS')),
    ('gds', 'gds @f_ref', 'point', 'active', ('gds_ref_mS', 'gds @f_ref per side (mS)', 'mS')),
    ('gneg', 'G_neg', 'point', 'active', ('G_neg_mS', 'G_neg at f0 (mS)', 'mS')),
    ('gcore', 'Core loading', 'point', 'active', ('G_core_mS', 'Core loading at f0 (mS)', 'mS')),
    ('gloss', 'G_loss', 'point', 'split', ('G_loss_mS', 'G_loss at f0 (mS)', 'mS')),
    ('qlc', 'Q LC', 'point', 'split', ('Q_LC', 'Q of LC only', '')),
    ('qload', 'Q loaded', 'point', 'split', ('Q_loaded', 'Q loaded', '')),
    ('ceff', 'C_eff', 'point', 'split', ('C_eff_fF', 'C_eff (fF)', 'fF')),
    ('leff', 'L_eff', 'point', 'split', ('L_eff_nH', 'L_eff (nH)', 'nH')),
    ('share', 'Loss share by module', 'share', 'split', ('share_pct', 'Share of G_loss at f0 (%)', '%')),
    ('z_abs', '|Z11| vs f', 'freq', None, ('z', '|Z11| (ohm)', 'ohm')),
    ('z_phase', 'Phase Z11 vs f', 'freq', None, ('z', 'Phase of Z11 (deg)', 'deg')),
    ('z_re', 'Re Z11 vs f', 'freq', None, ('z', 'Re Z11 (ohm)', 'ohm')),
    ('z_im', 'Im Z11 vs f', 'freq', None, ('z', 'Im Z11 (ohm)', 'ohm')),
    ('z21_abs', '|Z21| vs f', 'freq', 'port2', ('z21', '|Z21| port 2 / port 1 (ohm)', 'ohm')),
    ('z21_phase', 'Phase Z21 vs f', 'freq', 'port2', ('z21', 'Phase of Z21 (deg)', 'deg')),
    ('t_abs', 'Loop gain |T| vs f', 'freq', 'active', ('t', 'Loop gain |T| = |G_neg / Y_loss|', '')),
    ('t_phase', 'Loop gain phase vs f', 'freq', 'active', ('t', 'Phase of T (deg)', 'deg')),
]
QUANTITY = {q[0]: q for q in QUANTITIES}
F0_AXIS = 'f0 (GHz)'
FREQ_AXIS = 'Frequency (GHz)'
FREQ_LOG_AXIS = 'Frequency (GHz), log'
NEEDS_TEXT = {'active': 'Needs the gm core: tick "gm core" under Canvas contains and run.',
              'port2': 'Needs port 2: give two canvas pins the roles P2 and N2, and run.',
              'split': 'Needs the module loss split: tick "Module loss split" and run again.'}


def complex_value(key, z):
    if key in ('z_abs', 't_abs', 'z21_abs'):
        return abs(z)
    if key in ('z_phase', 't_phase', 'z21_phase'):
        return math.degrees(math.atan2(z.imag, z.real))
    if key == 'z_re':
        return z.real
    return z.imag


def interp_complex(curve, f):
    """Linear interpolation of a [(f, re, im), ...] curve at f (None outside)."""
    for a, b in zip(curve, curve[1:]):
        if a[0] <= f <= b[0] and b[0] > a[0]:
            t = (f - a[0]) / (b[0] - a[0])
            return complex(a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2]))
    return None


class PlotPanel(ttk.Frame):
    """One plot tab: quantity + x axis chosen by the user."""

    def __init__(self, view, spec):
        super().__init__(view.plotbook)
        self.view = view
        self.spec = spec
        bar = ttk.Frame(self, padding=(4, 4))
        bar.pack(fill='x')
        ttk.Label(bar, text='Quantity', style='Muted.TLabel').pack(side='left')
        self.qvar = tk.StringVar()
        self.qbox = ttk.Combobox(bar, textvariable=self.qvar, state='readonly', width=24)
        self.qbox.pack(side='left', padx=(4, 12))
        self.qbox.bind('<<ComboboxSelected>>', lambda e: self.changed())
        ttk.Label(bar, text='X axis', style='Muted.TLabel').pack(side='left')
        self.xvar = tk.StringVar()
        self.xbox = ttk.Combobox(bar, textvariable=self.xvar, state='readonly', width=16)
        self.xbox.pack(side='left', padx=(4, 12))
        self.xbox.bind('<<ComboboxSelected>>', lambda e: self.changed())
        self.only = tk.BooleanVar(value=bool(spec.get('only')))
        self.only_check = ttk.Checkbutton(bar, text='Selected point only', variable=self.only, command=self.changed)
        ttk.Button(bar, text='Remove plot', style='Ghost.TButton', command=lambda: view.remove_plot(self)).pack(side='right')
        self.cq = CQPlot(self, height=280)
        self.cq.hide_single_legend = True
        self.cq.axis_labels = {'f0_GHz': F0_AXIS}
        self.fp = FreqPlot(self, on_pick=view.pick_point, height=280)
        self.canvas = None
        self.set_theme(view.theme)

    def title(self):
        return QUANTITY.get(self.spec.get('q'), QUANTITIES[0])[1]

    def destroy(self):
        # Release the Tcl variables here, in the Tk thread.  Left to the cyclic GC
        # they may be collected on a worker thread, where each one stalls ~1 s.
        for var in (self.qvar, self.xvar, self.only):
            try:
                var._tk.globalunsetvar(var._name)
            except (tk.TclError, AttributeError):
                pass
            var._tk = None
        super().destroy()

    def set_theme(self, theme):
        self.cq.set_theme(theme)
        self.fp.set_theme(theme)

    def show(self, widget):
        if self.canvas is not widget:
            if self.canvas is not None:
                self.canvas.pack_forget()
            widget.pack(fill='both', expand=True)
            self.canvas = widget

    def changed(self):
        label_to_key = {q[1]: q[0] for q in QUANTITIES}
        self.spec['q'] = label_to_key.get(self.qvar.get(), self.spec.get('q'))
        self.spec['x'] = self.xvar.get()
        self.spec['only'] = bool(self.only.get())
        try:
            self.view.plotbook.tab(self, text=self.title())
        except tk.TclError:
            pass
        self.refresh()

    def refresh(self):
        v = self.view
        key, label, kind, needs, spec = QUANTITY.get(self.spec.get('q'), QUANTITIES[0])
        choices = [q[1] for q in QUANTITIES if v.available(q[3]) or q[0] == key]
        self.qbox.configure(values=choices)
        self.qvar.set(label)
        if kind == 'freq':
            axes = [FREQ_AXIS, FREQ_LOG_AXIS]
        elif kind == 'share':
            axes = list(v.axis_choices)
        else:
            axes = list(v.axis_choices) + [F0_AXIS]
        self.xbox.configure(values=axes)
        if self.spec.get('x') not in axes:
            self.spec['x'] = (FREQ_LOG_AXIS if v.log_sweep() else FREQ_AXIS) if kind == 'freq' else v.default_axis
        self.xvar.set(self.spec['x'])
        if kind == 'freq':
            self.only_check.pack(side='left')
        else:
            self.only_check.pack_forget()
        message = None if v.available(needs) else NEEDS_TEXT[needs]
        if kind == 'point':
            self.show(self.cq)
            rows = [r for r in v.rows if r.get(spec[0]) is not None] if message is None else []
            self.cq.empty_message = message or 'No resolved values; run the scan (or check the status column).'
            axis = self.axis_key()
            mode = 'list' if axis == 'f0_GHz' else getattr(v, 'mode', 'cartesian')
            self.cq.set_data(rows, axis, v.data.get('names', []), mode, metrics=[(spec[0], spec[1], 1, spec[2])],
                             include_frequency=False)
            return
        self.show(self.fp)
        self.fp.on_pick = v.pick_point if kind == 'freq' else None
        self.fp.only_selected = bool(self.only.get())
        self.fp.logx = self.spec['x'] == FREQ_LOG_AXIS
        if message:
            self.fp.set_curves([], spec[1], self.spec['x'], spec[2], empty_message=message)
        elif kind == 'freq':
            self.fp.set_curves(self.freq_curves(key, spec[0]), spec[1], self.spec['x'], spec[2],
                               empty_message='No saved sweep data; run the scan.' if spec[0] in ('z', 'z21') else
                               'No loop-gain data; run with the gm core and module currents.')
        else:
            self.fp.set_curves(self.share_curves(), spec[1], self.xlabel(), spec[2], palette='categorical',
                               empty_message='No module loss split; tick "Module loss split" and run.')
        self.highlight()

    def axis_key(self):
        x = self.spec.get('x')
        return 'f0_GHz' if x == F0_AXIS else 'point' if x == 'Scan point' else x

    def xlabel(self):
        x = self.axis_key()
        return 'Scan point (index)' if x == 'point' else 'Decimal code' if x == 'code' else x + ' (decimal)'

    def freq_curves(self, key, source):
        out = []
        for row in self.view.data.get('rows', []):
            ident = self.view.ident(row)
            curve = row.get('z11') if source == 'z' else row.get('z21') if source == 'z21' else (row.get('tank') or {}).get('gain_curve')
            if not curve:
                continue
            xs = [c[0] / 1e9 for c in curve]
            ys = [complex_value(key, complex(c[1], c[2])) for c in curve]
            f0 = (row.get('tank') or {}).get('f0_Hz')
            marker = None
            if f0:
                z = interp_complex(curve, f0)
                if z is not None:
                    marker = (f0 / 1e9, complex_value(key, z))
            long, tag = self.view.labels.get(ident, (str(ident), str(ident)))
            out.append({'key': ident, 'label': long, 'tag': tag, 'x': xs, 'y': ys, 'marker': marker})
        return out

    def share_curves(self):
        axis = self.axis_key()
        modules = {}
        for row in self.view.data.get('rows', []):
            r = row.get('tank') or {}
            if not r.get('available') or r.get('partial'):
                continue
            x = row.get(axis)
            if not isinstance(x, (int, float)):
                continue
            for c in r.get('contributions') or []:
                if c.get('share_pct') is not None:
                    name = '{} · {}'.format(c['module'], tank_scan.ROLE_LABELS.get(c.get('role'), c.get('role', '')))
                    modules.setdefault(name, []).append((x, c['share_pct']))
        out = []
        for name, pts in sorted(modules.items(), key=lambda kv: -max(p[1] for p in kv[1])):
            pts.sort()
            out.append({'key': name, 'label': name, 'x': [p[0] for p in pts], 'y': [p[1] for p in pts], 'dots': True})
        return out

    def highlight(self):
        v = self.view
        if self.canvas is not self.fp:
            return
        key = QUANTITY.get(self.spec.get('q'), QUANTITIES[0])
        if key[2] == 'share':
            row = next((r for r in v.data.get('rows', []) if v.ident(r) == v.selected_key), None)
            x = row.get(self.axis_key()) if row else None
            module = self.fp.selected if any(c['key'] == self.fp.selected for c in self.fp.curves) else None
            self.fp.set_selected(module, x if isinstance(x, (int, float)) else None)
        else:
            self.fp.set_selected(v.selected_key)


def _scaled(value, scale):
    return None if value is None else value * scale


def display_rows(data):
    out = []
    for row in data['rows']:
        r = row['tank']
        item = {k: v for k, v in row.items() if k not in ('tank', 'z11', 'z21')}
        item.update(
            f0_GHz=_scaled(r.get('f0_Hz'), 1e-9), f0_LC_GHz=_scaled(r.get('f0_LC_Hz'), 1e-9),
            Rp_LC_ohm=r.get('Rp_LC_ohm'), Rp_loaded_ohm=r.get('Rp_loaded_ohm'),
            margin=r.get('margin'), gmRp=r.get('gmRp'), gain=r.get('gain'), core_gates=r.get('core_gates'),
            Z21_off_ohm=(r.get('Z21_off_ohm') or [None])[0], gate_ratio=r.get('gate_ratio'),
            Rp_loaded_f0_ohm=r.get('Rp_loaded_f0_ohm'), margin_f0=r.get('margin_f0'),
            gm_ref_mS=_scaled(r.get('gm_ref_S'), 1e3), gds_ref_mS=_scaled(r.get('gds_ref_S'), 1e3),
            gm_f0_mS=_scaled(r.get('gm_f0_S'), 1e3), gload_f0_mS=_scaled(r.get('gload_f0_S'), 1e3),
            G_neg_mS=_scaled(r.get('G_neg_S'), 1e3), G_LC_mS=_scaled(r.get('G_LC_S'), 1e3),
            G_core_mS=_scaled(r.get('G_core_load_S'), 1e3), G_other_mS=_scaled(r.get('G_other_S'), 1e3),
            G_loss_mS=_scaled(r.get('G_loss_S'), 1e3), Q_LC=r.get('Q_LC'), Q_loaded=r.get('Q_loaded'),
            C_eff_fF=_scaled(r.get('C_eff_F'), 1e15), L_eff_nH=_scaled(r.get('L_eff_H'), 1e9),
            bracket_pct=_scaled(r.get('bracket_rel'), 100))
        if not r.get('available'):
            item['status'] = r.get('reason', 'Unavailable')
        else:
            parts = []
            if r.get('margin') is not None:
                parts.append('Starts' if r['margin'] > 1 else 'No start (margin < 1)')
            if r.get('partial'):
                parts.append(r.get('reason', ''))
            if r.get('warning'):
                parts.append(r['warning'])
            item['status'] = '; '.join(p for p in parts if p) or 'OK'
        for key, value in list(item.items()):
            if isinstance(value, float) and math.isfinite(value):
                item[key] = float('{:.6g}'.format(value))
        out.append(item)
    return out


def palette(name='dark'):
    """Tank view colors: the shared RF-FIELDWORK palette (dark) or its light variant."""
    from .product_theme import palette as theme_palette
    return theme_palette(name)


def ensure_styles(app, c=None):
    """Card, badge and checkbox styles used by the tank view (idempotent)."""
    c = c or palette()
    style = ttk.Style(app)
    font = getattr(app, 'font_family', 'TkDefaultFont')
    style.configure('Card.TFrame', background=c['CARD'])
    style.configure('Card.TLabel', background=c['CARD'], foreground=c['INK'])
    style.configure('CardMuted.TLabel', background=c['CARD'], foreground=c['MUTED'], font=(font, 9))
    style.configure('Badge.TLabel', background=c['SELECT'], foreground=c['ACCENT_TEXT'], font=(font, 9, 'bold'), padding=(8, 3))
    style.configure('Card.TCheckbutton', background=c['CARD'])
    style.map('Card.TCheckbutton', background=[('active', c['CARD'])])


class TankView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.data = {'rows': [], 'names': [], 'mode': 'passive', 'issues': []}
        self.rows = []
        self.colors = palette(getattr(app, 'ui_palette_name', 'dark'))
        ensure_styles(app, self.colors)
        font = getattr(app, 'font_family', 'DejaVu Sans')
        self.mono = getattr(app, 'mono_family', font)
        c = self.colors
        # --- toolbar: run, what the canvas contains, actions
        bar = ttk.Frame(self, style='Card.TFrame', padding=(10, 8))
        bar.pack(fill='x', padx=8, pady=(6, 4))
        ttk.Button(bar, text='Run', style='Primary.TButton', command=app.run).pack(side='left')
        ttk.Button(bar, text='Stop', command=app.stop).pack(side='left', padx=(6, 8))
        ttk.Label(bar, text='Canvas contains', style='CardMuted.TLabel').pack(side='left', padx=(0, 6))
        self.contains = {}
        for key, label in (('inductor', 'Inductor / N-port'), ('array', 'Cap array'), ('gm', 'gm core')):
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(bar, text=label, variable=var, style='Card.TCheckbutton',
                            command=self.settings_changed).pack(side='left', padx=(0, 4))
            self.contains[key] = var
        self.loss_split = tk.BooleanVar(value=True)
        self.split_check = ttk.Checkbutton(bar, text='Module loss split', variable=self.loss_split, style='Card.TCheckbutton',
                                           command=self.settings_changed)
        self.split_check.pack(side='left', padx=(4, 6))
        self.mode_label = tk.StringVar()
        ttk.Label(bar, textvariable=self.mode_label, style='Badge.TLabel').pack(side='left', padx=(4, 0))
        ttk.Button(bar, text='Export CSV', style='Ghost.TButton', command=self.export).pack(side='right')
        ttk.Button(bar, text='Refine sweep at each f0', style='Ghost.TButton', command=self.narrow_sweep).pack(side='right', padx=2)
        self.setup_button = ttk.Button(bar, text='Roles & options ▾', style='Ghost.TButton', command=self.toggle_setup)
        self.setup_button.pack(side='right', padx=2)
        self.run_state = tk.StringVar()
        if hasattr(app, 'sim_label'):
            ttk.Label(bar, textvariable=app.sim_label, style='CardMuted.TLabel').pack(side='right', padx=6)
        # --- collapsible roles / options
        self.setup = ttk.Frame(self, style='Card.TFrame', padding=(10, 6))
        self.setup_open = False
        roles = ttk.Frame(self.setup, style='Card.TFrame')
        roles.pack(side='left', fill='x', expand=True)
        self.role_tree = ttk.Treeview(roles, columns=('cell', 'role'), show='tree headings', height=4, selectmode='browse')
        self.role_tree.heading('#0', text='INSTANCE')
        self.role_tree.heading('cell', text='CELL / DEVICE')
        self.role_tree.heading('role', text='TANK ROLE')
        self.role_tree.column('#0', width=90)
        self.role_tree.column('cell', width=280)
        self.role_tree.column('role', width=160)
        self.role_tree.pack(side='left', fill='x', expand=True)
        self.role_tree.bind('<<TreeviewSelect>>', self.role_selected)
        side = ttk.Frame(self.setup, style='Card.TFrame', padding=(12, 0, 0, 0))
        side.pack(side='left', fill='y')
        ttk.Label(side, text='Role of selected instance', style='CardMuted.TLabel').pack(anchor='w')
        self.role_var = tk.StringVar()
        self.role_box = ttk.Combobox(side, textvariable=self.role_var, values=ROLE_CHOICES, state='readonly', width=22)
        self.role_box.pack(fill='x', pady=(2, 4))
        self.role_box.bind('<<ComboboxSelected>>', lambda e: self.apply_role())
        ttk.Button(side, text='Auto-detect roles', command=self.auto_roles).pack(fill='x')
        row = ttk.Frame(side, style='Card.TFrame')
        row.pack(fill='x', pady=(8, 0))
        ttk.Label(row, text='gm reference freq.', style='CardMuted.TLabel').pack(side='left')
        self.ref_var = tk.StringVar(value='10M')
        ttk.Entry(row, textvariable=self.ref_var, width=8).pack(side='right')
        self.refine_label = tk.StringVar()
        rrow = ttk.Frame(side, style='Card.TFrame')
        rrow.pack(fill='x', pady=(8, 0))
        ttk.Label(rrow, textvariable=self.refine_label, style='CardMuted.TLabel').pack(side='left')
        ttk.Button(rrow, text='Clear f0 refinement', style='Ghost.TButton', command=self.clear_refinement).pack(side='right')
        ttk.Label(side, text='Optional port 2: give two pins the roles P2 / N2\n(e.g. the gates of a transformer-coupled core,\nor an output). Z21 and gm*Z21 then appear.',
                  style='CardMuted.TLabel', justify='left').pack(anchor='w', pady=(8, 0))
        self.note = tk.StringVar()
        ttk.Label(self, textvariable=self.note, wraplength=1100, style='Muted.TLabel', padding=(10, 0, 10, 2)).pack(fill='x')
        # --- KPI tiles for the selected point
        self.kpi = tk.Frame(self, bg=c['PANEL'])
        self.kpi.pack(fill='x', padx=8, pady=(2, 4))
        self.tiles = {}
        for key, caption in (('f0', 'f0'), ('f0lc', 'f0 · LC only'), ('rplc', 'Rp(LC)'), ('rpload', 'Rp(LC+loading)'),
                             ('margin', 'Startup margin'), ('gmrp', 'Loop gain gm·Z'), ('gm', 'gm / gds  (per side)')):
            tile = tk.Frame(self.kpi, bg=c['CARD'], highlightthickness=1, highlightbackground=c['LINE'], padx=12, pady=6)
            tile.pack(side='left', fill='both', expand=True, padx=(0, 6))
            tk.Label(tile, text=caption.upper(), bg=c['CARD'], fg=c['MUTED'], font=(font, 8, 'bold'), anchor='w').pack(fill='x')
            value = tk.Label(tile, text='—', bg=c['CARD'], fg=c['INK'], font=(font, 16, 'bold'), anchor='w')
            value.pack(fill='x')
            unit = tk.Label(tile, text='', bg=c['CARD'], fg=c['MUTED'], font=(font, 9), anchor='w')
            unit.pack(fill='x')
            self.tiles[key] = (value, unit)
        # --- resizable plot / table / loss areas
        # plots on the left, results table above the loss table on the right; all dividers draggable
        self.panes = ttk.Panedwindow(self, orient='horizontal')
        self.panes.pack(fill='both', expand=True, padx=8, pady=(0, 6))
        plotframe = ttk.Frame(self.panes)
        self.tables = ttk.Panedwindow(self.panes, orient='vertical')
        tableframe = ttk.Frame(self.tables)
        lossframe = ttk.Frame(self.tables)
        self.panes.add(plotframe, weight=3)
        self.panes.add(self.tables, weight=2)
        self.tables.add(tableframe, weight=3)
        self.tables.add(lossframe, weight=2)
        self._sashes_set = False
        self.panes.bind('<Configure>', self._initial_sashes, add='+')
        pbar = ttk.Frame(plotframe, padding=(2, 2))
        pbar.pack(fill='x')
        ttk.Label(pbar, text='PLOTS', style='Muted.TLabel').pack(side='left')
        ttk.Button(pbar, text='+ Add plot', style='Ghost.TButton', command=self.add_plot).pack(side='left', padx=6)
        ttk.Label(pbar, text='Pick a quantity and x axis per tab · click a curve to select its row',
                  style='Muted.TLabel').pack(side='left', padx=8)
        self.plotbook = ttk.Notebook(plotframe)
        self.plotbook.pack(fill='both', expand=True)
        self.panels = []
        self._plot_specs = None
        self.selected_key = None
        self.theme = 'neon'
        self.table = ResultsTable(tableframe, on_select=self.select, on_log=self.open_log)
        self.table.tree.configure(height=12)
        self.table.tree.bind('<ButtonRelease-1>', lambda e: self.after_idle(self.user_picked), add='+')
        self.table.tree.bind('<KeyRelease>', lambda e: self.after_idle(self.user_picked), add='+')
        self.table.pack(fill='both', expand=True)
        self.detail = tk.StringVar(value='Select a scan point to see the loss contributions at f0.')
        detail = ttk.Label(lossframe, textvariable=self.detail, wraplength=500, style='Muted.TLabel', padding=(2, 4))
        detail.pack(fill='x')
        lossframe.bind('<Configure>', lambda e: detail.configure(wraplength=max(200, e.width - 12)), add='+')
        area = ttk.Frame(lossframe)
        area.pack(fill='both', expand=True)
        cols = ('module', 'role', 'g', 'share', 'gneg', 'gm', 'gload')
        self.loss_tree = ttk.Treeview(area, columns=cols, show='headings', height=5)
        for key, label, width in (('module', 'MODULE', 130), ('role', 'ROLE', 105), ('g', 'G (mS)', 70),
                                  ('share', 'SHARE %', 70), ('gneg', 'G_NEG mS', 75),
                                  ('gm', 'gm@f0 mS', 75), ('gload', 'g_load mS', 75)):
            self.loss_tree.heading(key, text=label)
            self.loss_tree.column(key, width=width, minwidth=50, stretch=True, anchor='w' if key in ('module', 'role') else 'e')
        sy = ttk.Scrollbar(area, orient='vertical', command=self.loss_tree.yview)
        sy.pack(side='right', fill='y')
        self.loss_tree.configure(yscrollcommand=sy.set)
        self.loss_tree.pack(fill='both', expand=True)
        for tree in (self.loss_tree, self.table.tree, self.role_tree):
            tree.tag_configure('odd', background=c['PANEL'])

    def _initial_sashes(self, event=None):
        """First layout: plots get ~58 % of the width; the results table ~60 % of the right column."""
        w, h = self.panes.winfo_width(), self.panes.winfo_height()
        if self._sashes_set or w < 500 or h < 200:
            return
        self._sashes_set = True
        try:
            self.panes.sashpos(0, int(w * 0.58))
            self.tables.sashpos(0, int(h * 0.60))
        except tk.TclError:
            pass

    def toggle_setup(self, show=None):
        if show is None:
            self._setup_touched = True
        self.setup_open = (not self.setup_open) if show is None else show
        if self.setup_open:
            self.setup.pack(fill='x', padx=8, pady=(0, 4), before=self.kpi)
        else:
            self.setup.pack_forget()
        self.setup_button.configure(text='Roles & options ▴' if self.setup_open else 'Roles & options ▾')

    def set_tile(self, key, value, unit='', color=None):
        label, unit_label = self.tiles[key]
        label.configure(text=value, fg=color or self.colors['INK'])
        unit_label.configure(text=unit)

    # ------------------------------------------------------------ settings
    def page_settings(self):
        page = self.app.page()
        project = page.get('run_project') or page['project']
        return tank_scan.tank_settings(page, project), page, project

    def load_controls(self):
        settings, page, project = self.page_settings()
        for key, var in self.contains.items():
            var.set(bool(settings['contains'].get(key)))
        refine = (page['project'].get('settings') or {}).get('tank_refine') or []
        self.refine_label.set('f0 refinement: {} codes'.format(len(refine)) if refine else '')
        ref = page['tank'].get('gm_ref')
        self.ref_var.set('10M' if ref is None else ref)
        self.role_tree.delete(*self.role_tree.get_children())
        nodes = {n['id']: n for n in page['project'].get('instances', []) if n.get('enabled', True)}
        for ident, role in sorted(settings['roles'].items(), key=lambda x: (len(x[0]), x[0])):
            node = nodes.get(ident) or {}
            cell = node.get('cell') or node.get('kind') or ''
            if node.get('kind') == 'snp':
                cell = 'N-port ' + Path((node.get('touchstone') or {}).get('path', '')).name
            elif node.get('library'):
                cell = '{}/{}'.format(node['library'], node['cell'])
            self.role_tree.insert('', 'end', iid=ident, text=ident, values=(cell, tank_scan.ROLE_LABELS[role]),
                                  tags=('odd',) if len(self.role_tree.get_children()) % 2 else ())
        active = tank_scan.backend_mode(settings) == 'active'
        self.loss_split.set(settings['loss_split'] or active)
        self.split_check.configure(state='disabled' if active else 'normal')
        port2 = ' · PORT 2' if tank_scan.has_port2(project) else ''
        self.mode_label.set(('ACTIVE · gm split' if active else
                             'PASSIVE · resonance + loss' if settings['loss_split'] else 'PASSIVE · resonance only (fast)') + port2)

    def store_ref(self):
        page = self.app.page()
        page.setdefault('tank', {})['gm_ref'] = self.ref_var.get().strip()
        return page['tank']['gm_ref']

    def settings_changed(self):
        settings, page, project = self.page_settings()
        page['tank']['contains'] = {k: bool(v.get()) for k, v in self.contains.items()}
        if not page['tank']['contains'].get('gm'):
            page['tank']['loss_split'] = bool(self.loss_split.get())
        self.app.update_measurement_view()

    def role_selected(self, event=None):
        sel = self.role_tree.selection()
        if sel:
            self.role_var.set(self.role_tree.set(sel[0], 'role'))

    def apply_role(self):
        sel = self.role_tree.selection()
        if not sel:
            return
        settings, page, project = self.page_settings()
        page['tank']['roles'][sel[0]] = ROLE_FROM_LABEL[self.role_var.get()]
        self.app.update_measurement_view()

    def auto_roles(self):
        page = self.app.page()
        page.setdefault('tank', {}).pop('roles', None)
        page['tank'].pop('contains', None)
        self.app.update_measurement_view()

    def narrow_sweep(self):
        """Add dense sweep points around each code's own f0 (the base sweep is kept)."""
        centers = tank_scan.refine_centers(self.data.get('rows', []))
        settings = self.app.project['settings']
        if not centers:
            self.app.status.set('Run a tank scan first; no resolved f0 to refine around.')
            return
        settings['tank_refine'] = [float(f) for f in centers]
        try:
            from .spectrum import simulation_grid
            n = len(simulation_grid(settings))
        except ValueError as ex:
            settings.pop('tank_refine', None)
            self.app.status.set(str(ex))
            return
        self.refine_label.set('f0 refinement: {} codes, {} sweep points'.format(len(centers), n))
        self.app.status.set('Sweep refined around {} f0 values ({:.4g}-{:.4g} GHz): {} points in total. Run again for '
                            'f0 brackets of about 0.1 %.'.format(len(centers), centers[0] / 1e9, centers[-1] / 1e9, n))

    def clear_refinement(self):
        self.app.project['settings'].pop('tank_refine', None)
        self.refine_label.set('')
        self.app.status.set('f0 refinement cleared; the next run uses the base sweep only.')

    # ------------------------------------------------------------- results
    def set_data(self, data, mode='cartesian', theme='neon'):
        self.data = data
        self.mode = mode
        self.load_controls()
        rows = display_rows(data)
        self.rows = rows
        issues = data.get('issues') or []
        self.note.set(('Check roles: ' + ' '.join(issues) + ' ') if issues else data.get('message', ''))
        names = data.get('names', [])
        ident = ['point'] if rows and 'point' in rows[0] else ['code']
        two = any(r.get('z21') for r in data.get('rows', []))
        keys = [k for k, _ in COLUMNS if not (data.get('mode') == 'passive' and k in PASSIVE_HIDE) and (two or k not in PORT2_ONLY)]
        self.table.fixed_columns = ident + names + keys
        self.table.LABELS.update({k: v for k, v in COLUMNS})
        self.table.set_rows(rows)
        self.theme = theme
        self.prepare_curves()
        self.sync_plots()
        if not rows or issues:
            self.toggle_setup(True)
        elif not getattr(self, '_setup_touched', False):
            self.toggle_setup(False)
        children = self.table.tree.get_children()
        if children:
            # The first row fills the KPI tiles; curves are highlighted only when the user picks a row or a curve.
            self._auto_key = self.ident(self.table.item_rows.get(children[0], rows[0]))
            self.table.tree.selection_set(children[0])
            self.select(self.table.item_rows.get(children[0], rows[0]) if hasattr(self.table, 'item_rows') else rows[0])
        else:
            self.select(None)

    # ------------------------------------------------------- plot manager
    def ident(self, row):
        return row.get('point', row.get('code'))

    def prepare_curves(self):
        """Curve labels and the scan-point order used for gradient colors."""
        names = self.data.get('names', [])
        rows = self.data.get('rows', [])
        varying = [n for n in names if len({r.get(n) for r in rows}) > 1]
        self.labels = {}
        for r in rows:
            key = self.ident(r)
            if varying:
                tag = '/'.join(str(r[n]) for n in varying)
                long = ', '.join('{}={}'.format(n, r[n]) for n in varying)
            else:
                tag = str(key)
                long = '{} {}'.format('point' if 'point' in r else 'code', key)
            self.labels[key] = (long, tag)
        self.axis_choices = names + (['Scan point'] if rows and 'point' in rows[0] else ['code'])
        self.default_axis = next((n for n in varying), self.axis_choices[0] if self.axis_choices else 'code')

    def log_sweep(self):
        project = self.page_settings()[2]
        return str((project.get('settings') or {}).get('simulation_sweep', '')).lower() == 'log'

    def available(self, needs):
        if needs == 'port2':
            return any(r.get('z21') for r in self.data.get('rows', [])) or tank_scan.has_port2(self.page_settings()[2])
        settings = tank_scan.tank_settings(self.app.page(), self.page_settings()[2])
        active = tank_scan.backend_mode(settings) == 'active'
        return needs is None or (needs == 'active' and active) or (needs == 'split' and (active or settings['loss_split']))

    def default_specs(self):
        two = [{'q': 'z21_abs'}] if any(r.get('z21') for r in self.data.get('rows', [])) else []
        if self.data.get('mode') == 'active':
            return [{'q': 'f0'}, {'q': 'margin'}, {'q': 'gain'}, {'q': 'z_abs'}] + two + [{'q': 't_abs'}, {'q': 'share'}]
        return [{'q': 'f0'}, {'q': 'z_abs'}] + two + [{'q': 'rpload'}, {'q': 'share'}]

    def sync_plots(self):
        page = self.app.page()
        specs = page.setdefault('tank', {}).get('plots')
        if not specs:
            # Defaults depend on the data (gm core, port 2); keep them only once results exist.
            specs = self.default_specs()
            if self.data.get('rows'):
                page['tank']['plots'] = specs
        if specs is not self._plot_specs:
            # Another page (or a restored workbook): reuse the tabs, add or drop the difference.
            while len(self.panels) > len(specs):
                panel = self.panels.pop()
                self.plotbook.forget(panel)
                panel.destroy()
            while len(self.panels) < len(specs):
                panel = PlotPanel(self, specs[len(self.panels)])
                self.panels.append(panel)
                self.plotbook.add(panel, text=panel.title())
            for panel, spec in zip(self.panels, specs):
                panel.spec = spec
                panel.only.set(bool(spec.get('only')))
                self.plotbook.tab(panel, text=panel.title())
            self._plot_specs = specs
        for panel in self.panels:
            panel.refresh()

    def add_plot(self):
        page = self.app.page()
        specs = page.setdefault('tank', {}).setdefault('plots', self.default_specs())
        if specs is not self._plot_specs:
            self.sync_plots()
        spec = {'q': 'z_abs'}
        specs.append(spec)
        panel = PlotPanel(self, spec)
        self.panels.append(panel)
        self.plotbook.add(panel, text=panel.title())
        panel.refresh()
        self.plotbook.select(panel)

    def remove_plot(self, panel):
        specs = self.app.page().setdefault('tank', {}).get('plots') or []
        if len(self.panels) <= 1:
            self.app.status.set('Keep at least one plot.')
            return
        specs[:] = [x for x in specs if x is not panel.spec]
        self.panels.remove(panel)
        self.plotbook.forget(panel)
        panel.destroy()

    def set_theme(self, theme):
        self.theme = theme
        for panel in self.panels:
            panel.set_theme(theme)

    def user_picked(self, event=None):
        """A click or key in the results table: highlight that row's curves from now on."""
        self._auto_key = None
        row = self.table.selected_row()
        if row is not None and self.ident(row) != self.selected_key:
            self.select(row)

    def pick_point(self, key):
        self._auto_key = None
        for iid, row in getattr(self.table, 'item_rows', {}).items():
            if self.ident(row) == key:
                self.table.tree.selection_set(iid)
                self.table.tree.see(iid)
                return
        row = next((r for r in self.rows if self.ident(r) == key), None)
        if row is not None:
            self.select(row)

    def _raw(self, row):
        key = row.get('point', row.get('code'))
        return next((r['tank'] for r in self.data['rows'] if r.get('point', r.get('code')) == key), {})

    def refresh_tiles(self):
        self.fill_tiles(getattr(self, '_tile_data', {}))

    def fill_tiles(self, r):
        self._tile_data = r

        def fmt(v, scale=1, digits=4):
            return '—' if v is None else '{:.{}g}'.format(v * scale, digits)
        c = self.colors
        self.set_tile('f0', fmt(r.get('f0_Hz'), 1e-9, 5), 'GHz')
        self.set_tile('f0lc', fmt(r.get('f0_LC_Hz'), 1e-9, 5), 'GHz  (core C removed)' if r.get('f0_LC_Hz') else '')
        self.set_tile('rplc', fmt(r.get('Rp_LC_ohm')), 'Ω  inductor + array')
        self.set_tile('rpload', fmt(r.get('Rp_loaded_ohm')), 'Ω  incl. core & other loading')
        m = r.get('margin')
        self.set_tile('margin', fmt(m, 1, 3), ('starts (> 1)' if m > 1 else 'does NOT start') if m is not None else 'needs gm core',
                      None if m is None else (c['GOOD'] if m > 1 else c['BAD']))
        kind = r.get('gain_kind')
        self.set_tile('gmrp', fmt(r.get('gain'), 1, 3),
                      ('gm × Z21  (gates on port 2)' if kind == 'gm*Z21' else 'gm × Rp  (gates on P/N)') if r.get('gain') is not None
                      else r.get('gain_reason', ''))
        if r.get('gm_ref_S') is not None:
            self.set_tile('gm', '{} / {}'.format(fmt(r['gm_ref_S'], 1e3, 3), fmt(r['gds_ref_S'], 1e3, 3)),
                          'mS @ {:.3g} MHz'.format(r['f_ref_Hz'] / 1e6))
        else:
            self.set_tile('gm', '—', '')

    def select(self, row):
        self.loss_tree.delete(*self.loss_tree.get_children())
        key = None if row is None else self.ident(row)
        self.selected_key = None if key == getattr(self, '_auto_key', None) else key
        for panel in self.panels:
            panel.highlight()
        if row is None:
            self.fill_tiles({})
            return
        r = self._raw(row)
        self.fill_tiles(r if r.get('available') else {})
        if not r.get('available'):
            self.detail.set('Unavailable: ' + r.get('reason', ''))
            return
        if r.get('partial'):
            self.detail.set('f0 {:.6g} GHz, Rp = Re(Z) {:.6g} ohm. {}'.format(r['f0_Hz'] / 1e9, r['Z_real_ohm'], r.get('reason', '')))
            return
        text = 'At f0 = {:.6g} GHz (bracket {:.6g}-{:.6g} GHz): G_loss {:.4g} mS = LC {:.4g} + other {:.4g} + core loading {:.4g} mS'.format(
            r['f0_Hz'] / 1e9, r['bracket_Hz'][0] / 1e9, r['bracket_Hz'][1] / 1e9, r['G_loss_S'] * 1e3,
            r['G_LC_S'] * 1e3, r['G_other_S'] * 1e3, r['G_core_load_S'] * 1e3)
        if r.get('margin') is not None:
            text += '; G_neg {:.4g} mS, margin {:.4g}, gm {:.4g} mS @ {:.4g} MHz.'.format(
                r['G_neg_S'] * 1e3, r['margin'], r['gm_ref_S'] * 1e3, r['f_ref_Hz'] / 1e6)
            if r.get('gain_kind') == 'gm*Z21' and r.get('Z21_off_ohm'):
                text += ' Core gates on port 2: loop gain gm*Z21 = {:.4g} (Re Z21 {:.4g} ohm, V_gate/V_drain {:.3g}).'.format(
                    r['gain'], r['Z21_off_ohm'][0], r.get('gate_ratio') or float('nan'))
            elif r.get('gain') is not None:
                text += ' Core gates on P/N: loop gain gm*Rp = {:.4g}.'.format(r['gain'])
        text += ' Module sum check {:.1e}; Re(Y) vs SP {:.2e} S.'.format(r.get('module_sum_error', 0), r.get('net_check_S', 0))
        if not r.get('shares_valid'):
            text += ' A passive module shows negative loss (coupling transfer); shares are indicative only.'
        self.detail.set(text)

        def ms(v):
            return '' if v is None else '{:.5g}'.format(v * 1e3)
        for n, c in enumerate(sorted(r['contributions'], key=lambda c: -c['G_S'])):
            self.loss_tree.insert('', 'end', tags=('odd',) if n % 2 else (), values=(c['module'], tank_scan.ROLE_LABELS.get(c['role'], c['role']), ms(c['G_S']),
                                                     '' if c['share_pct'] is None else '{:.4g}'.format(c['share_pct']),
                                                     ms(c.get('G_neg_S')), ms(c.get('gm_S')), ms(c.get('gload_S'))))

    def open_log(self, row):
        from .pointlogs import open_row_log
        open_row_log(self.app, row)

    def export(self):
        if not self.rows:
            return
        out = []
        for row in self.table.filtered or self.rows:
            r = self._raw(row)
            base = dict(row)
            for c in r.get('contributions') or [{}]:
                item = dict(base)
                item.update(module=c.get('module', ''), module_role=c.get('role', ''), module_G_S=c.get('G_S'),
                            module_share_pct=c.get('share_pct'), module_G_neg_S=c.get('G_neg_S'),
                            module_gm_S=c.get('gm_S'), module_gload_S=c.get('gload_S'))
                out.append(item)
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.csv', initialfile='tank_scan.csv',
                                            filetypes=[('CSV', '*.csv')])
        if not path:
            return
        if Path(path).exists():
            shutil.copy2(path, path + datetime.now().strftime('.bak-%Y%m%d-%H%M%S'))
        fields = list(dict.fromkeys(k for item in out for k in item))
        with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(out)
        self.app.status.set('Exported {} tank scan rows.'.format(len(out)))
