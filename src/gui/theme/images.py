"""Raster pieces for the ttk theme, drawn at start-up from theme tokens.

Tk cannot round corners, so rounded controls are ttk "image" elements: a
small antialiased picture whose edges stay fixed while the middle stretches
(9-slice). Drawing them with Pillow from the palette, instead of shipping
PNGs, is what lets a new theme restyle every control by changing tokens.

Transparent corners show the *style's* background colour, not the parent's,
so every style that uses these images also sets `background` to the colour
of the surface it sits on (see styles.py).
"""
import os

from PIL import Image, ImageDraw, ImageFont, ImageTk

_SS = 4  # supersampling factor for smooth edges


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


class _Sketch:
    """Draws at 4x on two layers: colour on an opaque RGB layer and coverage
    on a separate alpha mask. Downsampling them apart and merging afterwards
    keeps edge pixels the shape's own colour; resampling one RGBA image mixes
    in the colour of the transparent pixels and leaves a halo."""

    def __init__(self, width, height, base):
        self.size = (width, height)
        big = (width * _SS, height * _SS)
        self.rgb = Image.new("RGB", big, _rgb(base))
        self.mask = Image.new("L", big, 0)
        self.paint = ImageDraw.Draw(self.rgb)
        self.cover = ImageDraw.Draw(self.mask)

    def image(self):
        out = self.rgb.resize(self.size, Image.LANCZOS)
        out.putalpha(self.mask.resize(self.size, Image.LANCZOS))
        return out


def _rounded(sketch, radius, fill, border=None, border_width=1, ring=None, ring_width=2):
    s = _SS
    w, h = sketch.rgb.size
    outer = (0, 0, w - 1, h - 1)
    sketch.cover.rounded_rectangle(outer, radius=(radius + (ring_width if ring else 0)) * s, fill=255)
    box = outer
    if ring:
        inset = ring_width * s
        box = (inset, inset, w - 1 - inset, h - 1 - inset)
    if border:
        sketch.paint.rounded_rectangle(box, radius=radius * s, fill=_rgb(border))
        bw = border_width * s
        box = (box[0] + bw, box[1] + bw, box[2] - bw, box[3] - bw)
        radius = max(0, radius - border_width)
    sketch.paint.rounded_rectangle(box, radius=radius * s, fill=_rgb(fill))


def rounded_box(width, height, radius, fill, border=None, border_width=1,
                ring=None, ring_width=2):
    """A rounded rectangle, optionally with a border and an outer focus
    ring. Corners outside the shape are transparent."""
    sketch = _Sketch(width, height, ring or border or fill)
    _rounded(sketch, radius, fill, border, border_width, ring, ring_width)
    return sketch.image()


def check_box(size, radius, fill, border, mark=None):
    sketch = _Sketch(size, size, border)
    _rounded(sketch, radius, fill, border)
    if mark:
        s = size * _SS
        pts = [(s * 0.26, s * 0.53), (s * 0.43, s * 0.69), (s * 0.75, s * 0.34)]
        sketch.paint.line(pts, fill=_rgb(mark), width=max(2, round(s * 0.12)), joint="curve")
    return sketch.image()


def radio_dot(size, fill, border, dot=None):
    sketch = _Sketch(size, size, border)
    s = size * _SS
    sketch.cover.ellipse((0, 0, s - 1, s - 1), fill=255)
    sketch.paint.ellipse((0, 0, s - 1, s - 1), fill=_rgb(border))
    sketch.paint.ellipse((_SS, _SS, s - 1 - _SS, s - 1 - _SS), fill=_rgb(fill))
    if dot:
        r, c = s * 0.22, s / 2
        sketch.paint.ellipse((c - r, c - r, c + r, c + r), fill=_rgb(dot))
    return sketch.image()


def chevron(width, height, color, direction="down", stroke=1.6):
    sketch = _Sketch(width, height, color)
    w, h = sketch.rgb.size
    cx, cy = w / 2, h / 2
    dx, dy = w * 0.22, h * 0.13
    if direction == "down":
        pts = [(cx - dx, cy - dy), (cx, cy + dy), (cx + dx, cy - dy)]
    else:
        pts = [(cx - dx, cy + dy), (cx, cy - dy), (cx + dx, cy + dy)]
    sketch.cover.line(pts, fill=255, width=round(stroke * _SS), joint="curve")
    return sketch.image()


def theme_preview(width, height, palette, split_with=None, radius=6):
    """A miniature PDF Aura window in a theme's colours, for the theme
    picker: sidebar, a card with text lines and an accent button. With
    `split_with`, the right half is drawn in that second palette ("System"
    shows both)."""

    def draw(p):
        s = _SS
        sketch = _Sketch(width, height, p.canvas)
        paint = sketch.paint
        W, H = width * s, height * s
        paint.rectangle((0, 0, W, H), fill=_rgb(p.canvas))
        side = int(W * 0.26)
        paint.rectangle((0, 0, side, H), fill=_rgb(p.sidebar))
        for i in range(4):   # nav rows, the first one selected
            y = int(H * (0.18 + i * 0.13))
            fill = p.surface if i == 0 else p.border_subtle
            paint.rounded_rectangle((int(W * 0.04), y, side - int(W * 0.04), y + int(H * 0.07)),
                                    radius=2 * s, fill=_rgb(fill))
        card = (side + int(W * 0.07), int(H * 0.16), W - int(W * 0.07), H - int(H * 0.14))
        paint.rounded_rectangle(card, radius=4 * s, fill=_rgb(p.surface), outline=_rgb(p.border_subtle),
                                width=s)
        x0, x1 = card[0] + int(W * 0.06), card[2] - int(W * 0.06)
        line = int(H * 0.055)
        for y, colour, share in ((0.26, p.text, 0.55), (0.40, p.text_secondary, 0.9),
                                 (0.51, p.text_secondary, 0.7)):
            top = int(H * y)
            paint.rounded_rectangle((x0, top, x0 + int((x1 - x0) * share), top + line),
                                    radius=line // 2, fill=_rgb(colour))
        button_top = int(H * 0.66)
        paint.rounded_rectangle((x0, button_top, x0 + int((x1 - x0) * 0.42), button_top + int(H * 0.11)),
                                radius=2 * s, fill=_rgb(p.accent))
        paint.rounded_rectangle((0, 0, W - 1, H - 1), radius=radius * s, outline=_rgb(p.border), width=s)
        return sketch

    sketch = draw(palette)
    if split_with is not None:
        other = draw(split_with)
        W, H = width * _SS, height * _SS
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon([(W * 0.62, 0), (W, 0), (W, H), (W * 0.38, H)], fill=255)
        sketch.rgb.paste(other.rgb, (0, 0), mask)
    sketch.cover.rounded_rectangle((0, 0, width * _SS - 1, height * _SS - 1), radius=radius * _SS, fill=255)
    return sketch.image()


# ── Icons ───────────────────────────────────────────────────────────────────

class Icons:
    """Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10)
    glyphs by meaning, so screens ask for "lock", not for U+E72E."""
    COMPRESS = "\uE73F"
    ORGANIZE = "\uE8A9"
    SCAN = "\uE722"
    CONVERT = "\uE8AB"
    SECURITY = "\uE72E"
    ADVANCED = "\uE90F"
    BATCH = "\uE81E"
    SETTINGS = "\uE713"
    MIC = "\uE720"
    SEND = "\uE724"
    DOCUMENT = "\uE8A5"
    FOLDER = "\uE838"
    OPEN = "\uE8A7"
    INFO = "\uE946"
    WARNING = "\uE7BA"
    ERROR = "\uE783"
    SUCCESS = "\uE73E"
    CLOSE = "\uE711"
    ADD = "\uE710"
    DELETE = "\uE74D"
    UP = "\uE70E"
    DOWN = "\uE70D"
    LEFT = "\uE76B"
    RIGHT = "\uE76C"
    ROTATE_CW = "\uE7AD"
    CROP = "\uE7A8"
    FULLSCREEN = "\uE740"
    SPARK = "\uE945"
    ZOOM_IN = "\uE8A3"
    ZOOM_OUT = "\uE71F"
    SHIELD = "\uEA18"
    CLEAR = "\uE894"
    SYNC = "\uE72C"


def _icon_font_path(files):
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in files:
        path = os.path.join(fonts, name)
        if os.path.isfile(path):
            return path
    return None


def icon_image(glyph, size, color, font_files, box=None):
    """A glyph as an RGBA image, centred in a square box, or None when no icon
    font is installed (callers then show text only)."""
    path = _icon_font_path(font_files)
    if not path:
        return None
    box = box or size + 4
    font = ImageFont.truetype(path, size * _SS)
    sketch = _Sketch(box, box, color)
    left, top, right, bottom = sketch.cover.textbbox((0, 0), glyph, font=font)
    x = (box * _SS - (right - left)) / 2 - left
    y = (box * _SS - (bottom - top)) / 2 - top
    sketch.cover.text((x, y), glyph, font=font, fill=255)
    return sketch.image()


class ImageBank:
    """Keeps PhotoImages alive (Tk forgets an image once Python drops it)
    and hands out one instance per distinct recipe.

    A `live` recipe reads its colours from the active theme; repaint()
    redraws those into the same PhotoImage, so every widget showing one
    follows a theme change without being told."""

    def __init__(self, master):
        self.master = master
        self._photos = {}
        self._live = {}

    def photo(self, key, factory, live=False):
        photo = self._photos.get(key)
        if photo is None:
            image = factory()
            if image is None:
                return None
            photo = ImageTk.PhotoImage(image, master=self.master)
            self._photos[key] = photo
            if live:
                self._live[key] = factory
        return photo

    def repaint(self):
        for key, factory in self._live.items():
            image = factory()
            if image is None:
                continue
            photo = self._photos[key]
            # blank() first: paste() composites over the old pixels, and
            # the antialiased edges would keep a fringe of the old colour.
            photo._PhotoImage__photo.blank()
            photo.paste(image)

    def is_live(self, photo):
        """True if `photo` (a PhotoImage or its Tk name) follows the theme."""
        name = str(photo)
        return any(str(self._photos[key]) == name for key in self._live)

    def __len__(self):
        return len(self._photos)
