import time
import os
import keypad
import displayio
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font
from .constants import (PIN_BUTTONS, SAVE_INTERVAL, DISPLAY_WIDTH, DISPLAY_HEIGHT,
    WORD_CENTER, DEFAULT_WPM)
from .hardware import init_hardware
from .state import AppState, calculate_word_delay
from .book_reader import BookReader
from .display import Display
from .input_handlers import BUTTON_HANDLERS, ENCODER_HANDLERS
from .utils import parse_book_filename, clean_word
from .settings import load_settings
from . import menu as menu_mod
from . import recent


def main_loop(state, book, disp, keys, encoder):
    last_enc_pos = encoder.position
    last_word_time = 0.0
    lines_since_save = 0
    last_line = book.line_num
    prev_line_empty = False

    while True:
        now = time.monotonic()

        # --- Buttons ---
        event = keys.events.get()
        if event and event.pressed:
            handler = BUTTON_HANDLERS.get((state.mode, event.key_number))
            if handler:
                handler(state, book, disp)
            # Update cursor visibility after button handling
            disp.set_cursor_visible(not state.playing)

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
            # Calculate delay: smart pacing or flat rate
            if state.smart_pacing:
                word_delay = state._next_word_delay
            else:
                word_delay = state.speed

            if now - last_word_time >= word_delay:
                word = book.step_forward()
                if word:
                    cleaned = clean_word(word)

                    # Detect paragraph start: first word on a line that
                    # follows an empty line
                    is_para_start = (book.word_idx == 1
                                     and book.line_num > 0
                                     and prev_line_empty)

                    # Pre-compute delay for the NEXT iteration so the
                    # current word's complexity determines how long it
                    # stays on screen.
                    if state.smart_pacing:
                        ramp = state.get_ramp_factor()
                        state._next_word_delay = calculate_word_delay(
                            cleaned, state.wpm, is_para_start, ramp)
                    else:
                        state._next_word_delay = state.speed

                    # Track whether this line is empty (for next
                    # paragraph-start detection)
                    prev_line_empty = (book._get_words(book.line_num) == [])

                    if len(cleaned) > 17:
                        for part in cleaned.split('-'):
                            disp.show_word(part + '-', state.orp_mode)
                            disp.show_wpm(state.wpm)
                            disp.tick_animation(state, book)
                            disp.refresh()
                    else:
                        disp.show_word(cleaned, state.orp_mode)
                        disp.show_wpm(state.wpm)
                        disp.tick_animation(state, book)
                        disp.refresh()

                    # Track analytics
                    if state.book_stats:
                        state.book_stats.increment_word()
                    if state.session_stats:
                        state.session_stats.record_word(state.wpm)

                    # Auto-save and progress update
                    if book.line_num != last_line:
                        lines_since_save += book.line_num - last_line
                        last_line = book.line_num
                        if lines_since_save >= SAVE_INTERVAL:
                            book.save_place()
                            if state.book_stats:
                                state.book_stats.save()
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

    settings = load_settings()
    state = AppState(settings=settings)
    book = BookReader(books, metadata, lens)
    book.load_place()

    # Build menu tree
    recent_filenames = recent.load_recent()
    root = menu_mod.build_menu_tree(books, metadata, recent_filenames)
    state.menu_state = menu_mod.MenuState(root)

    disp = Display(hw_display, backlight, font, smallfont,
                   skin_name=state.skin_name)
    disp.set_brightness(state.brightness)
    disp.show_menu_screen(state.menu_state, metadata)

    with keypad.Keys(PIN_BUTTONS, value_when_pressed=False, pull=True) as keys:
        main_loop(state, book, disp, keys, encoder)
