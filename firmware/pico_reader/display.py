import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from .constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT, MENU_TITLE_POS,
    MENU_SLOTS, MENU_SELECT_COLORS, MENU_OTHER_COLORS, MENU_BG)
from .skins import load_skin
from .animations import load_animation


class Display:
    def __init__(self, hw_display, backlight, font, smallfont, skin_name='default'):
        self.display = hw_display
        self.backlight = backlight
        self._font = font
        self._smallfont = smallfont
        self._animation = None
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

    def set_cursor_visible(self, visible):
        """Set cursor visibility if the skin supports it."""
        if hasattr(self.skin, 'set_cursor_visible'):
            self.skin.set_cursor_visible(visible)

    # --- Animation lifecycle ---

    def set_animation(self, name):
        """Swap the active animation. Remove old elements, add new ones."""
        # Remove old animation elements (everything past index 7)
        while len(self.reader_group) > 8:
            self.reader_group.pop()
        if self._animation is not None:
            self._animation.destroy()
            self._animation = None

        anim = load_animation(name)
        if anim is not None:
            elements = anim.build(self)
            for elem in elements:
                self.reader_group.append(elem)
            self._animation = anim

    def tick_animation(self, state, book):
        """Called after each word display, before refresh."""
        if self._animation is not None:
            self._animation.tick(state, book, self)

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

    def _clear_menu_slots(self):
        """Clear all menu slot labels."""
        for rect, slot_labels in self._menu_slots:
            rect.fill = MENU_BG
            rect.outline = 0x3b3b3b
            for lbl in slot_labels:
                lbl.text = ''
                lbl.color = 0x909090

    def show_menu_screen(self, menu_state, book_metadata):
        """Update menu group from MenuState and refresh display.

        Args:
            menu_state: MenuState instance with current position
            book_metadata: full metadata list for resolving book details
        """
        items, cursor = menu_state.visible_items()
        breadcrumb_text = menu_state.breadcrumb()

        # Update title bar
        self.menu_group[1].text = breadcrumb_text

        # Empty category
        if not items:
            self._clear_menu_slots()
            self._menu_slots[1][1][0].text = "(Empty)"
            self.display.show(self.menu_group)
            self.display.refresh()
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
            rect, slot_labels = self._menu_slots[slot_idx]
            is_selected = (slot_idx == highlighted_slot)
            txt_c, bg_c, bdr_c = MENU_SELECT_COLORS if is_selected else MENU_OTHER_COLORS
            rect.fill = bg_c
            rect.outline = bdr_c
            for lbl in slot_labels:
                lbl.color = txt_c

            if 0 <= item_idx < total:
                node = items[item_idx]
                if node.book_id is not None:
                    # Book leaf -- show title + author
                    meta = book_metadata[node.book_id]
                    slot_labels[0].text = meta[0]  # title
                    slot_labels[1].text = meta[1]  # author
                    slot_labels[2].text = meta[2] if slot_idx < 2 else ''  # series
                else:
                    # Category node -- show label only
                    slot_labels[0].text = node.label
                    child_count = len(node.children) if node.children else 0
                    slot_labels[1].text = "({})".format(child_count)
                    slot_labels[2].text = ''
            else:
                for lbl in slot_labels:
                    lbl.text = ''

        self.display.show(self.menu_group)
        self.display.refresh()

    # --- Jump mode display ---

    def show_jump_screen(self, pct):
        """Show jump mode overlay: 'Jump: XX%' centered on reader screen."""
        self.skin.show_word("Jump: {}%".format(pct))
        self.skin.show_wpm("CENTER=go UP=cancel")
        self.display.show(self.reader_group)
        self.display.refresh()

    # --- Brightness ---

    def set_brightness(self, brightness):
        self.backlight.duty_cycle = int(brightness / 100 * 65535)

    def refresh(self):
        self.display.refresh()
