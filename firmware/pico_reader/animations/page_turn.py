"""Page Turn animation -- shows current page number in bottom-right.

Page is calculated as words_read // 250 + 1. Flashes the label to the
highlight color for 3 ticks whenever the page increments.
"""
from adafruit_display_text import label

# Words per "page"
WORDS_PER_PAGE = 250

# Flash duration in ticks
FLASH_TICKS = 3


class Animation:
    def __init__(self):
        self._label = None
        self._current_page = 0
        self._flash_remaining = 0
        self._normal_color = 0x4c4c4c  # subdued wpm-like color
        self._highlight_color = 0x7c7c7c

    def build(self, display):
        """Create a page label and return it as a single-element list."""
        # Use smallfont from the skin if available, otherwise create a basic label
        font = None
        if hasattr(display, '_smallfont'):
            font = display._smallfont
        elif hasattr(display, 'skin') and hasattr(display.skin, '_smallfont'):
            font = display.skin._smallfont

        self._label = label.Label(font, text='pg 1', color=self._normal_color,
                                  base_alignment=False)
        self._label.anchor_point = (1.0, 1.0)
        self._label.anchored_position = (160, 128)

        self._current_page = 1
        self._flash_remaining = 0
        return [self._label]

    def tick(self, state, book, display):
        """Update page number; flash on page change."""
        if self._label is None:
            return

        # Calculate words read -- try book_stats first, fall back to estimate
        words_read = 0
        if hasattr(state, 'book_stats') and hasattr(state.book_stats, 'words_read'):
            words_read = state.book_stats.words_read
        else:
            # Estimate from line position: ~10 words per line is typical
            words_read = book.line_num * 10 + book.word_idx

        new_page = words_read // WORDS_PER_PAGE + 1

        if new_page != self._current_page:
            self._current_page = new_page
            self._flash_remaining = FLASH_TICKS
            self._label.text = 'pg {}'.format(new_page)

        # Handle flash countdown
        if self._flash_remaining > 0:
            # Match skin highlight color
            if hasattr(display, 'skin') and hasattr(display.skin, 'get_highlight_color'):
                self._highlight_color = display.skin.get_highlight_color()
            self._label.color = self._highlight_color
            self._flash_remaining -= 1
        else:
            self._label.color = self._normal_color

    def destroy(self):
        """Release references."""
        self._label = None
        self._current_page = 0
        self._flash_remaining = 0
