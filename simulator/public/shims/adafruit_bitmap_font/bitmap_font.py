"""Shim for adafruit_bitmap_font.bitmap_font — font loading."""


class _Glyph:
    """Minimal glyph info for ORP pixel-width calculations."""
    def __init__(self, shift_x):
        self.shift_x = shift_x


class _Font:
    def __init__(self, path):
        self.font_id = path
        # Approximate character width based on font size in filename
        self._default_width = 8
        if '14' in path:
            self._default_width = 8
        elif '9' in path:
            self._default_width = 6

    def get_glyph(self, codepoint):
        """Return a glyph object with shift_x (advance width in pixels).

        Real PCF fonts have per-character widths. This shim returns a
        reasonable fixed width for ORP positioning calculations.
        Narrow chars (i, l, 1) get less, wide chars (m, w, M, W) get more.
        """
        ch = chr(codepoint)
        w = self._default_width
        if ch in 'iljt!|:;.,\'':
            w = max(3, w - 3)
        elif ch in 'mwMWHNOQDG@':
            w = w + 2
        return _Glyph(w)


def load_font(path):
    """Return a font object. The actual PCF parsing happens on the main thread;
    we just store the path as an identifier for the renderer."""
    return _Font(path)
