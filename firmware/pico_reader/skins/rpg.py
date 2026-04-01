import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..orp import calc_orp_positions, calc_bold_split

# BGR format (https://wamingo.net/rgbbgr/)
PALETTES = [
    {'name': 'Gold/Crimson', 'bg': 0x2e1a1a, 'border': 0x00c2e6, 'text': 0xeeeeee, 'hp_fill': 0x6045e9},
    {'name': 'Ice/Blue',     'bg': 0x2e1a1a, 'border': 0xe6c200, 'text': 0xeeeeee, 'hp_fill': 0xe6c200},
    {'name': 'Forest/Green', 'bg': 0x1a2e1a, 'border': 0x00c200, 'text': 0xeeeeee, 'hp_fill': 0x00c200},
]

# Dialogue box geometry
BOX_X = 8
BOX_Y = 30
BOX_W = 144
BOX_H = 60
BOX_STROKE = 2
BOX_INNER_X = BOX_X + BOX_STROKE
BOX_INNER_Y = BOX_Y + BOX_STROKE
BOX_INNER_W = BOX_W - BOX_STROKE * 2
BOX_INNER_H = BOX_H - BOX_STROKE * 2

# HP bar geometry
HP_X = 20
HP_Y = 108
HP_W = 120
HP_H = 6

# Flavor texts for variety
FLAVOR_TEXTS = [
    '* A voice speaks... *',
    '* Words appear... *',
    '* You read aloud... *',
    '* The tome glows... *',
]


class Skin:
    """RPG dialogue box skin.

    Group indices: 0=bg, 1=border_rect, 2=inner_rect, 3=flavor_text,
                   4=word_prefix, 5=word_orp, 6=word_suffix,
                   7=prog_label, 8=hp_bar, 9=wpm.
    """

    PALETTES = PALETTES

    def __init__(self, font, smallfont):
        self._font = font
        self._smallfont = smallfont
        self._palette_index = 0
        self._last_hp_width = 0
        self._flavor_idx = 0
        # Set by build_group()
        self._bg_palette = None
        self._border_rect = None
        self._inner_rect = None
        self._flavor_label = None
        self._word_prefix = None
        self._word_orp = None
        self._word_suffix = None
        self._prog_label = None
        self._hp_bmp = None
        self._hp_palette = None
        self._wpm_label = None

    def build_group(self, display_width, display_height):
        """Create and return the reader displayio.Group."""
        pal = PALETTES[self._palette_index]
        group = displayio.Group()

        # [0] background
        bg_bmp = displayio.Bitmap(display_width, display_height, 1)
        self._bg_palette = displayio.Palette(1)
        self._bg_palette[0] = pal['bg']
        group.append(displayio.TileGrid(bg_bmp, pixel_shader=self._bg_palette))

        # [1] dialogue box border
        self._border_rect = Rect(BOX_X, BOX_Y, BOX_W, BOX_H,
                                 fill=pal['border'])
        group.append(self._border_rect)

        # [2] dialogue box inner fill
        self._inner_rect = Rect(BOX_INNER_X, BOX_INNER_Y,
                                BOX_INNER_W, BOX_INNER_H,
                                fill=pal['bg'])
        group.append(self._inner_rect)

        # [3] flavor text
        self._flavor_label = label.Label(self._smallfont,
                                         text=FLAVOR_TEXTS[0],
                                         color=pal['border'],
                                         base_alignment=False)
        self._flavor_label.anchor_point = (0.5, 0.0)
        self._flavor_label.anchored_position = (80, BOX_Y + 4)
        group.append(self._flavor_label)

        # [4] word prefix (main word in normal mode)
        self._word_prefix = label.Label(self._font, text='',
                                        color=pal['text'],
                                        base_alignment=False)
        self._word_prefix.anchor_point = (0.5, 1)
        self._word_prefix.anchored_position = (80, BOX_Y + BOX_H - 8)
        group.append(self._word_prefix)

        # [5] ORP character label
        self._word_orp = label.Label(self._font, text='',
                                     color=pal['border'],
                                     base_alignment=False)
        self._word_orp.anchor_point = (0.0, 1)
        self._word_orp.anchored_position = (80, BOX_Y + BOX_H - 8)
        group.append(self._word_orp)

        # [6] word suffix label
        self._word_suffix = label.Label(self._font, text='',
                                        color=pal['text'],
                                        base_alignment=False)
        self._word_suffix.anchor_point = (0.0, 1)
        self._word_suffix.anchored_position = (90, BOX_Y + BOX_H - 8)
        group.append(self._word_suffix)

        # [7] PROG label
        self._prog_label = label.Label(self._smallfont, text='PROG',
                                       color=pal['border'],
                                       base_alignment=False)
        self._prog_label.anchor_point = (1.0, 0.5)
        self._prog_label.anchored_position = (HP_X - 2, HP_Y + HP_H // 2)
        group.append(self._prog_label)

        # [8] HP-bar progress (mutable Bitmap)
        self._hp_bmp = displayio.Bitmap(HP_W, HP_H, 2)
        self._hp_palette = displayio.Palette(2)
        self._hp_palette[0] = pal['bg']
        self._hp_palette[1] = pal['hp_fill']
        group.append(
            displayio.TileGrid(self._hp_bmp, pixel_shader=self._hp_palette,
                               x=HP_X, y=HP_Y))

        # [9] WPM label
        self._wpm_label = label.Label(self._smallfont, text='200',
                                      color=pal['border'],
                                      base_alignment=False)
        self._wpm_label.anchor_point = (1.0, 1.0)
        self._wpm_label.anchored_position = (158, 128)
        group.append(self._wpm_label)

        self._last_hp_width = 0
        return group

    def show_word(self, word, orp_mode=None):
        """Update the word display."""
        pal = PALETTES[self._palette_index]
        word_y = BOX_Y + BOX_H - 8

        # Cycle flavor text based on word content for variety
        if word:
            self._flavor_idx = ord(word[0]) % len(FLAVOR_TEXTS)
            self._flavor_label.text = FLAVOR_TEXTS[self._flavor_idx]

        if orp_mode == 'color' and len(word) > 1:
            prefix, orp_char, suffix, px, ox, sx = calc_orp_positions(
                word, self._font)
            self._word_prefix.anchor_point = (1.0, 1)
            self._word_prefix.anchored_position = (px, word_y)
            self._word_prefix.text = prefix
            self._word_prefix.color = pal['text']
            self._word_orp.anchor_point = (0.5, 1)
            self._word_orp.anchored_position = (ox, word_y)
            self._word_orp.text = orp_char
            self._word_orp.color = pal['border']
            self._word_suffix.anchor_point = (0.0, 1)
            self._word_suffix.anchored_position = (sx, word_y)
            self._word_suffix.text = suffix
            self._word_suffix.color = pal['text']
        elif orp_mode == 'bold' and len(word) > 1:
            bold, fade = calc_bold_split(word)
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = (80, word_y)
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = pal['text']
            self._word_orp.text = ''
            self._word_suffix.text = ''
        else:
            self._word_prefix.anchor_point = (0.5, 1)
            self._word_prefix.anchored_position = (80, word_y)
            self._word_prefix.text = "{:^30}".format(word)
            self._word_prefix.color = pal['text']
            self._word_orp.text = ''
            self._word_suffix.text = ''

    def show_wpm(self, wpm):
        """Update WPM indicator."""
        self._wpm_label.text = str(wpm)

    def update_progress(self, pct):
        """Update HP-bar progress."""
        width = max(0, min(HP_W, int(pct * HP_W)))
        if width == self._last_hp_width:
            return
        # Fill new pixels
        for x in range(self._last_hp_width, width):
            for y in range(HP_H):
                self._hp_bmp[x, y] = 1
        # Clear pixels if going backward
        for x in range(width, self._last_hp_width):
            for y in range(HP_H):
                self._hp_bmp[x, y] = 0
        self._last_hp_width = width

    def reset_progress(self):
        """Reset HP bar to zero."""
        for x in range(self._last_hp_width):
            for y in range(HP_H):
                self._hp_bmp[x, y] = 0
        self._last_hp_width = 0

    def apply_palette(self, palette_index):
        """Apply a palette by index without rebuilding the group."""
        self._palette_index = palette_index
        pal = PALETTES[palette_index]
        self._bg_palette[0] = pal['bg']
        self._border_rect.fill = pal['border']
        self._inner_rect.fill = pal['bg']
        self._flavor_label.color = pal['border']
        self._word_prefix.color = pal['text']
        self._word_orp.color = pal['border']
        self._word_suffix.color = pal['text']
        self._prog_label.color = pal['border']
        self._hp_palette[0] = pal['bg']
        self._hp_palette[1] = pal['hp_fill']
        self._wpm_label.color = pal['border']

    def get_highlight_color(self):
        """Return current palette's border/accent color."""
        return PALETTES[self._palette_index]['border']

    # ----- Menu rendering (RPG inventory style) -----

    def build_menu_group(self, display_width, display_height):
        """Build an RPG inventory-styled menu group. Returns a displayio.Group."""
        pal = PALETTES[self._palette_index]
        group = displayio.Group()

        # [0] dark background
        bg_bmp = displayio.Bitmap(display_width, display_height, 1)
        self._menu_bg_palette = displayio.Palette(1)
        self._menu_bg_palette[0] = pal['bg']
        group.append(displayio.TileGrid(bg_bmp, pixel_shader=self._menu_bg_palette))

        # [1] title bar label
        self._menu_title = label.Label(self._smallfont, text='INVENTORY',
                                       color=pal['border'],
                                       base_alignment=False)
        self._menu_title.anchor_point = (0.5, 0.5)
        self._menu_title.anchored_position = (80, 10)
        group.append(self._menu_title)

        # [2..4] 3 slot border rects (gold-bordered)
        # [5..7] 3 slot inner fill rects
        # [8..10] 3 slot title labels
        # [11..13] 3 slot detail labels
        self._menu_slot_borders = []
        self._menu_slot_fills = []
        self._menu_slot_titles = []
        self._menu_slot_details = []

        slot_positions = [(22, 32), (58, 32), (94, 32)]
        for y, h in slot_positions:
            border = Rect(6, y, 148, h, fill=pal['border'])
            group.append(border)
            self._menu_slot_borders.append(border)

            inner = Rect(8, y + 2, 144, h - 4, fill=pal['bg'])
            group.append(inner)
            self._menu_slot_fills.append(inner)

            title_lbl = label.Label(self._smallfont, text='',
                                    color=pal['text'],
                                    base_alignment=False)
            title_lbl.anchor_point = (0.5, 0.5)
            title_lbl.anchored_position = (80, y + 10)
            group.append(title_lbl)
            self._menu_slot_titles.append(title_lbl)

            detail_lbl = label.Label(self._smallfont, text='',
                                     color=pal['border'],
                                     base_alignment=False)
            detail_lbl.anchor_point = (0.5, 0.5)
            detail_lbl.anchored_position = (80, y + 22)
            group.append(detail_lbl)
            self._menu_slot_details.append(detail_lbl)

        self._menu_group = group
        return group

    def update_menu(self, items, cursor, breadcrumb, book_metadata):
        """Update the RPG inventory menu with current items and cursor."""
        pal = PALETTES[self._palette_index]

        # Title bar
        self._menu_title.text = "- {} -".format(breadcrumb.upper())
        self._menu_title.color = pal['border']

        # Selected slot fill is brighter, others darker
        selected_fill = 0x3a2a2a  # slightly brighter than bg
        normal_fill = pal['bg']

        if not items:
            for i in range(3):
                self._menu_slot_borders[i].fill = pal['bg']
                self._menu_slot_fills[i].fill = pal['bg']
                self._menu_slot_titles[i].text = ''
                self._menu_slot_details[i].text = ''
            self._menu_slot_titles[1].text = '(Empty)'
            self._menu_slot_titles[1].color = pal['text']
            return

        total = len(items)
        if cursor <= 1:
            window_start = 0
            highlighted_slot = cursor
        else:
            window_start = cursor - 1
            highlighted_slot = 1

        for slot_idx in range(3):
            item_idx = window_start + slot_idx
            is_selected = (slot_idx == highlighted_slot)

            border = self._menu_slot_borders[slot_idx]
            fill = self._menu_slot_fills[slot_idx]
            title_lbl = self._menu_slot_titles[slot_idx]
            detail_lbl = self._menu_slot_details[slot_idx]

            if 0 <= item_idx < total:
                node = items[item_idx]
                border.fill = pal['border']
                fill.fill = selected_fill if is_selected else normal_fill
                title_lbl.color = pal['text']
                detail_lbl.color = pal['border']

                if node.book_id is not None:
                    meta = book_metadata[node.book_id]
                    title_lbl.text = meta[0]
                    detail_lbl.text = meta[1]
                elif getattr(node, 'setting_key', None) is not None:
                    title_lbl.text = node.label
                    detail_lbl.text = ''
                else:
                    child_count = len(node.children) if node.children else 0
                    title_lbl.text = node.label
                    detail_lbl.text = "({})".format(child_count)
            else:
                border.fill = pal['bg']
                fill.fill = pal['bg']
                title_lbl.text = ''
                detail_lbl.text = ''
