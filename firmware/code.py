import board
import digitalio
import rotaryio
import time
import keypad
import busio
import sdcardio
import storage
import displayio
from adafruit_display_text import label
from adafruit_st7735r import ST7735R
from adafruit_bitmap_font import bitmap_font
from adafruit_display_shapes.rect import Rect
import os
import pwmio

# =============================================================================
# Constants
# =============================================================================

DEFAULT_WPM = 200
DEFAULT_BRIGHTNESS = 50
PWM_FREQ = 5000
SAVE_INTERVAL = 50

# BGR format (https://wamingo.net/rgbbgr/)
# Each theme: [background, text, wpm, highlight]
THEMES = [
    [0x000000, 0xe7e7e7, 0x4c4c4c, 0x7c7c7c],
    [0xf3f3f3, 0x000000, 0xa1a1a1, 0x949494],
    [0x696969, 0x000000, 0x272727, 0x403f3f],
    [0x460808, 0xbdbdbd, 0x898888, 0x0e8ee6],
    [0x000000, 0x696969, 0x4c4c4c, 0x696969],
]

# Display geometry
DISPLAY_WIDTH = 160
DISPLAY_HEIGHT = 128
WORD_CENTER = (80, 70)
WPM_POS = (0, 128)
GUIDE_RECTS = [(67, 42, 21, 1), (67, 84, 21, 1), (77, 42, 1, 6), (77, 78, 1, 6)]
MENU_TITLE_POS = (80, 10)
MENU_SLOTS = [(20, 40), (60, 40), (100, 28)]
MENU_SELECT_COLORS = (0x000000, 0xf1f1f1, 0x000000)   # text, bg, border
MENU_OTHER_COLORS = (0x909090, 0x323232, 0x3b3b3b)
MENU_BG = 0x323232

# Pin assignments
PIN_SPI_CLK = board.GP2
PIN_SPI_MOSI = board.GP3
PIN_SPI_MISO = board.GP4
PIN_DISPLAY_DC = board.GP17
PIN_DISPLAY_RST = board.GP18
PIN_DISPLAY_CS = board.GP19
PIN_SD_CS = board.GP15
PIN_ENC_A = board.GP14
PIN_ENC_B = board.GP13
PIN_BACKLIGHT = board.GP16
# 5-way keypad: CENTER, UP, LEFT, RIGHT, DOWN
PIN_BUTTONS = [board.GP11, board.GP9, board.GP10, board.GP8, board.GP6]
BTN_CENTER = 0  # GP11 — select / play / pause
BTN_UP     = 1  # GP9  — back to menu
BTN_LEFT   = 2  # GP10 — previous theme (when paused)
BTN_RIGHT  = 3  # GP8  — next theme (when paused)
BTN_DOWN   = 4  # GP6  — unused
PIN_COM = [board.GP12, board.GP7]


# =============================================================================
# Hardware init
# =============================================================================

def init_hardware():
    # COM pins (unused, set to output)
    for pin in PIN_COM:
        p = digitalio.DigitalInOut(pin)
        p.switch_to_output()

    displayio.release_displays()

    spi = busio.SPI(clock=PIN_SPI_CLK, MOSI=PIN_SPI_MOSI, MISO=PIN_SPI_MISO)
    display_bus = displayio.FourWire(spi, command=PIN_DISPLAY_DC,
                                     chip_select=PIN_DISPLAY_CS, reset=PIN_DISPLAY_RST)
    hw_display = ST7735R(display_bus, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT,
                         rotation=270, colstart=2, rowstart=1, auto_refresh=False)

    sdcard = sdcardio.SDCard(spi, PIN_SD_CS)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, "/sd")

    backlight = pwmio.PWMOut(PIN_BACKLIGHT, frequency=PWM_FREQ,
                             duty_cycle=int(DEFAULT_BRIGHTNESS / 100 * 65535))

    encoder = rotaryio.IncrementalEncoder(PIN_ENC_A, PIN_ENC_B, divisor=2)

    return hw_display, backlight, spi, encoder


# =============================================================================
# Utility functions
# =============================================================================

def parse_book_filename(filename):
    """Parse '(Series) Author - Title (wordcount).txt' into components."""
    try:
        name = filename.rsplit('.', 1)[0]
        parts = name.split(' - ', 1)
        if len(parts) == 2:
            author_part, title_part = parts
            if author_part.startswith('('):
                close = author_part.find(')')
                series = author_part[1:close]
                author = author_part[close+1:].strip()
            else:
                series = ''
                author = author_part.strip()
            paren = title_part.rfind('(')
            if paren != -1:
                title = title_part[:paren].strip()
                wordcount = int(title_part[paren+1:title_part.rfind(')')])
            else:
                title = title_part.strip()
                wordcount = 10000
        else:
            title, author, series, wordcount = name, '', '', 10000
    except (IndexError, ValueError):
        title, author, series, wordcount = filename, '', '', 10000
    return title, author, series, wordcount


def clean_word(word):
    return word.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")


# =============================================================================
# AppState
# =============================================================================

class AppState:
    MODE_MENU = 0
    MODE_READER = 1
    MODE_DISPLAY = 2

    def __init__(self):
        self.mode = self.MODE_MENU
        self.playing = False
        self.finished = False
        self.wpm = DEFAULT_WPM
        self.speed = 60.0 / DEFAULT_WPM
        self.brightness = DEFAULT_BRIGHTNESS
        self.theme_index = 0

    def set_wpm(self, wpm):
        self.wpm = max(10, wpm)
        self.speed = 60.0 / self.wpm


# =============================================================================
# BookReader
# =============================================================================

class BookReader:
    CACHE_LINES = 3

    def __init__(self, books, book_metadata, book_lens):
        self.books = books
        self.book_metadata = book_metadata
        self.book_lens = book_lens
        self.book_id = 0
        self.book = books[0]
        self.book_len = book_lens[0]
        self.line_num = 0
        self.word_idx = 0
        self._cache = []
        self._cache_start = -1

    def _ensure_cached(self, line):
        if self._cache_start <= line < self._cache_start + len(self._cache):
            return
        start = max(0, line - 1)
        self._cache = []
        self._cache_start = start
        with open("/sd/books/{}".format(self.book), 'r') as f:
            for _ in range(start):
                if not f.readline():
                    return
            for _ in range(self.CACHE_LINES):
                text = f.readline()
                if not text:
                    break
                self._cache.append(text.strip().split())

    def _get_words(self, line):
        self._ensure_cached(line)
        idx = line - self._cache_start
        if 0 <= idx < len(self._cache):
            return self._cache[idx]
        return []

    def step_forward(self):
        """Return next word, or None at end of book."""
        while True:
            words = self._get_words(self.line_num)
            if not words:
                self.line_num += 1
                self.word_idx = 0
                words = self._get_words(self.line_num)
                if not words:
                    return None
            if self.word_idx < len(words):
                word = words[self.word_idx]
                self.word_idx += 1
                return word
            self.line_num += 1
            self.word_idx = 0

    def step_backward(self):
        """Return previous word, or None at start of book."""
        self.word_idx -= 1
        if self.word_idx < 0:
            if self.line_num <= 0:
                self.word_idx = 0
                return None
            self.line_num -= 1
            words = self._get_words(self.line_num)
            self.word_idx = max(0, len(words) - 1) if words else 0
        words = self._get_words(self.line_num)
        if words and 0 <= self.word_idx < len(words):
            return words[self.word_idx]
        return None

    def save_place(self):
        with open("saves/save_{}".format(self.book), 'w') as f:
            f.write(str(self.line_num))

    def save_backup(self):
        with open("saves/save_prev_{}".format(self.book), 'w') as f:
            f.write(str(self.line_num))

    def load_place(self):
        try:
            with open("saves/save_{}".format(self.book), 'r') as f:
                self.line_num = int(f.read())
        except (OSError, ValueError):
            self.line_num = 0
        self.word_idx = 0
        self._cache_start = -1
        self._cache = []

    def select_book(self, book_id):
        self.book_id = book_id
        self.book = self.books[book_id]
        self.book_len = self.book_lens[book_id]
        self.load_place()


# =============================================================================
# Display
# =============================================================================

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


# =============================================================================
# Input handlers
# =============================================================================

def toggle_play(state, book, disp):
    if state.finished:
        book.line_num = 0
        book.word_idx = 0
        book._cache_start = -1
        book._cache = []
        book.save_place()
        disp.reset_progress()
        state.finished = False
        state.playing = True
        return
    book.save_place()
    state.playing = not state.playing

def goto_menu(state, book, disp):
    if state.mode == AppState.MODE_READER and state.playing:
        return
    book.save_place()
    state.mode = AppState.MODE_MENU
    disp.show_menu_screen(book.book_metadata, book.book_id, len(book.books))

def goto_display(state, book, disp):
    if state.playing:
        return
    book.save_place()
    state.mode = AppState.MODE_DISPLAY
    disp.show_word("picoReader")
    disp.refresh()

def select_and_play(state, book, disp):
    state.mode = AppState.MODE_READER
    state.playing = True
    state.finished = False
    book.save_backup()
    disp.apply_theme(THEMES[state.theme_index])
    disp.show_reader_screen()

def goto_reader_toggle(state, book, disp):
    state.mode = AppState.MODE_READER
    state.playing = not state.playing
    disp.show_reader_screen()

def cycle_theme_fwd(state, book, disp):
    state.theme_index = (state.theme_index + 1) % len(THEMES)
    disp.apply_theme(THEMES[state.theme_index])
    disp.show_word("picoReader")
    disp.refresh()

def cycle_theme_back(state, book, disp):
    state.theme_index = (state.theme_index - 1) % len(THEMES)
    disp.apply_theme(THEMES[state.theme_index])
    disp.show_word("picoReader")
    disp.refresh()

def wpm_up_or_step_fwd(state, book, disp):
    if state.playing:
        state.set_wpm(state.wpm + 2)
    else:
        word = book.step_forward()
        if word:
            disp.show_word(clean_word(word))
            disp.show_wpm(state.wpm)
            disp.refresh()
            book.save_place()

def wpm_down_or_step_back(state, book, disp):
    if state.playing:
        state.set_wpm(state.wpm - 2)
    else:
        word = book.step_backward()
        if word:
            disp.show_word(clean_word(word))
            disp.show_wpm(state.wpm)
            disp.refresh()
            book.save_place()

def menu_next(state, book, disp):
    book.book_id = (book.book_id + 1) % len(book.books)
    book.select_book(book.book_id)
    disp.show_menu_screen(book.book_metadata, book.book_id, len(book.books))

def menu_prev(state, book, disp):
    book.book_id = (book.book_id - 1) % len(book.books)
    book.select_book(book.book_id)
    disp.show_menu_screen(book.book_metadata, book.book_id, len(book.books))

def brightness_up(state, book, disp):
    state.brightness = min(100, state.brightness + 2)
    disp.set_brightness(state.brightness)

def brightness_down(state, book, disp):
    state.brightness = max(1, state.brightness - 2)
    disp.set_brightness(state.brightness)


# --- Dispatch tables ---

BUTTON_HANDLERS = {
    # Reader mode
    (AppState.MODE_READER, BTN_CENTER): toggle_play,
    (AppState.MODE_READER, BTN_UP):     goto_menu,          # only when paused
    (AppState.MODE_READER, BTN_LEFT):   goto_display,       # only when paused
    (AppState.MODE_READER, BTN_RIGHT):  goto_display,       # only when paused
    # Display mode (theme/brightness)
    (AppState.MODE_DISPLAY, BTN_CENTER): goto_reader_toggle,
    (AppState.MODE_DISPLAY, BTN_UP):     goto_menu,
    (AppState.MODE_DISPLAY, BTN_LEFT):   cycle_theme_back,
    (AppState.MODE_DISPLAY, BTN_RIGHT):  cycle_theme_fwd,
    # Menu mode
    (AppState.MODE_MENU, BTN_CENTER): select_and_play,
}

ENCODER_HANDLERS = {
    (AppState.MODE_READER, 1): wpm_up_or_step_fwd,
    (AppState.MODE_READER, -1): wpm_down_or_step_back,
    (AppState.MODE_MENU, 1): menu_next,
    (AppState.MODE_MENU, -1): menu_prev,
    (AppState.MODE_DISPLAY, 1): brightness_up,
    (AppState.MODE_DISPLAY, -1): brightness_down,
}


# =============================================================================
# Main loop
# =============================================================================

def main_loop(state, book, disp, keys, encoder):
    last_enc_pos = encoder.position
    last_word_time = 0.0
    lines_since_save = 0
    last_line = book.line_num

    while True:
        now = time.monotonic()

        # --- Buttons ---
        event = keys.events.get()
        if event and event.pressed:
            handler = BUTTON_HANDLERS.get((state.mode, event.key_number))
            if handler:
                handler(state, book, disp)

        # --- Encoder ---
        enc_pos = encoder.position
        if enc_pos != last_enc_pos:
            direction = 1 if enc_pos > last_enc_pos else -1
            handler = ENCODER_HANDLERS.get((state.mode, direction))
            if handler:
                handler(state, book, disp)
            last_enc_pos = enc_pos

        # --- Word display timer ---
        if state.mode == AppState.MODE_READER and state.playing:
            if now - last_word_time >= state.speed:
                word = book.step_forward()
                if word:
                    cleaned = clean_word(word)
                    if len(cleaned) > 17:
                        for part in cleaned.split('-'):
                            disp.show_word(part + '-')
                            disp.show_wpm(state.wpm)
                            disp.refresh()
                    else:
                        disp.show_word(cleaned)
                        disp.show_wpm(state.wpm)
                        disp.refresh()

                    # Auto-save and progress update
                    if book.line_num != last_line:
                        lines_since_save += book.line_num - last_line
                        last_line = book.line_num
                        if lines_since_save >= SAVE_INTERVAL:
                            book.save_place()
                            disp.update_progress(book.line_num, book.book_len)
                            disp.refresh()
                            lines_since_save = 0
                else:
                    # End of book
                    state.playing = False
                    state.finished = True
                    book.save_place()
                    disp.show_word("End of Book")
                    disp.show_wpm(state.wpm)
                    disp.refresh()

                last_word_time = now

        time.sleep(0.01)


# =============================================================================
# Entry point
# =============================================================================

def main():
    hw_display, backlight, spi, encoder = init_hardware()

    font = bitmap_font.load_font("fonts/Toronto_14.pcf")
    smallfont = bitmap_font.load_font("fonts/Toronto_9.pcf")

    books = [x for x in os.listdir("/sd/books/") if x.endswith('.txt')]

    if not books:
        # Show error and halt
        splash = displayio.Group()
        hw_display.show(splash)
        bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        pal = displayio.Palette(1)
        pal[0] = 0x000000
        splash.append(displayio.TileGrid(bmp, pixel_shader=pal))
        err_label = label.Label(font, text="{:^30}".format("No books found"),
                                color=0xe7e7e7, base_alignment=False)
        err_label.anchor_point = (0.5, 1)
        err_label.anchored_position = WORD_CENTER
        splash.append(err_label)
        hw_display.refresh()
        while True:
            pass

    metadata = [parse_book_filename(b) for b in books]
    lens = [m[3] for m in metadata]

    state = AppState()
    book = BookReader(books, metadata, lens)
    book.load_place()
    disp = Display(hw_display, backlight, font, smallfont)
    disp.show_menu_screen(metadata, 0, len(books))

    with keypad.Keys(PIN_BUTTONS, value_when_pressed=False, pull=True) as keys:
        main_loop(state, book, disp, keys, encoder)


main()
