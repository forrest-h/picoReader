import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from .constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT, MENU_TITLE_POS,
    MENU_SLOTS, MENU_SELECT_COLORS, MENU_OTHER_COLORS, MENU_BG)
from .skins import load_skin


class Display:
    def __init__(self, hw_display, backlight, font, smallfont, skin_name='default'):
        self.display = hw_display
        self.backlight = backlight
        self._font = font
        self._smallfont = smallfont
        self._font_dirty = False
        self._set_skin(skin_name)
        self._build_menu_group()

    def _set_skin(self, skin_name):
        SkinClass = load_skin(skin_name)
        self.skin = SkinClass(self._font, self._smallfont)
        self.reader_group = self.skin.build_group(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self._font_dirty = False

    def set_font(self, font):
        """Set a new reading font. Takes effect on next show_reader_screen()."""
        self._font = font
        self._font_dirty = True

    def _build_menu_group(self):
        self.menu_group = displayio.Group()

        # [0] background
        menu_bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        self._menu_bg_palette = displayio.Palette(1)
        self._menu_bg_palette[0] = MENU_BG
        self.menu_group.append(
            displayio.TileGrid(menu_bmp, pixel_shader=self._menu_bg_palette))

        # [1] title
        title_lbl = label.Label(self._font, text='picoReader', color=0xffffff,
                                base_alignment=False)
        title_lbl.anchor_point = (0.5, 0.5)
        title_lbl.anchored_position = MENU_TITLE_POS
        self.menu_group.append(title_lbl)

        # [2..] 3 slots: each has 1 rect + 3 labels (title, author, series)
        self._menu_slots = []
        for y, h in MENU_SLOTS:
            rect = Rect(4, y, 152, h, fill=MENU_BG, outline=0x3b3b3b, stroke=2)
            self.menu_group.append(rect)
            slot_labels = []
            for offset in [10, 20, 30]:
                lbl = label.Label(self._smallfont, text='', color=0x909090,
                                  base_alignment=True)
                lbl.anchor_point = (0.5, 0.5)
                lbl.anchored_position = (80, y + offset)
                self.menu_group.append(lbl)
                slot_labels.append(lbl)
            self._menu_slots.append((rect, slot_labels))

    # --- Reader display (delegated to skin) ---

    def show_word(self, word, orp_mode=None):
        self.skin.show_word(word, orp_mode)

    def show_wpm(self, wpm):
        self.skin.show_wpm(wpm)

    def update_progress(self, line_num, book_len):
        if book_len > 0:
            self.skin.update_progress(line_num / book_len)

    def reset_progress(self):
        self.skin.reset_progress()

    def set_palette(self, index):
        """Apply a palette by index to the current skin."""
        self.skin.apply_palette(index)

    def set_skin(self, skin_name):
        """Switch to a different skin."""
        self._set_skin(skin_name)

    def show_reader_screen(self):
        if self._font_dirty:
            palette_idx = self.skin._palette_index
            self.skin = self.skin.__class__(self._font, self._smallfont)
            self.reader_group = self.skin.build_group(DISPLAY_WIDTH, DISPLAY_HEIGHT)
            self.skin.apply_palette(palette_idx)
            self._font_dirty = False
        self.display.show(self.reader_group)
        self.display.refresh()

    # --- Menu display ---

    def show_menu_screen(self, book_metadata, selected, total):
        if selected <= 1:
            indices = [0, 1, 2]
            highlighted = selected
        else:
            indices = [selected - 1, selected, selected + 1]
            highlighted = 1

        for slot_idx, (rect, slot_labels) in enumerate(self._menu_slots):
            book_idx = indices[slot_idx]
            is_selected = (slot_idx == highlighted)
            txt_c, bg_c, bdr_c = MENU_SELECT_COLORS if is_selected else MENU_OTHER_COLORS
            rect.fill = bg_c
            rect.outline = bdr_c
            for lbl in slot_labels:
                lbl.color = txt_c

            if 0 <= book_idx < total:
                title, author, series = book_metadata[book_idx][:3]
                slot_labels[0].text = title
                slot_labels[1].text = author
                # Third slot is shorter -- no room for series
                slot_labels[2].text = series if slot_idx < 2 else ''
            else:
                for lbl in slot_labels:
                    lbl.text = ''

        self.display.show(self.menu_group)
        self.display.refresh()

    # --- Brightness ---

    def set_brightness(self, brightness):
        self.backlight.duty_cycle = int(brightness / 100 * 65535)

    def refresh(self):
        self.display.refresh()
