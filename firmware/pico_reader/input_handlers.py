from .state import AppState
from .constants import BTN_CENTER, BTN_UP, BTN_LEFT, BTN_RIGHT, BTN_DOWN, AVAILABLE_FONTS
from .utils import clean_word, load_reading_font
from .settings import set_setting
from .analytics import BookStats, SessionStats
from . import recent

# ORP mode cycle: off -> color -> bold -> off
ORP_MODES = [None, 'color', 'bold']


# --- Reader mode handlers ---

def toggle_play(state, book, disp):
    if state.finished:
        book.line_num = 0
        book.word_idx = 0
        book._cache_start = -1
        book._cache = []
        book.save_place()
        disp.reset_progress()
        state.finished = False
        state.start_playing()
        return
    if state.playing:
        book.save_place()
        state.playing = False
    else:
        state.start_playing()

def goto_menu(state, book, disp):
    if state.mode == AppState.MODE_READER and state.playing:
        return
    book.save_place()
    state.mode = AppState.MODE_MENU
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def prev_chapter(state, book, disp):
    """LEFT when paused: jump to previous chapter."""
    if state.playing:
        return
    title = book.jump_to_chapter(-1)
    if title is None:
        return
    book.save_place()
    disp.show_word(title[:17])
    disp.refresh()

def next_chapter(state, book, disp):
    """RIGHT when paused: jump to next chapter."""
    if state.playing:
        return
    title = book.jump_to_chapter(1)
    if title is None:
        return
    book.save_place()
    disp.show_word(title[:17])
    disp.refresh()

def enter_jump_mode(state, book, disp):
    """DOWN pressed while paused in reader mode."""
    if state.playing:
        return
    if book.book_len > 0:
        state.jump_pct = int(book.line_num * 100 / book.book_len)
    else:
        state.jump_pct = 0
    state.jump_pct = max(0, min(100, state.jump_pct))
    state.mode = AppState.MODE_JUMP
    disp.show_jump_screen(state.jump_pct)

def wpm_up_or_step_fwd(state, book, disp):
    if state.playing:
        state.set_wpm(state.wpm + 2)
    else:
        word = book.step_forward()
        if word:
            disp.show_word(clean_word(word), state.orp_mode)
            disp.show_wpm(state.wpm)
            disp.refresh()
            book.save_place()

def wpm_down_or_step_back(state, book, disp):
    if state.playing:
        state.set_wpm(state.wpm - 2)
    else:
        word = book.step_backward()
        if word:
            disp.show_word(clean_word(word), state.orp_mode)
            disp.show_wpm(state.wpm)
            disp.refresh()
            book.save_place()


# --- Display mode handlers (kept for backward compat, used by Phase 3 Settings) ---

def goto_display(state, book, disp):
    if state.playing:
        return
    book.save_place()
    state.mode = AppState.MODE_DISPLAY
    disp.show_word("picoReader")
    disp.refresh()

def goto_reader_toggle(state, book, disp):
    state.mode = AppState.MODE_READER
    state.playing = not state.playing
    disp.show_reader_screen()

def cycle_theme_fwd(state, book, disp):
    palette_count = len(disp.skin.PALETTES)
    state.theme_index = (state.theme_index + 1) % palette_count
    disp.set_palette(state.theme_index)
    disp.show_word("picoReader")
    disp.refresh()

def cycle_theme_back(state, book, disp):
    palette_count = len(disp.skin.PALETTES)
    state.theme_index = (state.theme_index - 1) % palette_count
    disp.set_palette(state.theme_index)
    disp.show_word("picoReader")
    disp.refresh()

def brightness_up(state, book, disp):
    state.brightness = min(100, state.brightness + 2)
    disp.set_brightness(state.brightness)

def brightness_down(state, book, disp):
    state.brightness = max(1, state.brightness - 2)
    disp.set_brightness(state.brightness)

def cycle_font(state, book, disp):
    current = state.font_name
    if current in AVAILABLE_FONTS:
        idx = AVAILABLE_FONTS.index(current)
    else:
        idx = 0
    idx = (idx + 1) % len(AVAILABLE_FONTS)
    state.font_name = AVAILABLE_FONTS[idx]
    set_setting(state.settings, 'font', state.font_name)
    # Load new font and mark display for rebuild on next show_reader_screen()
    new_font = load_reading_font(state.font_name)
    disp.set_font(new_font)
    # Preview: show font name (without extension) in current font
    disp.show_word(state.font_name.split('.')[0])
    disp.refresh()


# --- Menu mode handlers ---

def menu_select(state, book, disp):
    """CENTER in menu: drill into category or select book."""
    book_id = state.menu_state.select()
    if book_id is not None:
        # A book was selected -- start reading
        book.select_book(book_id)
        recent.update_recent(book.book)
        state.menu_state.refresh_recent(book.books, book.book_metadata, recent.load_recent())
        state.mode = AppState.MODE_READER
        state.start_playing()
        state.finished = False
        book.save_backup()
        book_stats = BookStats(book.book)
        book_stats.start_session()
        state.book_stats = book_stats
        state.session_stats = SessionStats()
        disp.set_palette(state.theme_index)
        disp.show_reader_screen()
    else:
        # Drilled into a category -- redraw menu
        disp.show_menu_screen(state.menu_state, book.book_metadata)

def menu_back(state, book, disp):
    """UP in menu: go back one level."""
    state.menu_state.back()
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def menu_scroll_down(state, book, disp):
    """Encoder CW in menu: scroll down."""
    state.menu_state.scroll(1)
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def menu_scroll_up(state, book, disp):
    """Encoder CCW in menu: scroll up."""
    state.menu_state.scroll(-1)
    disp.show_menu_screen(state.menu_state, book.book_metadata)


# --- Jump mode handlers ---

def jump_confirm(state, book, disp):
    """CENTER in jump mode: jump to position and return to reader."""
    target_line = int(book.book_len * state.jump_pct / 100)
    book.line_num = target_line
    book.word_idx = 0
    book._cache_start = -1
    book._cache = []
    book._update_chapter_index()
    book.save_place()
    state.mode = AppState.MODE_READER
    word = book.step_forward()
    if word:
        disp.show_word(clean_word(word))
    disp.show_wpm(state.wpm)
    disp.update_progress(book.line_num, book.book_len)
    disp.show_reader_screen()

def jump_cancel(state, book, disp):
    """UP in jump mode: cancel and return to reader."""
    state.mode = AppState.MODE_READER
    disp.show_reader_screen()

def jump_adjust_up(state, book, disp):
    """Encoder CW in jump mode: increase by 5%."""
    state.jump_pct = min(100, state.jump_pct + 5)
    disp.show_jump_screen(state.jump_pct)

def jump_adjust_down(state, book, disp):
    """Encoder CCW in jump mode: decrease by 5%."""
    state.jump_pct = max(0, state.jump_pct - 5)
    disp.show_jump_screen(state.jump_pct)


# --- Legacy handlers (kept as aliases for backward compatibility) ---

def select_and_play(state, book, disp):
    state.mode = AppState.MODE_READER
    state.playing = True
    state.finished = False
    book.save_backup()
    disp.set_palette(state.theme_index)
    disp.show_reader_screen()

def menu_next(state, book, disp):
    book.book_id = (book.book_id + 1) % len(book.books)
    book.select_book(book.book_id)
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def menu_prev(state, book, disp):
    book.book_id = (book.book_id - 1) % len(book.books)
    book.select_book(book.book_id)
    disp.show_menu_screen(state.menu_state, book.book_metadata)


# --- Dispatch tables ---

BUTTON_HANDLERS = {
    # Reader mode
    (AppState.MODE_READER, BTN_CENTER): toggle_play,
    (AppState.MODE_READER, BTN_UP):     goto_menu,
    (AppState.MODE_READER, BTN_LEFT):   prev_chapter,
    (AppState.MODE_READER, BTN_RIGHT):  next_chapter,
    (AppState.MODE_READER, BTN_DOWN):   enter_jump_mode,
    # Display mode (theme/brightness/font)
    (AppState.MODE_DISPLAY, BTN_CENTER): goto_reader_toggle,
    (AppState.MODE_DISPLAY, BTN_UP):     goto_menu,
    (AppState.MODE_DISPLAY, BTN_LEFT):   cycle_theme_back,
    (AppState.MODE_DISPLAY, BTN_RIGHT):  cycle_theme_fwd,
    (AppState.MODE_DISPLAY, BTN_DOWN):   cycle_font,
    # Menu mode
    (AppState.MODE_MENU, BTN_CENTER): menu_select,
    (AppState.MODE_MENU, BTN_UP):     menu_back,
    # Jump mode
    (AppState.MODE_JUMP, BTN_CENTER): jump_confirm,
    (AppState.MODE_JUMP, BTN_UP):     jump_cancel,
}

ENCODER_HANDLERS = {
    (AppState.MODE_READER, 1):  wpm_up_or_step_fwd,
    (AppState.MODE_READER, -1): wpm_down_or_step_back,
    (AppState.MODE_MENU, 1):    menu_scroll_down,
    (AppState.MODE_MENU, -1):   menu_scroll_up,
    (AppState.MODE_JUMP, 1):    jump_adjust_up,
    (AppState.MODE_JUMP, -1):   jump_adjust_down,
}
