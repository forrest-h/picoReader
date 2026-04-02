from .state import AppState
from .constants import BTN_CENTER, BTN_UP, BTN_LEFT, BTN_RIGHT, BTN_DOWN, AVAILABLE_FONTS
from .utils import clean_word, load_reading_font
from .settings import set_setting
from .analytics import BookStats, SessionStats
from .skins import SKIN_NAMES
from .animations import ANIMATION_NAMES  # kept for backward compat
from . import recent

# ORP mode cycle: off -> color -> bold -> off
ORP_MODES = [None, 'color', 'bold']
ORP_NAMES = ['off', 'color', 'bold']


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
    """DOWN pressed in reader mode — auto-pauses if playing."""
    if state.playing:
        book.save_place()
        state.playing = False
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


# --- Settings-related handlers (used by Settings menu cycling) ---

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

def _cycle_setting(state, disp, key):
    """Cycle a setting value and update display/state accordingly."""
    if key == 'skin':
        idx = SKIN_NAMES.index(state.skin_name) if state.skin_name in SKIN_NAMES else 0
        idx = (idx + 1) % len(SKIN_NAMES)
        state.skin_name = SKIN_NAMES[idx]
        set_setting(state.settings, 'skin', state.skin_name)
        state.theme_index = 0
        set_setting(state.settings, 'palette', '0')
        disp.set_skin(state.skin_name)
        disp.set_palette(0)
    elif key == 'palette':
        # Enter palette preview mode with live reader preview
        state.mode = AppState.MODE_PALETTE
        disp.set_palette(state.theme_index)
        disp.show_word("picoReader", state.orp_mode)
        p = disp.skin.PALETTES[state.theme_index]
        disp.show_wpm(p.get('name', str(state.theme_index)))
        disp.show_reader_screen()
        return  # Skip menu redraw
    elif key == 'orp':
        idx = ORP_NAMES.index(ORP_NAMES[0] if state.orp_mode is None else state.orp_mode)
        idx = (idx + 1) % len(ORP_NAMES)
        state.orp_mode = ORP_MODES[idx]
        set_setting(state.settings, 'orp', ORP_NAMES[idx])
    elif key.startswith('anim_'):
        anim_name = key[5:]  # e.g., 'walker', 'particles', 'page_turn'
        if anim_name in state.active_animations:
            state.active_animations.discard(anim_name)
            disp.toggle_animation(anim_name)
        else:
            state.active_animations.add(anim_name)
            disp.toggle_animation(anim_name)
        if state.active_animations:
            set_setting(state.settings, 'animation',
                        ','.join(sorted(state.active_animations)))
        else:
            set_setting(state.settings, 'animation', 'off')
    elif key == 'font':
        # Enter font preview mode
        state.mode = AppState.MODE_FONT
        if state.font_name in AVAILABLE_FONTS:
            state.font_preview_idx = AVAILABLE_FONTS.index(state.font_name)
        else:
            state.font_preview_idx = 0
        _preview_font(state, disp)
        return  # Skip menu redraw
    elif key == 'smart_pacing':
        state.smart_pacing = not state.smart_pacing
        set_setting(state.settings, 'smart_pacing', 'on' if state.smart_pacing else 'off')
    elif key == 'brightness':
        # Enter brightness adjustment mode (stay on menu screen)
        state.mode = AppState.MODE_BRIGHTNESS
    elif key == 'games':
        state.mode = AppState.MODE_GAME_SELECT
        state.game_select_cursor = 0
        disp.show_game_select_screen(state.game_select_cursor)
        return


def menu_select(state, book, disp):
    """CENTER in menu: drill into category, select book, or cycle setting."""
    result = state.menu_state.select()
    if result is None:
        # Drilled into a category -- redraw menu
        disp.show_menu_screen(state.menu_state, book.book_metadata)
    elif isinstance(result, str) and result == "setting:stats":
        # Stats screen -- enter stats mode directly
        state.mode = AppState.MODE_STATS
        total_wc = 0
        if book.books and book.book_id < len(book.book_metadata):
            total_wc = book.book_metadata[book.book_id][3]
        disp.show_stats_screen(state.book_stats, state.session_stats,
                               total_wc, state.wpm)
    elif isinstance(result, str) and result.startswith("setting:"):
        # Setting leaf -- cycle the value
        setting_key = result[8:]
        _cycle_setting(state, disp, setting_key)
        # Update the menu item label to show current value
        # (skip if _cycle_setting entered a preview mode)
        if state.mode == AppState.MODE_MENU:
            items = state.menu_state.current_node.children
            node = items[state.menu_state.cursor]
            node.label = _setting_label(state, disp, setting_key)
            disp.show_menu_screen(state.menu_state, book.book_metadata)
    else:
        # A book was selected -- start reading
        book_id = result
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
        disp.set_book_title(book.book_metadata[book_id][0])
        disp.update_progress(book.line_num, book.book_len)
        disp.show_reader_screen()


def _setting_label(state, disp, key):
    """Return display label for a setting showing its current value."""
    if key == 'skin':
        return "Skin: {}".format(state.skin_name)
    elif key == 'palette':
        p = disp.skin.PALETTES[state.theme_index]
        name = p.get('name', str(state.theme_index))
        return "Color: {}".format(name)
    elif key == 'orp':
        return "ORP: {}".format('off' if state.orp_mode is None else state.orp_mode)
    elif key.startswith('anim_'):
        anim_name = key[5:]
        on = anim_name in state.active_animations
        display_name = ' '.join(w[0].upper() + w[1:] for w in anim_name.split('_'))
        return "{}: {}".format(display_name, 'ON' if on else 'off')
    elif key == 'font':
        return "Font: {}".format(state.font_name.split('.')[0])
    elif key == 'smart_pacing':
        return "Smart Pace: {}".format('on' if state.smart_pacing else 'off')
    elif key == 'brightness':
        return "Bright: {}%".format(state.brightness)
    return key

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


# --- Brightness mode handlers ---

def brightness_confirm(state, book, disp):
    """CENTER in brightness mode: confirm and return to settings menu."""
    # Update the menu label to show current value
    items = state.menu_state.current_node.children
    node = items[state.menu_state.cursor]
    node.label = _setting_label(state, disp, 'brightness')
    state.mode = AppState.MODE_MENU
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def brightness_adjust_up(state, book, disp):
    """Encoder CW in brightness mode: increase by 2%."""
    state.brightness = min(100, state.brightness + 2)
    set_setting(state.settings, 'brightness', str(state.brightness))
    disp.set_brightness(state.brightness)
    # Update menu label in-place and redraw menu
    items = state.menu_state.current_node.children
    node = items[state.menu_state.cursor]
    node.label = _setting_label(state, disp, 'brightness')
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def brightness_adjust_down(state, book, disp):
    """Encoder CCW in brightness mode: decrease by 2%."""
    state.brightness = max(1, state.brightness - 2)
    set_setting(state.settings, 'brightness', str(state.brightness))
    disp.set_brightness(state.brightness)
    # Update menu label in-place and redraw menu
    items = state.menu_state.current_node.children
    node = items[state.menu_state.cursor]
    node.label = _setting_label(state, disp, 'brightness')
    disp.show_menu_screen(state.menu_state, book.book_metadata)


# --- Palette preview mode handlers ---

def palette_adjust_up(state, book, disp):
    """Encoder CW in palette mode: next palette."""
    palette_count = len(disp.skin.PALETTES)
    state.theme_index = (state.theme_index + 1) % palette_count
    set_setting(state.settings, 'palette', str(state.theme_index))
    disp.set_palette(state.theme_index)
    disp.show_word("picoReader", state.orp_mode)
    p = disp.skin.PALETTES[state.theme_index]
    disp.show_wpm(p.get('name', str(state.theme_index)))
    disp.refresh()

def palette_adjust_down(state, book, disp):
    """Encoder CCW in palette mode: previous palette."""
    palette_count = len(disp.skin.PALETTES)
    state.theme_index = (state.theme_index - 1) % palette_count
    set_setting(state.settings, 'palette', str(state.theme_index))
    disp.set_palette(state.theme_index)
    disp.show_word("picoReader", state.orp_mode)
    p = disp.skin.PALETTES[state.theme_index]
    disp.show_wpm(p.get('name', str(state.theme_index)))
    disp.refresh()

def palette_confirm(state, book, disp):
    """CENTER/UP in palette mode: confirm and return to menu."""
    items = state.menu_state.current_node.children
    node = items[state.menu_state.cursor]
    node.label = _setting_label(state, disp, 'palette')
    state.mode = AppState.MODE_MENU
    disp.show_menu_screen(state.menu_state, book.book_metadata)


# --- Font preview mode handlers ---

def _preview_font(state, disp):
    """Show current font preview on reader screen."""
    import gc
    gc.collect()
    font_name = AVAILABLE_FONTS[state.font_preview_idx]
    new_font = load_reading_font(font_name)
    disp.set_font(new_font)
    disp.show_reader_screen()
    display_name = font_name.split('.')[0]
    disp.show_word(display_name)
    disp.show_wpm("{}/{}".format(state.font_preview_idx + 1, len(AVAILABLE_FONTS)))
    disp.refresh()

def font_preview_next(state, book, disp):
    """Encoder CW in font mode: next font."""
    state.font_preview_idx = (state.font_preview_idx + 1) % len(AVAILABLE_FONTS)
    _preview_font(state, disp)

def font_preview_prev(state, book, disp):
    """Encoder CCW in font mode: previous font."""
    state.font_preview_idx = (state.font_preview_idx - 1) % len(AVAILABLE_FONTS)
    _preview_font(state, disp)

def font_confirm(state, book, disp):
    """CENTER/UP in font mode: confirm selection and return to menu."""
    font_name = AVAILABLE_FONTS[state.font_preview_idx]
    state.font_name = font_name
    set_setting(state.settings, 'font', font_name)
    items = state.menu_state.current_node.children
    node = items[state.menu_state.cursor]
    node.label = _setting_label(state, disp, 'font')
    state.mode = AppState.MODE_MENU
    disp.show_menu_screen(state.menu_state, book.book_metadata)


# --- Stats mode handlers ---

def stats_dismiss(state, book, disp):
    """CENTER or UP in stats mode: return to settings menu."""
    state.mode = AppState.MODE_MENU
    disp.show_menu_screen(state.menu_state, book.book_metadata)


# --- Game select mode handlers ---

def game_select_confirm(state, book, disp):
    """CENTER in game select: launch selected game."""
    import gc
    from .games import GAME_LIST, launch_game
    name, module_name = GAME_LIST[state.game_select_cursor]
    gc.collect()
    game = launch_game(module_name, disp.display, disp._smallfont)
    if game:
        state.active_game = game
        state.mode = AppState.MODE_GAME
        disp.display.show(game.get_group())
        disp.display.refresh()

def game_select_back(state, book, disp):
    """UP in game select: return to settings menu."""
    state.mode = AppState.MODE_MENU
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def game_select_scroll_down(state, book, disp):
    """Encoder CW in game select."""
    from .games import GAME_LIST
    state.game_select_cursor = (state.game_select_cursor + 1) % len(GAME_LIST)
    disp.show_game_select_screen(state.game_select_cursor)

def game_select_scroll_up(state, book, disp):
    """Encoder CCW in game select."""
    from .games import GAME_LIST
    state.game_select_cursor = (state.game_select_cursor - 1) % len(GAME_LIST)
    disp.show_game_select_screen(state.game_select_cursor)


# --- Game mode handlers ---

def _game_quit(state, disp):
    """Clean up active game and return to game select."""
    import gc
    if state.active_game:
        state.active_game.destroy()
        state.active_game = None
    gc.collect()
    state.mode = AppState.MODE_GAME_SELECT
    disp.show_game_select_screen(state.game_select_cursor)

def game_button_center(state, book, disp):
    if state.active_game:
        result = state.active_game.handle_button(BTN_CENTER)
        if result == 'quit':
            _game_quit(state, disp)
        else:
            disp.display.refresh()

def game_button_up(state, book, disp):
    if state.active_game:
        result = state.active_game.handle_button(BTN_UP)
        if result == 'quit':
            _game_quit(state, disp)
        else:
            disp.display.refresh()

def game_button_left(state, book, disp):
    if state.active_game:
        result = state.active_game.handle_button(BTN_LEFT)
        if result == 'quit':
            _game_quit(state, disp)
        else:
            disp.display.refresh()

def game_button_right(state, book, disp):
    if state.active_game:
        result = state.active_game.handle_button(BTN_RIGHT)
        if result == 'quit':
            _game_quit(state, disp)
        else:
            disp.display.refresh()

def game_button_down(state, book, disp):
    if state.active_game:
        result = state.active_game.handle_button(BTN_DOWN)
        if result == 'quit':
            _game_quit(state, disp)
        else:
            disp.display.refresh()

def game_encoder_up(state, book, disp):
    if state.active_game:
        result = state.active_game.handle_encoder(1)
        if result == 'quit':
            _game_quit(state, disp)
        else:
            disp.display.refresh()

def game_encoder_down(state, book, disp):
    if state.active_game:
        result = state.active_game.handle_encoder(-1)
        if result == 'quit':
            _game_quit(state, disp)
        else:
            disp.display.refresh()


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
    # Menu mode
    (AppState.MODE_MENU, BTN_CENTER): menu_select,
    (AppState.MODE_MENU, BTN_UP):     menu_back,
    # Jump mode
    (AppState.MODE_JUMP, BTN_CENTER): jump_confirm,
    (AppState.MODE_JUMP, BTN_UP):     jump_cancel,
    # Brightness mode
    (AppState.MODE_BRIGHTNESS, BTN_CENTER): brightness_confirm,
    (AppState.MODE_BRIGHTNESS, BTN_UP):     brightness_confirm,
    # Stats mode
    (AppState.MODE_STATS, BTN_CENTER): stats_dismiss,
    (AppState.MODE_STATS, BTN_UP):     stats_dismiss,
    # Palette preview mode
    (AppState.MODE_PALETTE, BTN_CENTER): palette_confirm,
    (AppState.MODE_PALETTE, BTN_UP):     palette_confirm,
    # Font preview mode
    (AppState.MODE_FONT, BTN_CENTER): font_confirm,
    (AppState.MODE_FONT, BTN_UP):     font_confirm,
    # Game select mode
    (AppState.MODE_GAME_SELECT, BTN_CENTER): game_select_confirm,
    (AppState.MODE_GAME_SELECT, BTN_UP):     game_select_back,
    # Game mode
    (AppState.MODE_GAME, BTN_CENTER): game_button_center,
    (AppState.MODE_GAME, BTN_UP):     game_button_up,
    (AppState.MODE_GAME, BTN_LEFT):   game_button_left,
    (AppState.MODE_GAME, BTN_RIGHT):  game_button_right,
    (AppState.MODE_GAME, BTN_DOWN):   game_button_down,
}

ENCODER_HANDLERS = {
    (AppState.MODE_READER, 1):      wpm_up_or_step_fwd,
    (AppState.MODE_READER, -1):     wpm_down_or_step_back,
    (AppState.MODE_MENU, 1):        menu_scroll_down,
    (AppState.MODE_MENU, -1):       menu_scroll_up,
    (AppState.MODE_JUMP, 1):        jump_adjust_up,
    (AppState.MODE_JUMP, -1):       jump_adjust_down,
    (AppState.MODE_BRIGHTNESS, 1):  brightness_adjust_up,
    (AppState.MODE_BRIGHTNESS, -1): brightness_adjust_down,
    (AppState.MODE_PALETTE, 1):     palette_adjust_up,
    (AppState.MODE_PALETTE, -1):    palette_adjust_down,
    (AppState.MODE_FONT, 1):        font_preview_next,
    (AppState.MODE_FONT, -1):       font_preview_prev,
    # Game select mode
    (AppState.MODE_GAME_SELECT, 1):  game_select_scroll_down,
    (AppState.MODE_GAME_SELECT, -1): game_select_scroll_up,
    # Game mode
    (AppState.MODE_GAME, 1):  game_encoder_up,
    (AppState.MODE_GAME, -1): game_encoder_down,
}
