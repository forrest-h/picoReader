import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..orp import calc_orp_positions, calc_bold_split

# BGR format (https://wamingo.net/rgbbgr/)
PALETTES = [
    {'name': 'Dark',       'bg': 0x000000, 'text': 0xe7e7e7, 'wpm': 0x4c4c4c, 'highlight': 0x7c7c7c},
    {'name': 'Light',      'bg': 0xf3f3f3, 'text': 0x000000, 'wpm': 0xa1a1a1, 'highlight': 0x949494},
    {'name': 'Gray',       'bg': 0x696969, 'text': 0x000000, 'wpm': 0x272727, 'highlight': 0x403f3f},
    {'name': 'Crimson',    'bg': 0x460808, 'text': 0xbdbdbd, 'wpm': 0x898888, 'highlight': 0x0e8ee6},
    {'name': 'Muted Dark', 'bg': 0x000000, 'text': 0x696969, 'wpm': 0x4c4c4c, 'highlight': 0x696969},
]

# Guide mark positions (crosshair)
GUIDE_RECTS = [(67, 42, 21, 1), (67, 84, 21, 1), (77, 42, 1, 6), (77, 78, 1, 6)]

# Layout constants
WORD_CENTER = (80, 70)
WPM_POS = (0, 128)
DEFAULT_WPM = 200


class Skin:
    """Default skin -- preserves the exact original picoReader layout.

    Group indices: 0=bg, 1=word_prefix, 2=word_orp, 3=word_suffix,
                   4-7=guides, 8=progress, 9=wpm.
    """

    PALETTES = PALETTES

    def __init__(self, font, smallfont):
        self._font = font
        self._smallfont = smallfont
        self._palette_index = 0
        self._last_progress_width = 0
        # These are set by build_group()
        self._bg_palette = None
        self._word_prefix = None
        self._word_orp = None
        self._word_suffix = None
        self._guides = None
        self._progress_bmp = None
        self._progress_palette = None
        self._wpm_label = None
        self._display_width = 0

    def build_group(self, display_width, display_height):
        """Create and return the reader displayio.Group."""
        self._display_width = display_width
        pal = PALETTES[self._palette_index]
        group = displayio.Group()

        # [0] background
        bg_bmp = displayio.Bitmap(display_width, display_height, 1)
        self._bg_palette = displayio.Palette(1)
        self._bg_palette[0] = pal['bg']
        group.append(displayio.TileGrid(bg_bmp, pixel_shader=self._bg_palette))

        # [1] word prefix label (for ORP mode, or full word in normal mode)
        self._word_prefix = label.Label(self._font, text="{:^30}".format(''),
                                        color=pal['text'], base_alignment=False)
        self._word_prefix.anchor_point = (0.5, 1)
        self._word_prefix.anchored_position = WORD_CENTER
        group.append(self._word_prefix)

        # [2] ORP highlight character label
        self._word_orp = label.Label(self._font, text='',
                                     color=pal['highlight'], base_alignment=False)
        self._word_orp.anchor_point = (0.0, 1)
        self._word_orp.anchored_position = (80, 70)
        group.append(self._word_orp)

        # [3] word suffix label
        self._word_suffix = label.Label(self._font, text='',
                                        color=pal['text'], base_alignment=False)
        self._word_suffix.anchor_point = (0.0, 1)
        self._word_suffix.anchored_position = (90, 70)
        group.append(self._word_suffix)

        # [4-7] guide rects
        self._guides = []
        for x, y, w, h in GUIDE_RECTS:
            r = Rect(x, y, w, h, fill=pal['highlight'])
            self._guides.append(r)
            group.append(r)

        # [8] progress bar -- Bitmap so width is mutable
        self._progress_bmp = displayio.Bitmap(display_width, 2, 2)
        self._progress_palette = displayio.Palette(2)
        self._progress_palette[0] = pal['bg']
        self._progress_palette[1] = pal['highlight']
        group.append(
            displayio.TileGrid(self._progress_bmp, pixel_shader=self._progress_palette))

        # [9] WPM label
        self._wpm_label = label.Label(self._smallfont, text=str(DEFAULT_WPM),
                                      color=pal['wpm'], base_alignment=False)
        self._wpm_label.anchor_point = (0.0, 1.0)
        self._wpm_label.anchored_position = WPM_POS
        group.append(self._wpm_label)

        self._last_progress_width = 0
        return group

    def show_word(self, word, orp_mode=None):
        """Update the word display.

        orp_mode: None, 'color', or 'bold'.
        """
        if orp_mode == 'color' and len(word) > 1:
            prefix, orp_char, suffix, px, ox, sx = calc_orp_positions(
                word, self._font)
            # Prefix: right-anchored so its right edge meets ORP
            self._word_prefix.anchor_point = (1.0, 1)
            self._word_prefix.anchored_position = (px, 70)
            self._word_prefix.text = prefix
            self._word_prefix.color = PALETTES[self._palette_index]['text']
            # ORP char: centered at anchor point
            self._word_orp.anchor_point = (0.5, 1)
            self._word_orp.anchored_position = (ox, 70)
            self._word_orp.text = orp_char
            self._word_orp.color = PALETTES[self._palette_index]['highlight']
            # Suffix: left-anchored from ORP right edge
            self._word_suffix.anchor_point = (0.0, 1)
            self._word_suffix.anchored_position = (sx, 70)
            self._word_suffix.text = suffix
            self._word_suffix.color = PALETTES[self._palette_index]['text']
        elif orp_mode == 'bold' and len(word) > 1:
            bold, fade = calc_bold_split(word)
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = WORD_CENTER
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = PALETTES[self._palette_index]['text']
            # Use ORP label for bold portion overlay (positioned at start)
            self._word_orp.text = ''
            self._word_suffix.text = ''
        else:
            # Normal mode -- single centered label
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = WORD_CENTER
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = PALETTES[self._palette_index]['text']
            self._word_orp.text = ''
            self._word_suffix.text = ''

    def show_wpm(self, wpm):
        """Update WPM indicator."""
        self._wpm_label.text = str(wpm)

    def update_progress(self, pct):
        """Update progress bar. pct is 0.0-1.0 float."""
        width = max(1, int(pct * self._display_width))
        if width == self._last_progress_width:
            return
        # Paint new pixels
        for x in range(self._last_progress_width, width):
            self._progress_bmp[x, 0] = 1
            self._progress_bmp[x, 1] = 1
        # Clear pixels if going backward (new book)
        for x in range(width, self._last_progress_width):
            self._progress_bmp[x, 0] = 0
            self._progress_bmp[x, 1] = 0
        self._last_progress_width = width

    def reset_progress(self):
        """Reset progress bar to zero."""
        for x in range(self._last_progress_width):
            self._progress_bmp[x, 0] = 0
            self._progress_bmp[x, 1] = 0
        self._last_progress_width = 0

    def apply_palette(self, palette_index):
        """Apply a palette by index without rebuilding the group."""
        self._palette_index = palette_index
        pal = PALETTES[palette_index]
        self._bg_palette[0] = pal['bg']
        self._word_prefix.color = pal['text']
        self._word_orp.color = pal['highlight']
        self._word_suffix.color = pal['text']
        self._wpm_label.color = pal['wpm']
        for g in self._guides:
            g.fill = pal['highlight']
        self._progress_palette[0] = pal['bg']
        self._progress_palette[1] = pal['highlight']

    def get_highlight_color(self):
        """Return current palette's highlight/accent color."""
        return PALETTES[self._palette_index]['highlight']
