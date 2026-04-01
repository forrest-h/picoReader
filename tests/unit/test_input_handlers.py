"""Tests for input_handlers dispatch tables and key handler functions."""
import pytest
from unittest.mock import MagicMock, patch

from pico_reader.state import AppState
from pico_reader.constants import BTN_CENTER, BTN_UP, BTN_LEFT, BTN_RIGHT, BTN_DOWN
from pico_reader.menu import MenuNode, MenuState
from pico_reader.input_handlers import (
    BUTTON_HANDLERS, ENCODER_HANDLERS,
    toggle_play, menu_select, brightness_confirm,
    brightness_adjust_up, brightness_adjust_down,
    goto_menu, prev_chapter, next_chapter, enter_jump_mode,
    wpm_up_or_step_fwd, wpm_down_or_step_back,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides):
    """Create an AppState with sensible defaults for testing."""
    state = AppState()
    for k, v in overrides.items():
        setattr(state, k, v)
    return state


def _make_mocks():
    """Return (state, book_mock, disp_mock) with useful defaults."""
    state = _make_state()
    book = MagicMock()
    book.book = "test_book.txt"
    book.books = ["test_book.txt"]
    book.book_metadata = [("Title", "Author", "", 1000, "")]
    book.book_len = 1000
    book.line_num = 500
    book.word_idx = 0
    disp = MagicMock()
    # Give the mock skin a PALETTES attribute for cycle_theme handlers
    disp.skin = MagicMock()
    disp.skin.PALETTES = [
        {'name': 'A', 'bg': 0, 'text': 0, 'wpm': 0, 'highlight': 0},
        {'name': 'B', 'bg': 0, 'text': 0, 'wpm': 0, 'highlight': 0},
    ]
    return state, book, disp


# ---------------------------------------------------------------------------
# Dispatch table coverage
# ---------------------------------------------------------------------------

class TestButtonHandlers:
    def test_has_reader_center(self):
        assert (AppState.MODE_READER, BTN_CENTER) in BUTTON_HANDLERS

    def test_has_reader_up(self):
        assert (AppState.MODE_READER, BTN_UP) in BUTTON_HANDLERS

    def test_has_reader_left(self):
        assert (AppState.MODE_READER, BTN_LEFT) in BUTTON_HANDLERS

    def test_has_reader_right(self):
        assert (AppState.MODE_READER, BTN_RIGHT) in BUTTON_HANDLERS

    def test_has_reader_down(self):
        assert (AppState.MODE_READER, BTN_DOWN) in BUTTON_HANDLERS

    def test_has_menu_center(self):
        assert (AppState.MODE_MENU, BTN_CENTER) in BUTTON_HANDLERS

    def test_has_menu_up(self):
        assert (AppState.MODE_MENU, BTN_UP) in BUTTON_HANDLERS

    def test_has_jump_center(self):
        assert (AppState.MODE_JUMP, BTN_CENTER) in BUTTON_HANDLERS

    def test_has_jump_up(self):
        assert (AppState.MODE_JUMP, BTN_UP) in BUTTON_HANDLERS

    def test_has_brightness_center(self):
        assert (AppState.MODE_BRIGHTNESS, BTN_CENTER) in BUTTON_HANDLERS

    def test_has_brightness_up(self):
        assert (AppState.MODE_BRIGHTNESS, BTN_UP) in BUTTON_HANDLERS

    def test_all_handlers_callable(self):
        for key, handler in BUTTON_HANDLERS.items():
            assert callable(handler), f"Handler for {key} is not callable"


class TestEncoderHandlers:
    def test_has_reader_cw(self):
        assert (AppState.MODE_READER, 1) in ENCODER_HANDLERS

    def test_has_reader_ccw(self):
        assert (AppState.MODE_READER, -1) in ENCODER_HANDLERS

    def test_has_menu_cw(self):
        assert (AppState.MODE_MENU, 1) in ENCODER_HANDLERS

    def test_has_menu_ccw(self):
        assert (AppState.MODE_MENU, -1) in ENCODER_HANDLERS

    def test_has_jump_cw(self):
        assert (AppState.MODE_JUMP, 1) in ENCODER_HANDLERS

    def test_has_jump_ccw(self):
        assert (AppState.MODE_JUMP, -1) in ENCODER_HANDLERS

    def test_has_brightness_cw(self):
        assert (AppState.MODE_BRIGHTNESS, 1) in ENCODER_HANDLERS

    def test_has_brightness_ccw(self):
        assert (AppState.MODE_BRIGHTNESS, -1) in ENCODER_HANDLERS

    def test_all_handlers_callable(self):
        for key, handler in ENCODER_HANDLERS.items():
            assert callable(handler), f"Handler for {key} is not callable"


# ---------------------------------------------------------------------------
# toggle_play
# ---------------------------------------------------------------------------

class TestTogglePlay:
    def test_not_playing_calls_start_playing(self):
        state, book, disp = _make_mocks()
        state.playing = False
        state.finished = False
        with patch.object(state, 'start_playing') as mock_start:
            toggle_play(state, book, disp)
            mock_start.assert_called_once()

    def test_playing_saves_and_stops(self):
        state, book, disp = _make_mocks()
        state.playing = True
        state.finished = False
        toggle_play(state, book, disp)
        book.save_place.assert_called_once()
        assert state.playing is False

    def test_finished_resets_position_and_starts(self):
        state, book, disp = _make_mocks()
        state.finished = True
        state.playing = False
        book.line_num = 500
        book.word_idx = 10
        with patch.object(state, 'start_playing') as mock_start:
            toggle_play(state, book, disp)
            assert book.line_num == 0
            assert book.word_idx == 0
            book.save_place.assert_called_once()
            disp.reset_progress.assert_called_once()
            assert state.finished is False
            mock_start.assert_called_once()

    def test_finished_clears_cache(self):
        state, book, disp = _make_mocks()
        state.finished = True
        book._cache_start = 100
        book._cache = ["some", "words"]
        with patch.object(state, 'start_playing'):
            toggle_play(state, book, disp)
        assert book._cache_start == -1
        assert book._cache == []


# ---------------------------------------------------------------------------
# menu_select
# ---------------------------------------------------------------------------

class TestMenuSelect:
    def test_book_id_selected(self):
        """When menu_state.select() returns an int, start reading that book."""
        state, book, disp = _make_mocks()
        state.mode = AppState.MODE_MENU

        # Build a menu with a single book leaf
        root = MenuNode("Root", children=[
            MenuNode("Recently Read", children=[]),
            MenuNode("Book A", book_id=0),
        ])
        state.menu_state = MenuState(root)
        state.menu_state.cursor = 1  # Point at the book leaf

        with patch('pico_reader.input_handlers.recent') as mock_recent, \
             patch('pico_reader.input_handlers.BookStats') as MockBookStats, \
             patch('pico_reader.input_handlers.SessionStats') as MockSessionStats:
            mock_recent.load_recent.return_value = []
            mock_book_stats = MagicMock()
            MockBookStats.return_value = mock_book_stats
            mock_session_stats = MagicMock()
            MockSessionStats.return_value = mock_session_stats

            menu_select(state, book, disp)

        book.select_book.assert_called_once_with(0)
        assert state.mode == AppState.MODE_READER
        assert state.finished is False
        book.save_backup.assert_called_once()
        disp.set_palette.assert_called_once_with(state.theme_index)
        disp.show_reader_screen.assert_called_once()

    def test_setting_key_returned(self):
        """When menu_state.select() returns 'setting:skin', cycle that setting."""
        state, book, disp = _make_mocks()
        state.mode = AppState.MODE_MENU
        state.skin_name = 'default'

        # Build a settings menu with a skin setting leaf
        root = MenuNode("Root", children=[
            MenuNode("Skin", setting_key="skin"),
        ])
        state.menu_state = MenuState(root)
        state.menu_state.cursor = 0

        with patch('pico_reader.input_handlers.set_setting'):
            menu_select(state, book, disp)

        # Should have cycled the skin
        disp.set_skin.assert_called_once()
        disp.show_menu_screen.assert_called()

    def test_none_drills_into_category(self):
        """When menu_state.select() returns None, redraw the menu."""
        state, book, disp = _make_mocks()
        state.mode = AppState.MODE_MENU

        # Build a nested menu: root -> Category -> Book
        category = MenuNode("Category", children=[
            MenuNode("Book A", book_id=0),
        ])
        root = MenuNode("Root", children=[category])
        state.menu_state = MenuState(root)
        state.menu_state.cursor = 0  # Point at the category

        menu_select(state, book, disp)

        # After drilling in, menu should be redrawn
        disp.show_menu_screen.assert_called_once_with(state.menu_state, book.book_metadata)
        # Mode should remain MENU since we just drilled in
        assert state.mode == AppState.MODE_MENU


# ---------------------------------------------------------------------------
# brightness_confirm
# ---------------------------------------------------------------------------

class TestBrightnessConfirm:
    def test_returns_to_menu(self):
        state, book, disp = _make_mocks()
        state.mode = AppState.MODE_BRIGHTNESS
        state.brightness = 75

        # Set up menu state so label update doesn't crash
        root = MenuNode("Root", children=[
            MenuNode("Bright: 50%", setting_key="brightness"),
        ])
        state.menu_state = MenuState(root)
        state.menu_state.cursor = 0

        brightness_confirm(state, book, disp)

        assert state.mode == AppState.MODE_MENU
        disp.show_menu_screen.assert_called_once()


# ---------------------------------------------------------------------------
# brightness_adjust_up / brightness_adjust_down
# ---------------------------------------------------------------------------

class TestBrightnessAdjust:
    def test_up_increases_by_2(self):
        state, book, disp = _make_mocks()
        state.brightness = 50
        state.settings = {'brightness': '50'}
        with patch('pico_reader.input_handlers.set_setting'):
            brightness_adjust_up(state, book, disp)
        assert state.brightness == 52
        disp.set_brightness.assert_called_once_with(52)

    def test_down_decreases_by_2(self):
        state, book, disp = _make_mocks()
        state.brightness = 50
        state.settings = {'brightness': '50'}
        with patch('pico_reader.input_handlers.set_setting'):
            brightness_adjust_down(state, book, disp)
        assert state.brightness == 48
        disp.set_brightness.assert_called_once_with(48)

    def test_up_clamps_at_100(self):
        state, book, disp = _make_mocks()
        state.brightness = 99
        state.settings = {'brightness': '99'}
        with patch('pico_reader.input_handlers.set_setting'):
            brightness_adjust_up(state, book, disp)
        assert state.brightness == 100

    def test_down_clamps_at_1(self):
        state, book, disp = _make_mocks()
        state.brightness = 2
        state.settings = {'brightness': '2'}
        with patch('pico_reader.input_handlers.set_setting'):
            brightness_adjust_down(state, book, disp)
        assert state.brightness == 1

    def test_down_cannot_go_below_1(self):
        state, book, disp = _make_mocks()
        state.brightness = 1
        state.settings = {'brightness': '1'}
        with patch('pico_reader.input_handlers.set_setting'):
            brightness_adjust_down(state, book, disp)
        assert state.brightness == 1

    def test_up_cannot_go_above_100(self):
        state, book, disp = _make_mocks()
        state.brightness = 100
        state.settings = {'brightness': '100'}
        with patch('pico_reader.input_handlers.set_setting'):
            brightness_adjust_up(state, book, disp)
        assert state.brightness == 100


# ---------------------------------------------------------------------------
# goto_menu
# ---------------------------------------------------------------------------

class TestGotoMenu:
    def test_paused_goes_to_menu(self):
        state, book, disp = _make_mocks()
        state.mode = AppState.MODE_READER
        state.playing = False
        state.menu_state = MagicMock()
        goto_menu(state, book, disp)
        assert state.mode == AppState.MODE_MENU
        book.save_place.assert_called_once()
        disp.show_menu_screen.assert_called_once()

    def test_playing_does_not_go_to_menu(self):
        state, book, disp = _make_mocks()
        state.mode = AppState.MODE_READER
        state.playing = True
        goto_menu(state, book, disp)
        assert state.mode == AppState.MODE_READER
        book.save_place.assert_not_called()


# ---------------------------------------------------------------------------
# prev_chapter / next_chapter
# ---------------------------------------------------------------------------

class TestChapterNavigation:
    def test_prev_chapter_when_paused(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.jump_to_chapter.return_value = "Chapter 1"
        prev_chapter(state, book, disp)
        book.jump_to_chapter.assert_called_once_with(-1)
        book.save_place.assert_called_once()
        disp.show_word.assert_called_once()
        disp.refresh.assert_called_once()

    def test_next_chapter_when_paused(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.jump_to_chapter.return_value = "Chapter 2"
        next_chapter(state, book, disp)
        book.jump_to_chapter.assert_called_once_with(1)
        book.save_place.assert_called_once()

    def test_prev_chapter_noop_when_playing(self):
        state, book, disp = _make_mocks()
        state.playing = True
        prev_chapter(state, book, disp)
        book.jump_to_chapter.assert_not_called()

    def test_next_chapter_noop_when_playing(self):
        state, book, disp = _make_mocks()
        state.playing = True
        next_chapter(state, book, disp)
        book.jump_to_chapter.assert_not_called()

    def test_prev_chapter_noop_when_none_returned(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.jump_to_chapter.return_value = None
        prev_chapter(state, book, disp)
        book.save_place.assert_not_called()
        disp.show_word.assert_not_called()


# ---------------------------------------------------------------------------
# enter_jump_mode
# ---------------------------------------------------------------------------

class TestEnterJumpMode:
    def test_sets_jump_mode(self):
        state, book, disp = _make_mocks()
        state.mode = AppState.MODE_READER
        state.playing = False
        book.book_len = 1000
        book.line_num = 500
        enter_jump_mode(state, book, disp)
        assert state.mode == AppState.MODE_JUMP
        assert state.jump_pct == 50
        disp.show_jump_screen.assert_called_once_with(50)

    def test_noop_when_playing(self):
        state, book, disp = _make_mocks()
        state.playing = True
        enter_jump_mode(state, book, disp)
        assert state.mode != AppState.MODE_JUMP

    def test_zero_book_len(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.book_len = 0
        book.line_num = 0
        enter_jump_mode(state, book, disp)
        assert state.jump_pct == 0


# ---------------------------------------------------------------------------
# wpm_up_or_step_fwd / wpm_down_or_step_back
# ---------------------------------------------------------------------------

class TestWpmAndStepping:
    def test_wpm_up_when_playing(self):
        state, book, disp = _make_mocks()
        state.playing = True
        state.wpm = 200
        wpm_up_or_step_fwd(state, book, disp)
        assert state.wpm == 202

    def test_wpm_down_when_playing(self):
        state, book, disp = _make_mocks()
        state.playing = True
        state.wpm = 200
        wpm_down_or_step_back(state, book, disp)
        assert state.wpm == 198

    def test_step_forward_when_paused(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.step_forward.return_value = "hello"
        wpm_up_or_step_fwd(state, book, disp)
        book.step_forward.assert_called_once()
        disp.show_word.assert_called_once()
        disp.show_wpm.assert_called_once()
        disp.refresh.assert_called_once()
        book.save_place.assert_called_once()

    def test_step_backward_when_paused(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.step_backward.return_value = "world"
        wpm_down_or_step_back(state, book, disp)
        book.step_backward.assert_called_once()
        disp.show_word.assert_called_once()
        book.save_place.assert_called_once()

    def test_step_forward_none_does_not_update_display(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.step_forward.return_value = None
        wpm_up_or_step_fwd(state, book, disp)
        disp.show_word.assert_not_called()

    def test_step_backward_none_does_not_update_display(self):
        state, book, disp = _make_mocks()
        state.playing = False
        book.step_backward.return_value = None
        wpm_down_or_step_back(state, book, disp)
        disp.show_word.assert_not_called()
