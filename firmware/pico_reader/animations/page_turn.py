"""Page Turn animation -- shows book progress percentage in bottom-right.

Flashes the label to the highlight color for 3 ticks whenever the
percentage increments.
"""
from adafruit_display_text import label

# Flash duration in ticks
FLASH_TICKS = 3


class Animation:
    def __init__(self):
        self._label = None
        self._current_pct = 0
        self._flash_remaining = 0
        self._normal_color = 0x4c4c4c  # subdued wpm-like color
        self._highlight_color = 0x7c7c7c

    def build(self, display):
        """Create a percentage label and return it as a single-element list."""
        font = None
        if hasattr(display, '_smallfont'):
            font = display._smallfont
        elif hasattr(display, 'skin') and hasattr(display.skin, '_smallfont'):
            font = display.skin._smallfont

        self._label = label.Label(font, text='0%', color=self._normal_color,
                                  base_alignment=False)
        self._label.anchor_point = (1.0, 1.0)
        self._label.anchored_position = (160, 128)

        self._current_pct = 0
        self._flash_remaining = 0
        return [self._label]

    def tick(self, state, book, display):
        """Update progress percentage; flash on change."""
        if self._label is None:
            return

        new_pct = 0
        if book.total_lines > 0:
            new_pct = int(book.line_num * 100 / book.total_lines)
        new_pct = min(100, max(0, new_pct))

        if new_pct != self._current_pct:
            self._current_pct = new_pct
            self._flash_remaining = FLASH_TICKS
            self._label.text = '{}%'.format(new_pct)

        # Handle flash countdown
        if self._flash_remaining > 0:
            if hasattr(display, 'skin') and hasattr(display.skin, 'get_highlight_color'):
                self._highlight_color = display.skin.get_highlight_color()
            self._label.color = self._highlight_color
            self._flash_remaining -= 1
        else:
            self._label.color = self._normal_color

    def destroy(self):
        """Release references."""
        self._label = None
        self._current_pct = 0
        self._flash_remaining = 0
