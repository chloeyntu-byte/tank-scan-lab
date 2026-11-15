"""Anti-aliased plot rendering for the Tk canvas plots.

A Painter records lines, dots, rectangles and texts during a plot's draw() and
then either renders them with PIL (2x supersampling, optional neon glow) into a
single canvas image, or, when PIL/ImageTk is unavailable, issues ordinary canvas
items.  Plots keep their own hit lists for hover and click, so interaction does
not depend on canvas items.
"""
import math
import os

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk
    HAVE_PIL = True
except Exception:  # pragma: no cover - depends on the runtime
    HAVE_PIL = False

SCALE = 2
_FONT_FILES = {
    'normal': ['/usr/share/fonts/open-sans/OpenSans-Regular.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf'],
    'semibold': ['/usr/share/fonts/open-sans/OpenSans-Semibold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'],
    'bold': ['/usr/share/fonts/open-sans/OpenSans-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'],
}
_font_cache = {}
_ANCHOR = {'center': 'mm', 'n': 'mt', 's': 'mb', 'e': 'rm', 'w': 'lm', 'nw': 'lt', 'ne': 'rt', 'sw': 'lb', 'se': 'rb'}
PIXELS_PER_POINT = 1.2  # matches tk scaling set by the app


def _font(size, weight, scale):
    key = (size, weight, scale)
    if key not in _font_cache:
        path = next((p for p in _FONT_FILES.get(weight, _FONT_FILES['normal']) if os.path.isfile(p)), None)
        px = max(6, int(round(size * PIXELS_PER_POINT * scale)))
        _font_cache[key] = ImageFont.truetype(path, px) if path else ImageFont.load_default()
    return _font_cache[key]


def _weight(font):
    w = font[2] if len(font) > 2 else 'normal'
    return 'bold' if 'bold' in str(w) else 'normal'


def rgb(color):
    c = color.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """Color a blended toward b by t (0..1)."""
    x, y = rgb(a), rgb(b)
    return '#{:02x}{:02x}{:02x}'.format(*(int(round(p + t * (q - p))) for p, q in zip(x, y)))


_photo_ok = {}


def photos_supported(widget):
    """Tk photo images crash Tk 8.5 on Cadence's RealVNC-based cdsXvnc; use plain canvas items there.

    CAPLAB_ANTIALIAS=0 / 1 forces the choice.
    """
    force = os.environ.get('CAPLAB_ANTIALIAS')
    if force in ('0', '1'):
        return force == '1'
    try:
        server = widget.winfo_server()
    except Exception:
        return False
    if server not in _photo_ok:
        _photo_ok[server] = 'RealVNC' not in server
    return _photo_ok[server]


class Painter:
    def __init__(self, canvas, bg, enabled=True):
        self.canvas = canvas
        self.bg = bg
        self.items = []
        self.pil = HAVE_PIL and enabled and photos_supported(canvas)
        self.image = None

    # ---- recording API (canvas-like coordinates in pixels)
    def line(self, coords, fill, width=1.0, dash=None, glow=0):
        if len(coords) >= 4:
            self.items.append(('line', list(coords), fill, width, dash, glow))

    def dot(self, x, y, r, fill, outline=None, glow=0):
        self.items.append(('dot', x, y, r, fill, outline, glow))

    def rect(self, x0, y0, x1, y1, fill=None, outline=None):
        self.items.append(('rect', x0, y0, x1, y1, fill, outline))

    def text(self, x, y, text, fill, font, anchor='center', glow=0):
        self.items.append(('text', x, y, str(text), fill, font, anchor, glow))

    def measure(self, text, font):
        if self.pil:
            f = _font(font[1], _weight(font), 1)
            b = f.getbbox(str(text))
            return b[2] - b[0], b[3] - b[1]
        tid = self.canvas.create_text(-1000, -1000, text=text, font=font)
        b = self.canvas.bbox(tid)
        self.canvas.delete(tid)
        return b[2] - b[0], b[3] - b[1]

    # ---- output
    def flush(self):
        c = self.canvas
        c.delete('plot')
        if not self.pil:
            for it in self.items:
                self._canvas_item(it)
            return
        w, h = max(2, c.winfo_width()), max(2, c.winfo_height())
        S = SCALE
        base = Image.new('RGB', (w * S, h * S), self.bg)
        top = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0))
        glow_wide = Image.new('RGB', (w, h), (0, 0, 0))
        glow_core = Image.new('RGB', (w, h), (0, 0, 0))
        db, dt = ImageDraw.Draw(base), ImageDraw.Draw(top)
        gw, gc = ImageDraw.Draw(glow_wide), ImageDraw.Draw(glow_core)
        any_glow = False
        for it in self.items:
            kind = it[0]
            # grid, axes and plain text go to the base; glowing items and curves on top
            draw = dt if kind in ('line', 'dot') or (kind == 'text' and it[7]) else db
            if kind == 'line':
                _, coords, fill, width, dash, glow = it
                pts = [(coords[i] * S, coords[i + 1] * S) for i in range(0, len(coords) - 1, 2)]
                for seg in (_dash(pts, [d * S for d in dash]) if dash else [pts]):
                    draw.line(seg, fill=fill, width=max(1, int(round(width * S))), joint='curve')
                if glow:
                    any_glow = True
                    p1 = [(x / S, y / S) for x, y in pts]
                    gw.line(p1, fill=fill, width=int(width + (9 if glow > 1 else 6)), joint='curve')
                    gc.line(p1, fill=fill, width=int(width + (3 if glow > 1 else 2)), joint='curve')
            elif kind == 'dot':
                _, x, y, r, fill, outline, glow = it
                box = [(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S]
                draw.ellipse(box, fill=fill, outline=outline, width=max(1, S) if outline else 0)
                if glow:
                    any_glow = True
                    gw.ellipse([x - r - 4, y - r - 4, x + r + 4, y + r + 4], fill=fill)
                    gc.ellipse([x - r - 1, y - r - 1, x + r + 1, y + r + 1], fill=fill)
            elif kind == 'rect':
                _, x0, y0, x1, y1, fill, outline = it
                draw.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill, outline=outline, width=S if outline else 0)
            else:
                _, x, y, text, fill, font, anchor, glow = it
                f = _font(font[1], _weight(font), S)
                draw.text((x * S, y * S), text, fill=fill, font=f, anchor=_ANCHOR.get(anchor, 'mm'))
                if glow:
                    any_glow = True
                    f1 = _font(font[1], 'bold', 1)
                    for g in (gw, gc):
                        g.text((x, y), text, fill=fill, font=f1, anchor=_ANCHOR.get(anchor, 'mm'),
                               stroke_width=2 if g is gw else 1, stroke_fill=fill)
        img = base.resize((w, h), Image.LANCZOS)
        if any_glow:
            wide = glow_wide.filter(ImageFilter.GaussianBlur(7))
            core = glow_core.filter(ImageFilter.GaussianBlur(2.2))
            img = ImageChops.screen(img, ImageChops.multiply(wide, Image.new('RGB', (w, h), (150, 150, 150))))
            img = ImageChops.screen(img, ImageChops.multiply(core, Image.new('RGB', (w, h), (175, 175, 175))))
        img = img.convert('RGBA')
        img.alpha_composite(top.resize((w, h), Image.LANCZOS))
        self.image = ImageTk.PhotoImage(img, master=c)
        c.create_image(0, 0, image=self.image, anchor='nw', tags=('plot',))
        c.tag_lower('plot')
        # The canvas owns the photo (and the previous one until the item is replaced);
        # a photo freed while displayed crashes Tk.
        old = getattr(c, '_plot_images', [])
        c._plot_images = [self.image] + old[:1]

    def _canvas_item(self, it):
        c = self.canvas
        kind = it[0]
        if kind == 'line':
            _, coords, fill, width, dash, glow = it
            c.create_line(*coords, fill=fill, width=width, dash=tuple(int(d) for d in dash) if dash else (), tags=('plot',))
        elif kind == 'dot':
            _, x, y, r, fill, outline, glow = it
            c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline or fill, tags=('plot',))
        elif kind == 'rect':
            _, x0, y0, x1, y1, fill, outline = it
            c.create_rectangle(x0, y0, x1, y1, fill=fill or '', outline=outline or '', width=1 if outline else 0, tags=('plot',))
        else:
            _, x, y, text, fill, font, anchor, glow = it
            c.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor, tags=('plot',))


def _dash(pts, pattern):
    """Split a polyline into dash segments."""
    out, on, left, k = [], True, pattern[0], 0
    cur = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while seg - pos > left:
            pos += left
            t = pos / seg
            p = (x0 + t * (x1 - x0), y0 + t * (y1 - y0))
            if on:
                cur.append(p)
                out.append(cur)
            cur = [p]
            on = not on
            k = (k + 1) % len(pattern)
            left = pattern[k]
        left -= seg - pos
        if on:
            cur.append((x1, y1))
    if on and len(cur) > 1:
        out.append(cur)
    return out
