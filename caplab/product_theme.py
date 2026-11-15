"""Product-side theme helpers on top of the shared RF-FIELDWORK kit.

* ``apply_theme`` applies the kit (dark instrument glass, product 'cap') and a
  font fallback for Tk builds that report lower-case family names.
* Tank Scan Lab adds a Dark / Light switch.  Dark is the kit palette unchanged;
  Light is derived here (the kit colours are never modified) and re-styles the
  same ttk styles, then walks classic Tk widgets to swap palette colours live.
"""
from tkinter import font as tkfont, ttk

from . import fieldwork_tk as _fw

ACCENT = _fw.accent('cap')

# Dark = the shared kit palette.
DARK = {
    'BG': _fw.BG, 'PANEL': _fw.PANEL, 'CARD': _fw.PANEL, 'RAISED': _fw.RAISED, 'LINE': _fw.LINE,
    'HOVER': '#2A302C', 'SELECT': _fw._mix(_fw.BG, ACCENT, .35), 'INK': _fw.TEXT, 'MUTED': _fw.DIM,
    'FAINT': _fw.MUTED, 'PLOT_BG': _fw.PLOT_BG, 'ACCENT': ACCENT, 'ACCENT_TEXT': ACCENT,
    'ON_ACCENT': _fw.INK, 'GOOD': _fw.OK, 'BAD': _fw.ERR, 'WARN': _fw.WARN, 'LOG': '#090D0B',
}
# Light = the website's grey instrument chassis; the cyan fill stays, accent text is darkened for contrast.
LIGHT = {
    'BG': '#E9ECEA', 'PANEL': '#F4F6F5', 'CARD': '#F4F6F5', 'RAISED': '#FFFFFF', 'LINE': '#C8CFCB',
    'HOVER': '#E1E6E3', 'SELECT': '#CBEFF2', 'INK': '#18201C', 'MUTED': '#55605A',
    'FAINT': '#8E9893', 'PLOT_BG': '#FEFEFE', 'ACCENT': ACCENT, 'ACCENT_TEXT': '#0B7F8B',
    'ON_ACCENT': _fw.INK, 'GOOD': '#2F8F2A', 'BAD': '#C9372C', 'WARN': '#9A6A00', 'LOG': '#F7F9F8',
}
PALETTES = {'dark': DARK, 'light': LIGHT}
# Canvas plot theme per UI theme (see plotview.THEMES).
PLOT_THEME = {'dark': 'neon', 'light': 'light'}
# Fixed colours used directly by older widgets, and their light counterparts.
EXTRA = {'#34576a': LIGHT['SELECT'], '#090d11': LIGHT['LOG']}


def apply_theme(root, fw=_fw):
    fw.apply(root, product='cap')
    have = {name.lower(): name for name in tkfont.families(root)}
    family = next((have[name.lower()] for name in ('Inter', 'Noto Sans', 'Liberation Sans', 'DejaVu Sans') if name.lower() in have), None)
    if family is None:
        return
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont', 'TkCaptionFont', 'TkSmallCaptionFont', 'TkTooltipFont'):
        try:
            tkfont.nametofont(name).configure(family=family)
        except Exception:
            pass
    for key, value in root.fw_fonts.items():
        if key != 'mono':
            root.fw_fonts[key] = (family,) + value[1:]
    style = ttk.Style(root)
    style.configure('.', font=(family, 10))
    style.configure('Primary.TButton', font=(family, 10, 'bold'))
    style.configure('Title.TLabel', font=(family, 14, 'bold'))
    style.configure('Section.TLabel', font=(family, 9, 'bold'))
    style.configure('Treeview.Heading', font=(family, 9, 'bold'))


def palette(name='dark'):
    return dict(PALETTES.get(name, DARK))


def _restyle(root, c):
    """The kit's ttk styles with another palette (used for the light theme)."""
    st = ttk.Style(root)
    acc = c['ACCENT']
    root.configure(bg=c['BG'])
    for pat, val in (('*Background', c['BG']), ('*Foreground', c['INK']), ('*activeBackground', c['RAISED']),
                     ('*activeForeground', c['INK']), ('*selectBackground', c['SELECT']), ('*selectForeground', c['INK']),
                     ('*Listbox.background', c['RAISED']), ('*Text.background', c['RAISED']),
                     ('*Entry.background', c['RAISED']), ('*Canvas.background', c['PLOT_BG']),
                     ('*Menu.background', c['PANEL']), ('*troughColor', c['BG']),
                     ('*TCombobox*Listbox.background', c['RAISED']), ('*TCombobox*Listbox.foreground', c['INK']),
                     ('*TCombobox*Listbox.selectBackground', c['SELECT'])):
        root.option_add(pat, val)
    st.configure('.', background=c['BG'], foreground=c['INK'], fieldbackground=c['RAISED'], bordercolor=c['LINE'],
                 lightcolor=c['LINE'], darkcolor=c['LINE'], troughcolor=c['BG'], focuscolor=acc,
                 selectbackground=c['SELECT'], selectforeground=c['INK'], insertcolor=c['ACCENT_TEXT'])
    st.map('.', foreground=[('disabled', c['FAINT'])])
    st.configure('TFrame', background=c['BG'])
    st.configure('Panel.TFrame', background=c['PANEL'])
    st.configure('TLabel', background=c['BG'], foreground=c['INK'])
    st.configure('Panel.TLabel', background=c['PANEL'])
    st.configure('Dim.TLabel', foreground=c['MUTED'])
    st.configure('PanelDim.TLabel', background=c['PANEL'], foreground=c['MUTED'])
    st.configure('Section.TLabel', background=c['PANEL'], foreground=c['MUTED'])
    st.configure('Muted.TLabel', foreground=c['MUTED'])
    st.configure('TLabelframe', background=c['PANEL'], bordercolor=c['LINE'])
    st.configure('TLabelframe.Label', background=c['PANEL'], foreground=c['MUTED'])
    st.configure('TButton', background=c['RAISED'], foreground=c['INK'], bordercolor=c['LINE'], lightcolor=c['RAISED'],
                 darkcolor=c['RAISED'])
    st.map('TButton', background=[('disabled', c['BG']), ('pressed', c['LINE']), ('active', c['HOVER'])],
           foreground=[('disabled', c['FAINT'])], bordercolor=[('focus', acc)])
    st.configure('Primary.TButton', background=acc, foreground=c['ON_ACCENT'], bordercolor=acc, lightcolor=acc, darkcolor=acc)
    st.map('Primary.TButton', background=[('disabled', _fw._mix(c['BG'], acc, .25)), ('pressed', _fw._mix(acc, '#000000', .15)),
                                          ('active', _fw._mix(acc, '#FFFFFF', .2))],
           foreground=[('disabled', c['FAINT'])], bordercolor=[('disabled', _fw._mix(c['BG'], acc, .25))])
    st.configure('Ghost.TButton', background=c['BG'], foreground=c['MUTED'], bordercolor=c['BG'], lightcolor=c['BG'], darkcolor=c['BG'])
    st.map('Ghost.TButton', foreground=[('active', c['INK']), ('disabled', c['FAINT'])], background=[('active', c['PANEL'])])
    st.configure('Danger.TButton', foreground=c['BAD'])
    for w in ('TEntry', 'TCombobox', 'TSpinbox'):
        st.configure(w, fieldbackground=c['RAISED'], background=c['RAISED'], foreground=c['INK'], bordercolor=c['LINE'],
                     lightcolor=c['RAISED'], darkcolor=c['RAISED'], arrowcolor=c['MUTED'])
        st.map(w, bordercolor=[('focus', acc)], fieldbackground=[('readonly', c['RAISED']), ('disabled', c['BG'])],
               foreground=[('disabled', c['FAINT'])], arrowcolor=[('active', c['ACCENT_TEXT'])])
    for w in ('TCheckbutton', 'TRadiobutton'):
        st.configure(w, background=c['BG'], foreground=c['INK'], indicatorbackground=c['RAISED'],
                     indicatorforeground=c['ACCENT_TEXT'], focuscolor=c['BG'])
        st.map(w, indicatorbackground=[('selected', c['RAISED'])],
               indicatorcolor=[('selected', c['ACCENT_TEXT']), ('!selected', c['RAISED'])],
               background=[('active', c['BG'])], foreground=[('disabled', c['FAINT'])])
    st.configure('Panel.TCheckbutton', background=c['PANEL'])
    st.configure('Panel.TRadiobutton', background=c['PANEL'])
    st.configure('TNotebook', background=c['BG'], bordercolor=c['LINE'])
    st.configure('TNotebook.Tab', background=c['BG'], foreground=c['MUTED'], bordercolor=c['BG'], lightcolor=c['BG'])
    st.map('TNotebook.Tab', background=[('selected', c['PANEL'])], foreground=[('selected', c['INK']), ('active', c['INK'])],
           lightcolor=[('selected', acc)], bordercolor=[('selected', c['LINE'])])
    st.configure('Treeview', background=c['RAISED'], fieldbackground=c['RAISED'], foreground=c['INK'], bordercolor=c['LINE'])
    st.map('Treeview', background=[('selected', c['SELECT'])], foreground=[('selected', c['INK'])])
    st.configure('Treeview.Heading', background=c['PANEL'], foreground=c['MUTED'], bordercolor=c['LINE'],
                 lightcolor=c['PANEL'], darkcolor=c['PANEL'])
    st.map('Treeview.Heading', background=[('active', c['HOVER'])])
    st.configure('TScrollbar', background=c['HOVER'], troughcolor=c['BG'], bordercolor=c['BG'], arrowcolor=c['MUTED'],
                 lightcolor=c['HOVER'], darkcolor=c['HOVER'])
    st.map('TScrollbar', background=[('active', c['LINE'])])
    st.configure('Horizontal.TProgressbar', background=acc, troughcolor=c['RAISED'], bordercolor=c['BG'],
                 lightcolor=acc, darkcolor=acc)
    st.configure('TScale', background=c['BG'], troughcolor=c['RAISED'])
    st.configure('TSeparator', background=c['LINE'])
    st.configure('TPanedwindow', background=c['LINE'])
    st.configure('Sash', background=c['LINE'])


def apply_ui_palette(root, name):
    """Style the whole application with the dark (kit) or light palette."""
    apply_theme(root)
    c = PALETTES.get(name, DARK)
    if c is LIGHT:
        _restyle(root, c)
    style = ttk.Style(root)
    style.configure('Muted.TLabel', foreground=c['MUTED'])
    style.map('TCombobox', selectbackground=[('readonly', c['RAISED'])], selectforeground=[('readonly', c['INK'])])
    return c


def color_map(old, new):
    """Old-palette colour -> new-palette colour (lower-case keys) for live recolouring."""
    out = {}
    for key in ('BG', 'PANEL', 'RAISED', 'LINE', 'HOVER', 'SELECT', 'INK', 'MUTED', 'FAINT', 'PLOT_BG', 'LOG',
                'GOOD', 'BAD', 'WARN', 'ACCENT_TEXT'):
        out.setdefault(old[key].lower(), new[key])
    extra = EXTRA if old is DARK else {b.lower(): a for a, b in EXTRA.items()}
    for a, b in extra.items():
        out.setdefault(a.lower(), b)
    return out


_TK_OPTIONS = ('background', 'foreground', 'highlightbackground', 'highlightcolor', 'insertbackground',
               'selectbackground', 'selectforeground', 'activebackground', 'activeforeground', 'disabledforeground',
               'troughcolor', 'readonlybackground')


def recolor(widget, mapping, skip=()):
    """Walk classic Tk widgets and swap palette colours (ttk widgets follow their styles)."""
    if widget in skip:
        return
    cls = widget.winfo_class()
    if not cls.startswith('T') or cls in ('Toplevel', 'Text'):
        for opt in _TK_OPTIONS:
            try:
                value = str(widget.cget(opt)).lower()
            except Exception:
                continue
            if value in mapping:
                try:
                    widget.configure(**{opt: mapping[value]})
                except Exception:
                    pass
    if cls == 'Treeview':
        try:
            tags = widget.tk.splitlist(widget.tk.call(widget, 'tag', 'names'))
        except Exception:
            tags = ()
        for tag in tags:
            for opt in ('background', 'foreground'):
                value = str(widget.tag_configure(tag, opt) or '').lower()
                if value in mapping:
                    widget.tag_configure(tag, **{opt: mapping[value]})
    for child in widget.winfo_children():
        recolor(child, mapping, skip)
