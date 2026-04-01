import displayio
from adafruit_display_text import label
from ..orp import calc_orp_positions, calc_bold_split

# BGR format (https://wamingo.net/rgbbgr/)
PALETTES = [
    {'name': 'Green Phosphor', 'bg': 0x000000, 'phosphor': 0x33ff33, 'dim': 0x1a8a1a},
    {'name': 'Amber Phosphor', 'bg': 0x000000, 'phosphor': 0x00b0ff, 'dim': 0x005880},
    {'name': 'Blue Phosphor',  'bg': 0x000000, 'phosphor': 0xff3300, 'dim': 0x801a00},
]


class Skin:
    """Terminal/CRT phosphor skin.

    Group indices: 0=bg, 1=path_header, 2=word_prefix, 3=word_orp,
                   4=word_suffix, 5=cursor, 6=progress, 7=wpm.
    """

    PALETTES = PALETTES

    def __init__(self, font, smallfont):
        self._font = font
        self._smallfont = smallfont
        self._palette_index = 0
        # Set by build_group()
        self._bg_palette = None
        self._path_label = None
        self._word_prefix = None
        self._word_orp = None
        self._word_suffix = None
        self._cursor_label = None
        self._progress_label = None
        self._wpm_label = None
        self._book_title = ''

    def build_group(self, display_width, display_height):
        """Create and return the reader displayio.Group."""
        pal = PALETTES[self._palette_index]
        group = displayio.Group()

        # [0] background
        bg_bmp = displayio.Bitmap(display_width, display_height, 1)
        self._bg_palette = displayio.Palette(1)
        self._bg_palette[0] = pal['bg']
        group.append(displayio.TileGrid(bg_bmp, pixel_shader=self._bg_palette))

        # [1] path header
        self._path_label = label.Label(self._smallfont, text='C:\\BOOKS>',
                                       color=pal['dim'], base_alignment=False)
        self._path_label.anchor_point = (0.0, 0.0)
        self._path_label.anchored_position = (2, 2)
        group.append(self._path_label)

        # [2] word prefix (main word in normal mode)
        self._word_prefix = label.Label(self._font, text='',
                                        color=pal['phosphor'],
                                        base_alignment=False)
        self._word_prefix.anchor_point = (0.5, 1)
        self._word_prefix.anchored_position = (80, 70)
        group.append(self._word_prefix)

        # [3] ORP character label
        self._word_orp = label.Label(self._font, text='',
                                     color=pal['bg'], base_alignment=False)
        self._word_orp.anchor_point = (0.0, 1)
        self._word_orp.anchored_position = (80, 70)
        group.append(self._word_orp)

        # [4] word suffix label
        self._word_suffix = label.Label(self._font, text='',
                                        color=pal['phosphor'],
                                        base_alignment=False)
        self._word_suffix.anchor_point = (0.0, 1)
        self._word_suffix.anchored_position = (90, 70)
        group.append(self._word_suffix)

        # [5] cursor (visible only when paused)
        self._cursor_label = label.Label(self._font, text='_',
                                         color=pal['phosphor'],
                                         base_alignment=False)
        self._cursor_label.anchor_point = (0.5, 1)
        self._cursor_label.anchored_position = (80, 86)
        self._cursor_label.color = pal['bg']  # Hidden by default
        group.append(self._cursor_label)

        # [6] ASCII progress bar
        self._progress_label = label.Label(self._smallfont,
                                           text='[>          ]  0%',
                                           color=pal['dim'],
                                           base_alignment=False)
        self._progress_label.anchor_point = (0.5, 1.0)
        self._progress_label.anchored_position = (80, 116)
        group.append(self._progress_label)

        # [7] WPM label
        self._wpm_label = label.Label(self._smallfont, text='200',
                                      color=pal['dim'], base_alignment=False)
        self._wpm_label.anchor_point = (0.0, 1.0)
        self._wpm_label.anchored_position = (0, 128)
        group.append(self._wpm_label)

        return group

    def show_word(self, word, orp_mode=None):
        """Update the word display."""
        pal = PALETTES[self._palette_index]

        if orp_mode == 'color' and len(word) > 1:
            prefix, orp_char, suffix, px, ox, sx = calc_orp_positions(
                word, self._font)
            self._word_prefix.anchor_point = (0.0, 1)
            self._word_prefix.anchored_position = (px, 70)
            self._word_prefix.text = prefix
            self._word_prefix.color = pal['phosphor']
            # ORP char gets inverted: bg on phosphor background
            # Use dim color for the ORP highlight
            self._word_orp.anchored_position = (ox, 70)
            self._word_orp.text = orp_char
            self._word_orp.color = pal['bg']
            self._word_suffix.anchored_position = (sx, 70)
            self._word_suffix.text = suffix
            self._word_suffix.color = pal['phosphor']
        elif orp_mode == 'bold' and len(word) > 1:
            bold, fade = calc_bold_split(word)
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = (80, 70)
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = pal['phosphor']
            self._word_orp.text = ''
            self._word_suffix.text = ''
        else:
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = (80, 70)
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = pal['phosphor']
            self._word_orp.text = ''
            self._word_suffix.text = ''

    def show_wpm(self, wpm):
        """Update WPM indicator."""
        self._wpm_label.text = str(wpm)

    def update_progress(self, pct):
        """Update ASCII progress bar."""
        filled = int(pct * 10)
        bar = '=' * filled + '>' + ' ' * (10 - filled)
        self._progress_label.text = "[{}] {:>3}%".format(bar, int(pct * 100))

    def reset_progress(self):
        """Reset progress bar to zero."""
        self._progress_label.text = '[>          ]  0%'

    def set_cursor_visible(self, visible):
        """Show or hide the cursor underscore."""
        pal = PALETTES[self._palette_index]
        if visible:
            self._cursor_label.color = pal['phosphor']
        else:
            self._cursor_label.color = pal['bg']

    def set_book_title(self, title):
        """Update the path header with the current book title."""
        self._book_title = title
        short = title[:12].upper().replace(' ', '_')
        self._path_label.text = "C:\\BOOKS\\{}>".format(short)

    def apply_palette(self, palette_index):
        """Apply a palette by index without rebuilding the group."""
        self._palette_index = palette_index
        pal = PALETTES[palette_index]
        self._bg_palette[0] = pal['bg']
        self._path_label.color = pal['dim']
        self._word_prefix.color = pal['phosphor']
        self._word_orp.color = pal['bg']
        self._word_suffix.color = pal['phosphor']
        # Keep cursor visibility state — re-hide if it was hidden
        if self._cursor_label.color == 0x000000 or self._cursor_label.color == pal['bg']:
            self._cursor_label.color = pal['bg']
        else:
            self._cursor_label.color = pal['phosphor']
        self._progress_label.color = pal['dim']
        self._wpm_label.color = pal['dim']

    def get_highlight_color(self):
        """Return current palette's phosphor color (used as highlight)."""
        return PALETTES[self._palette_index]['phosphor']
