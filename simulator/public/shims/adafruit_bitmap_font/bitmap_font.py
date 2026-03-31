"""Shim for adafruit_bitmap_font.bitmap_font — font loading."""


class _Font:
    def __init__(self, path):
        self.font_id = path


def load_font(path):
    """Return a font object. The actual PCF parsing happens on the main thread;
    we just store the path as an identifier for the renderer."""
    return _Font(path)
