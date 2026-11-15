"""Multi-curve plot for the tank plot manager (anti-aliased through caplab.render).

Every curve gets its own color (scan-point order), a marker with a short label
(the code value at f0) and, in the dark theme, a neon glow.  Clicking a curve
highlights it and dims the rest; the key is reported so the results table can
follow.  Hovering reads out x / y of the nearest point.
"""
import math
import tkinter as tk

from .plotview import THEMES, CQPlot, series_color, tooltip
from .render import Painter, mix


def nice_ticks(lo, hi, count=5):
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / count
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.ceil(lo / step - 1e-9) * step
    out, v = [], start
    while v <= hi + 1e-9 * span:
        out.append(0.0 if abs(v) < 1e-12 * step else v)
        v += step
    return out


def log_ticks(lo, hi):
    out = []
    for e in range(int(math.floor(math.log10(lo))), int(math.ceil(math.log10(hi))) + 1):
        for m in (1, 2, 5):
            v = m * 10 ** e
            if lo <= v <= hi:
                out.append(v)
    return out if len(out) >= 2 else nice_ticks(lo, hi, 6)


class FreqPlot(tk.Canvas):
    """curves: list of dict(key, label, x, y, marker=(x, y) | None, tag=short label, dots=bool)."""

    def __init__(self, parent, on_pick=None, **kwargs):
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('height', 300)
        super().__init__(parent, **kwargs)
        self.on_pick = on_pick
        self.theme = 'neon'
        self.curves = []
        self.title = ''
        self.xlabel = ''
        self.unit = ''
        self.palette = 'distinct'
        self.selected = None
        self.only_selected = False
        self.vline = None
        self.logx = False
        self.empty_message = 'No data.'
        self.pending = None
        self.hits = []
        self.bind('<Configure>', lambda e: self.schedule_draw())
        self.bind('<Button-1>', self.click)
        self.bind('<Motion>', self.hover)
        self.bind('<Leave>', lambda e: self.delete('tooltip'))

    @property
    def font(self):
        return CQPlot.FONT

    def set_theme(self, theme):
        self.theme = theme.lower() if theme.lower() in THEMES else 'neon'
        self.configure(background=THEMES[self.theme]['bg'])
        self.draw()

    def set_curves(self, curves, title='', xlabel='', unit='', palette='distinct', empty_message=None):
        self.curves = curves
        self.title, self.xlabel, self.unit, self.palette = title, xlabel, unit, palette
        if empty_message:
            self.empty_message = empty_message
        self.draw()

    def set_selected(self, key, vline=None):
        self.selected = key
        self.vline = vline
        self.draw()

    def schedule_draw(self):
        if self.pending:
            self.after_cancel(self.pending)
        self.pending = self.after(60, self.draw)

    def color(self, index, count):
        return series_color(THEMES[self.theme], index, count)

    def curves_visible(self):
        curves = [c for c in self.curves if c['x']]
        if self.only_selected and self.selected is not None:
            curves = [c for c in curves if c['key'] == self.selected] or curves
        return curves

    def draw(self):
        self.pending = None
        self.delete('all')
        self.hits = []
        w, h = self.winfo_width(), self.winfo_height()
        theme = THEMES[self.theme]
        if w < 60 or h < 60:
            return
        F = self.font
        neon = bool(theme.get('glow'))
        p = Painter(self, theme['bg'], CQPlot.antialias)
        p.text(w / 2, 18, self.title, theme['ink'], (F, 12, 'bold'))
        curves = self.curves_visible()
        pts = [(x, y) for c in curves for x, y in zip(c['x'], c['y']) if y is not None and math.isfinite(y)]
        if not pts:
            p.text(w / 2, h / 2, self.empty_message, theme['muted'], (F, 11))
            p.flush()
            return
        logx = self.logx and min(q[0] for q in pts) > 0
        xmin, xmax = min(q[0] for q in pts), max(q[0] for q in pts)
        ymin, ymax = min(q[1] for q in pts), max(q[1] for q in pts)
        if xmax == xmin:   # single frequency: widen multiplicatively so a log axis stays positive
            xmin, xmax = (xmin / 1.25, xmax * 1.25) if xmin > 0 else (xmin - .5, xmax + .5)
        yr = ymax - ymin
        if yr <= max(abs(ymin), abs(ymax)) * 1e-10:
            yr = max(abs(ymax) * .1, 1e-9)
        ymin, ymax = ymin - .06 * yr, ymax + .16 * yr  # head room for the code labels
        x0, x1, y0, y1 = 70, w - 20, 44, h - 50
        lx = math.log10 if logx else (lambda v: v)
        lmin, lmax = lx(xmin), lx(xmax)

        def X(v):
            return x0 + (lx(v) - lmin) / (lmax - lmin) * (x1 - x0)

        def Y(v):
            return y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)
        for t in nice_ticks(ymin, ymax):
            p.line([x0, Y(t), x1, Y(t)], theme['grid'], 1)
            p.text(x0 - 8, Y(t), '{:.4g}'.format(t), theme['muted'], (F, 10), 'e')
        for t in (log_ticks(xmin, xmax) if logx else nice_ticks(xmin, xmax, 6)):
            p.line([X(t), y0, X(t), y1], theme['grid'], 1)
            p.text(X(t), y1 + 15, '{:.4g}'.format(t), theme['muted'], (F, 10))
        p.line([x0, y0, x0, y1, x1, y1], theme.get('axis', theme['ink']), 1.2)
        p.text((x0 + x1) / 2, h - 15, self.xlabel, theme['ink'], (F, 11))
        if self.unit:
            p.text(x0 - 8, y0 - 14, self.unit, theme['muted'], (F, 10), 'e')
        if self.vline is not None and xmin <= self.vline <= xmax:
            p.line([X(self.vline), y0, X(self.vline), y1], theme['ink'], 1, dash=(4, 3))
        n_all = len(self.curves)
        step = max(1, int(math.ceil(n_all / 14.0)))  # at most ~14 code labels
        placed = []
        sel = self.selected if any(c['key'] == self.selected for c in curves) else None
        order = sorted(range(len(curves)), key=lambda i: curves[i]['key'] == sel)  # highlighted on top
        for i in order:
            c = curves[i]
            index = self.curves.index(c)
            chosen = sel is not None and c['key'] == sel
            dim = sel is not None and not chosen
            color = self.color(index, n_all)
            if dim:
                color = mix(color, theme['bg'], .75)
            glow = 0 if (dim or not neon) else (2 if chosen else 1)
            width = 3.2 if chosen else (1.3 if dim else 1.9)
            seg = []
            for x, y in zip(c['x'], c['y']):
                if y is None or not math.isfinite(y) or (logx and x <= 0):
                    if len(seg) >= 4:
                        p.line(seg, color, width, glow=glow)
                    seg = []
                    continue
                seg += [X(x), Y(y)]
                self.hits.append((X(x), Y(y), i, x, y))
            if len(seg) >= 4:
                p.line(seg, color, width, glow=glow)
            elif len(seg) == 2:
                p.dot(seg[0], seg[1], 3, color, glow=glow)
            if c.get('dots'):
                for x, y in zip(c['x'], c['y']):
                    if y is not None and math.isfinite(y):
                        p.dot(X(x), Y(y), 4 if chosen else 2.6, color, glow=glow)
            m = c.get('marker')
            if m and m[1] is not None and math.isfinite(m[1]) and xmin <= m[0] <= xmax:
                mx, my = X(m[0]), Y(m[1])
                p.dot(mx, my, 5 if chosen else 3.6, color, outline=theme['ink'] if chosen else None, glow=glow)
                if c.get('tag') and (chosen or (not dim and (index % step == 0 or index == n_all - 1))):
                    half = 4 + 4 * len(c['tag'])
                    ly = my - 11
                    for _ in range(4):  # lift the label above ones already placed
                        if not any(abs(mx - px) < half + ph and abs(ly - py) < 14 for px, py, ph in placed):
                            break
                        ly -= 14
                    else:
                        if not chosen:
                            continue
                    placed.append((mx, ly, half))
                    p.text(mx, ly, c['tag'], color, (F, 11 if chosen else 10, 'bold'), 's', glow=glow)
        if self.palette == 'categorical':
            x = x0 + 6
            for i, c in enumerate(self.curves[:8]):
                color = self.color(i, n_all)
                p.line([x, 34, x + 16, 34], color, 3, glow=1 if neon else 0)
                p.text(x + 20, 34, c['label'], theme['ink'], (F, 9), 'w')
                x += 20 + p.measure(c['label'], (F, 9))[0] + 14
        elif n_all > 1:
            p.text(x1, 32, 'click a curve to highlight it  ·  hover for x / y', theme['muted'], (F, 9), 'e')
        p.flush()

    def nearest(self, ex, ey, radius=10):
        best = None
        for x, y, i, vx, vy in self.hits:
            d = (x - ex) ** 2 + (y - ey) ** 2
            if d <= radius ** 2 and (best is None or d < best[0]):
                best = (d, x, y, i, vx, vy)
        return best

    def click(self, event):
        hit = self.nearest(event.x, event.y)
        if hit is None:
            if self.selected is not None and self.on_pick is None:
                self.set_selected(None, self.vline)
            return
        key = self.curves_visible()[hit[3]]['key']
        if self.on_pick:
            self.on_pick(key)
        else:
            self.set_selected(None if key == self.selected else key, self.vline)

    def hover(self, event):
        self.delete('tooltip')
        hit = self.nearest(event.x, event.y, 12)
        if hit is None:
            return
        _, x, y, i, vx, vy = hit
        c = self.curves_visible()[i]
        text = '{}\n{} = {:.6g}\ny = {:.6g} {}'.format(c['label'], self.xlabel.split(' (')[0] or 'x', vx, vy, self.unit)
        tooltip(self, THEMES[self.theme], self.font, x, y, text)
