from .state import AppState
from .constants import THEMES, BTN_CENTER, BTN_UP, BTN_LEFT, BTN_RIGHT, BTN_DOWN
from .utils import clean_word
from .analytics import BookStats, SessionStats


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
    book_stats = BookStats(book.book)
    book_stats.start_session()
    state.book_stats = book_stats
    state.session_stats = SessionStats()
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
