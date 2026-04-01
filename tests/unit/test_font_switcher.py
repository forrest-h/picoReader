"""Tests for Phase 5D: font switcher."""
import pytest
from unittest.mock import MagicMock, patch
from pico_reader.constants import AVAILABLE_FONTS
from pico_reader.state import AppState
from pico_reader.settings import DEFAULTS
from pico_reader.input_handlers import cycle_font


# ---------------------------------------------------------------------------
# AVAILABLE_FONTS constant
# ---------------------------------------------------------------------------

class TestAvailableFonts:
    def test_has_eight_entries(self):
        assert len(AVAILABLE_FONTS) == 8

    def test_all_are_pcf_files(self):
        for name in AVAILABLE_FONTS:
            assert name.endswith('.pcf'), "{} is not a PCF file".format(name)

    def test_toronto_is_first(self):
        assert AVAILABLE_FONTS[0] == 'Toronto_14.pcf'

    def test_no_duplicates(self):
        assert len(AVAILABLE_FONTS) == len(set(AVAILABLE_FONTS))


# ---------------------------------------------------------------------------
# AppState.font_name
# ---------------------------------------------------------------------------

class TestAppStateFontName:
    def test_default_font(self):
        s = AppState()
        assert s.font_name == 'Toronto_14.pcf'

    def test_font_from_settings(self):
        s = AppState(settings={'font': 'Bitter-Regular-14.pcf',
                               'palette': '0', 'brightness': '50'})
        assert s.font_name == 'Bitter-Regular-14.pcf'

    def test_missing_font_key_uses_default(self):
        s = AppState(settings={'palette': '1', 'brightness': '75'})
        assert s.font_name == DEFAULTS['font']

    def test_settings_stored_on_state(self):
        settings = {'font': 'Aleo-Regular-14.pcf', 'palette': '0',
                     'brightness': '50'}
        s = AppState(settings=settings)
        assert s.settings is settings

    def test_no_settings_creates_default_dict(self):
        s = AppState(settings=None)
        assert s.settings == dict(DEFAULTS)


# ---------------------------------------------------------------------------
# Settings persistence (font key)
# ---------------------------------------------------------------------------

class TestFontSetting:
    def test_default_font_in_defaults(self):
        assert DEFAULTS['font'] == 'Toronto_14.pcf'

    def test_font_loaded_from_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        (tmp_path / "saves" / "settings.txt").write_text(
            "font:Merriweather-Regular-14.pcf\n")
        from pico_reader.settings import load_settings
        s = load_settings()
        assert s['font'] == 'Merriweather-Regular-14.pcf'

    def test_font_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        from pico_reader.settings import save_settings, load_settings
        settings = dict(DEFAULTS)
        settings['font'] = 'SpecialElite-Regular-14.pcf'
        save_settings(settings)
        loaded = load_settings()
        assert loaded['font'] == 'SpecialElite-Regular-14.pcf'


# ---------------------------------------------------------------------------
# cycle_font handler
# ---------------------------------------------------------------------------

class TestCycleFont:
    def _make_state(self, font_name='Toronto_14.pcf'):
        settings = dict(DEFAULTS)
        settings['font'] = font_name
        s = AppState(settings=settings)
        return s

    def _make_disp(self):
        disp = MagicMock()
        disp._font = MagicMock()
        disp._font_dirty = False
        return disp

    @patch('pico_reader.input_handlers.load_reading_font')
    @patch('pico_reader.input_handlers.set_setting')
    def test_advances_to_next_font(self, mock_set, mock_load, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        state = self._make_state('Toronto_14.pcf')
        book = MagicMock()
        disp = self._make_disp()
        mock_load.return_value = MagicMock()

        cycle_font(state, book, disp)

        assert state.font_name == AVAILABLE_FONTS[1]  # Aleo

    @patch('pico_reader.input_handlers.load_reading_font')
    @patch('pico_reader.input_handlers.set_setting')
    def test_wraps_around(self, mock_set, mock_load, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        last_font = AVAILABLE_FONTS[-1]
        state = self._make_state(last_font)
        book = MagicMock()
        disp = self._make_disp()
        mock_load.return_value = MagicMock()

        cycle_font(state, book, disp)

        assert state.font_name == AVAILABLE_FONTS[0]  # wraps to Toronto

    @patch('pico_reader.input_handlers.load_reading_font')
    @patch('pico_reader.input_handlers.set_setting')
    def test_unknown_font_resets_to_second(self, mock_set, mock_load, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        state = self._make_state('NonExistent.pcf')
        book = MagicMock()
        disp = self._make_disp()
        mock_load.return_value = MagicMock()

        cycle_font(state, book, disp)

        # Unknown font defaults to index 0, then advances to index 1
        assert state.font_name == AVAILABLE_FONTS[1]

    @patch('pico_reader.input_handlers.load_reading_font')
    @patch('pico_reader.input_handlers.set_setting')
    def test_persists_setting(self, mock_set, mock_load, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        state = self._make_state('Toronto_14.pcf')
        book = MagicMock()
        disp = self._make_disp()
        mock_load.return_value = MagicMock()

        cycle_font(state, book, disp)

        mock_set.assert_called_once_with(state.settings, 'font', AVAILABLE_FONTS[1])

    @patch('pico_reader.input_handlers.load_reading_font')
    @patch('pico_reader.input_handlers.set_setting')
    def test_loads_new_font(self, mock_set, mock_load, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        state = self._make_state('Toronto_14.pcf')
        book = MagicMock()
        disp = self._make_disp()
        mock_font = MagicMock()
        mock_load.return_value = mock_font

        cycle_font(state, book, disp)

        mock_load.assert_called_once_with(AVAILABLE_FONTS[1])
        disp.set_font.assert_called_once_with(mock_font)

    @patch('pico_reader.input_handlers.load_reading_font')
    @patch('pico_reader.input_handlers.set_setting')
    def test_shows_preview(self, mock_set, mock_load, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        state = self._make_state('Toronto_14.pcf')
        book = MagicMock()
        disp = self._make_disp()
        mock_load.return_value = MagicMock()

        cycle_font(state, book, disp)

        # Preview shows font name without .pcf extension
        expected_name = AVAILABLE_FONTS[1].split('.')[0]
        disp.show_word.assert_called_once_with(expected_name)
        disp.refresh.assert_called_once()

    @patch('pico_reader.input_handlers.load_reading_font')
    @patch('pico_reader.input_handlers.set_setting')
    def test_full_cycle_through_all_fonts(self, mock_set, mock_load, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        state = self._make_state('Toronto_14.pcf')
        book = MagicMock()
        disp = self._make_disp()
        mock_load.return_value = MagicMock()

        visited = [state.font_name]
        for _ in range(len(AVAILABLE_FONTS)):
            cycle_font(state, book, disp)
            visited.append(state.font_name)

        # After N cycles, should be back to start
        assert visited[0] == visited[-1]
        # Should have visited all fonts
        assert set(visited) == set(AVAILABLE_FONTS)


# ---------------------------------------------------------------------------
# Display.set_font and show_reader_screen rebuild
# ---------------------------------------------------------------------------

class TestDisplayFontIntegration:
    def test_set_font_marks_dirty(self):
        from pico_reader.display import Display
        hw = MagicMock()
        hw.refresh = MagicMock()
        bl = MagicMock()
        font = MagicMock()
        smallfont = MagicMock()
        disp = Display(hw, bl, font, smallfont)
        assert disp._font_dirty is False

        new_font = MagicMock()
        disp.set_font(new_font)
        assert disp._font_dirty is True
        assert disp._font is new_font

    def test_show_reader_screen_rebuilds_when_dirty(self):
        from pico_reader.display import Display
        hw = MagicMock()
        hw.refresh = MagicMock()
        bl = MagicMock()
        font = MagicMock()
        smallfont = MagicMock()
        disp = Display(hw, bl, font, smallfont)

        # Set a palette so we can check it's preserved
        disp.skin.apply_palette(2)
        old_group = disp.reader_group

        new_font = MagicMock()
        disp.set_font(new_font)
        disp.show_reader_screen()

        # Group should be rebuilt (different object)
        assert disp.reader_group is not old_group
        assert disp._font_dirty is False
        # Palette index should be preserved after rebuild
        assert disp.skin._palette_index == 2

    def test_show_reader_screen_no_rebuild_when_clean(self):
        from pico_reader.display import Display
        hw = MagicMock()
        hw.refresh = MagicMock()
        bl = MagicMock()
        font = MagicMock()
        smallfont = MagicMock()
        disp = Display(hw, bl, font, smallfont)

        old_group = disp.reader_group
        disp.show_reader_screen()

        # Group should be the same object (no rebuild)
        assert disp.reader_group is old_group


# ---------------------------------------------------------------------------
# Dispatch table wiring
# ---------------------------------------------------------------------------

class TestDispatchWiring:
    def test_btn_down_display_mode_is_cycle_font(self):
        from pico_reader.input_handlers import BUTTON_HANDLERS
        from pico_reader.constants import BTN_DOWN
        handler = BUTTON_HANDLERS.get((AppState.MODE_DISPLAY, BTN_DOWN))
        assert handler is cycle_font
