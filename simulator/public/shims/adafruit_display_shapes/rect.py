"""Shim for adafruit_display_shapes.rect — Rect display element."""


class Rect:
    def __init__(self, x, y, width, height, fill=None, outline=None, stroke=1):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self._fill = fill
        self._outline = outline
        self.stroke = stroke

    @property
    def fill(self):
        return self._fill

    @fill.setter
    def fill(self, value):
        self._fill = value

    @property
    def outline(self):
        return self._outline

    @outline.setter
    def outline(self, value):
        self._outline = value

    def serialize(self):
        return {
            "type": "rect",
            "x": self.x,
            "y": self.y,
            "w": self.width,
            "h": self.height,
            "fill": self._fill if self._fill is not None else -1,
            "outline": self._outline if self._outline is not None else -1,
            "stroke": self.stroke,
        }
