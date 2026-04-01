import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from .constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT, WORD_CENTER, WPM_POS,
    GUIDE_RECTS, THEMES, DEFAULT_WPM, MENU_TITLE_POS, MENU_SLOTS,
    MENU_SELECT_COLORS, MENU_OTHER_COLORS, MENU_BG)


class Display:
    def __init__(self, hw_display, backlight, font, smallfont):
        self.display = hw_display
        self.backlight = backlight
        self._font = font
        self._smallfont = smallfont
        self._last_progress_width = 0
        self._build_reader_group()
        self._build_menu_group()

    def _build_reader_group(self):
        self.reader_group = displayio.Group()

        # [0] background
        bg_bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        self._bg_palette = displayio.Palette(1)
        self._bg_palette[0] = THEMES[0][0]
        self.reader_group.append(displayio.TileGrid(bg_bmp, pixel_shader=self._bg_palette))

        # [1] word label
        self._word_label = label.Label(self._font, text="{:^30}".format(''),
                                       color=THEMES[0][1], base_alignment=False)
        self._word_label.anchor_point = (0.5, 1)
        self._word_label.anchored_position = WORD_CENTER
        self.reader_group.append(self._word_label)

        # [2-5] guide rects
        self._guides = []
        for x, y, w, h in GUIDE_RECTS:
            r = Rect(x, y, w, h, fill=THEMES[0][3])
            self._guides.append(r)
            self.reader_group.append(r)

        # [6] progress bar — Bitmap avoids Rect replacement
        self._progress_bmp = displayio.Bitmap(DISPLAY_WIDTH, 2, 2)
        self._progress_palette = displayio.Palette(2)
        self._progress_palette[0] = THEMES[0][0]
        self._progress_palette[1] = THEMES[0][3]
        self.reader_group.append(
            displayio.TileGrid(self._progress_bmp, pixel_shader=self._progress_palette))

        # [7] WPM label
        self._wpm_label = label.Label(self._smallfont, text=str(DEFAULT_WPM),
                                      color=THEMES[0][2], base_alignment=False)
        self._wpm_label.anchor_point = (0.0, 1.0)
        self._wpm_label.anchored_position = WPM_POS
        self.reader_group.append(self._wpm_label)

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

    # --- Reader display ---

    def show_word(self, word):
        self._word_label.text = "{:^30}".format(word)

    def show_wpm(self, wpm):
        self._wpm_label.text = str(wpm)

    def update_progress(self, line_num, book_len):
        if book_len <= 0:
            return
        width = max(1, int(line_num / book_len * DISPLAY_WIDTH))
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
        for x in range(self._last_progress_width):
            self._progress_bmp[x, 0] = 0
            self._progress_bmp[x, 1] = 0
        self._last_progress_width = 0

    def apply_theme(self, theme):
        bg, text, wpm, highlight = theme
        self._bg_palette[0] = bg
        self._word_label.color = text
        self._wpm_label.color = wpm
        for g in self._guides:
            g.fill = highlight
        self._progress_palette[0] = bg
        self._progress_palette[1] = highlight

    def show_reader_screen(self):
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
                # Third slot is shorter — no room for series
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
