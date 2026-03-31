"""Shim for adafruit_display_text.label — Label display element."""


class Label:
    def __init__(self, font, text='', color=0xFFFFFF, base_alignment=True, **kwargs):
        self._font = font
        self._text = text
        self._color = color
        self._base_alignment = base_alignment
        self._anchor_point = (0.0, 0.0)
        self._anchored_position = (0, 0)

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value

    @property
    def anchor_point(self):
        return self._anchor_point

    @anchor_point.setter
    def anchor_point(self, value):
        self._anchor_point = value

    @property
    def anchored_position(self):
        return self._anchored_position

    @anchored_position.setter
    def anchored_position(self, value):
        self._anchored_position = value

    def serialize(self):
        return {
            "type": "label",
            "text": self._text,
            "x": self._anchored_position[0],
            "y": self._anchored_position[1],
            "anchorX": self._anchor_point[0],
            "anchorY": self._anchor_point[1],
            "color": self._color,
            "fontId": self._font.font_id if hasattr(self._font, 'font_id') else 'unknown',
            "baseAlignment": self._base_alignment,
        }
