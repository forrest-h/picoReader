import displayio
from adafruit_display_text import label
from ..orp import calc_orp_positions, calc_bold_split

# BGR format (https://wamingo.net/rgbbgr/)
PALETTES = [
    {'name': 'Cream/Brown',   'bg': 0xd8ecf4, 'ink': 0x1f2b3d, 'dim': 0x557388},
    {'name': 'Aged/Yellowed', 'bg': 0xb0d8e8, 'ink': 0x1a3040, 'dim': 0x507090},
    {'name': 'Night/Sepia',   'bg': 0x303848, 'ink': 0xa0b8c8, 'dim': 0x607080},
]

# Layout constants
WORD_Y = 70
UNDERLINE_Y = 126
WPM_Y = 128


class Skin:
    """Typewriter/analog skin with Y-jitter and underline progress.

    Group indices: 0=bg, 1=word_prefix, 2=word_orp, 3=word_suffix,
                   4=underline_progress, 5=wpm.
    """

    PALETTES = PALETTES

    def __init__(self, font, smallfont):
        self._font = font
        self._smallfont = smallfont
        self._palette_index = 0
        self._last_progress_width = 0
        # Set by build_group()
        self._bg_palette = None
        self._word_prefix = None
        self._word_orp = None
        self._word_suffix = None
        self._underline_bmp = None
        self._underline_palette = None
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

        # [1] word prefix (main word in normal mode)
        self._word_prefix = label.Label(self._font, text='',
                                        color=pal['ink'],
                                        base_alignment=False)
        self._word_prefix.anchor_point = (0.5, 1)
        self._word_prefix.anchored_position = (80, WORD_Y)
        group.append(self._word_prefix)

        # [2] ORP character label
        self._word_orp = label.Label(self._font, text='',
                                     color=pal['dim'],
                                     base_alignment=False)
        self._word_orp.anchor_point = (0.0, 1)
        self._word_orp.anchored_position = (80, WORD_Y)
        group.append(self._word_orp)

        # [3] word suffix label
        self._word_suffix = label.Label(self._font, text='',
                                        color=pal['ink'],
                                        base_alignment=False)
        self._word_suffix.anchor_point = (0.0, 1)
        self._word_suffix.anchored_position = (90, WORD_Y)
        group.append(self._word_suffix)

        # [4] underline progress (1px tall bitmap)
        self._underline_bmp = displayio.Bitmap(display_width, 1, 2)
        self._underline_palette = displayio.Palette(2)
        self._underline_palette[0] = pal['bg']
        self._underline_palette[1] = pal['ink']
        group.append(
            displayio.TileGrid(self._underline_bmp,
                               pixel_shader=self._underline_palette,
                               y=UNDERLINE_Y))

        # [5] WPM label with typewriter style
        self._wpm_label = label.Label(self._smallfont, text='~ 200 wpm ~',
                                      color=pal['dim'],
                                      base_alignment=False)
        self._wpm_label.anchor_point = (1.0, 1.0)
        self._wpm_label.anchored_position = (158, WPM_Y)
        group.append(self._wpm_label)

        self._last_progress_width = 0
        return group

    def show_word(self, word, orp_mode=None):
        """Update the word display with slight Y-jitter for analog feel."""
        pal = PALETTES[self._palette_index]

        # Pseudo-random Y offset from word content for typewriter feel
        if word:
            offset = (ord(word[0]) % 3) - 1  # -1, 0, or +1
        else:
            offset = 0

        jitter_y = WORD_Y + offset

        if orp_mode == 'color' and len(word) > 1:
            prefix, orp_char, suffix, px, ox, sx = calc_orp_positions(
                word, self._font)
            self._word_prefix.anchor_point = (0.0, 1)
            self._word_prefix.anchored_position = (px, jitter_y)
            self._word_prefix.text = prefix
            self._word_prefix.color = pal['ink']
            # ORP char gets the dim/accent color
            self._word_orp.anchored_position = (ox, jitter_y)
            self._word_orp.text = orp_char
            self._word_orp.color = pal['dim']
            self._word_suffix.anchored_position = (sx, jitter_y)
            self._word_suffix.text = suffix
            self._word_suffix.color = pal['ink']
        elif orp_mode == 'bold' and len(word) > 1:
            bold, fade = calc_bold_split(word)
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = (80, jitter_y)
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = pal['ink']
            self._word_orp.text = ''
            self._word_suffix.text = ''
        else:
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = (80, jitter_y)
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = pal['ink']
            self._word_orp.text = ''
            self._word_suffix.text = ''

    def show_wpm(self, wpm):
        """Update WPM indicator in typewriter style."""
        self._wpm_label.text = "~ {} wpm ~".format(wpm)

    def update_progress(self, pct):
        """Update underline progress bar."""
        width = max(0, int(pct * self._display_width))
        if width == self._last_progress_width:
            return
        # Paint new pixels
        for x in range(self._last_progress_width, width):
            self._underline_bmp[x, 0] = 1
        # Clear pixels if going backward
        for x in range(width, self._last_progress_width):
            self._underline_bmp[x, 0] = 0
        self._last_progress_width = width

    def reset_progress(self):
        """Reset underline progress to zero."""
        for x in range(self._last_progress_width):
            self._underline_bmp[x, 0] = 0
        self._last_progress_width = 0

    def apply_palette(self, palette_index):
        """Apply a palette by index without rebuilding the group."""
        self._palette_index = palette_index
        pal = PALETTES[palette_index]
        self._bg_palette[0] = pal['bg']
        self._word_prefix.color = pal['ink']
        self._word_orp.color = pal['dim']
        self._word_suffix.color = pal['ink']
        self._underline_palette[0] = pal['bg']
        self._underline_palette[1] = pal['ink']
        self._wpm_label.color = pal['dim']

    def get_highlight_color(self):
        """Return current palette's ink color (used as highlight)."""
        return PALETTES[self._palette_index]['ink']
