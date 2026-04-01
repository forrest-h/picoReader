import pytest
from pico_reader.state import AppState


class TestAppState:
    def test_defaults(self):
        s = AppState()
        assert s.mode == AppState.MODE_MENU
        assert s.wpm == 200
        assert s.speed == pytest.approx(0.3)
        assert s.brightness == 50
        assert s.theme_index == 0
        assert s.playing is False
        assert s.finished is False

    def test_set_wpm(self):
        s = AppState()
        s.set_wpm(300)
        assert s.wpm == 300
        assert s.speed == pytest.approx(0.2)

    def test_wpm_floor(self):
        s = AppState()
        s.set_wpm(5)
        assert s.wpm == 10

    def test_wpm_floor_exact(self):
        s = AppState()
        s.set_wpm(10)
        assert s.wpm == 10

    def test_settings_applied(self):
        s = AppState(settings={'palette': '3', 'brightness': '75'})
        assert s.theme_index == 3
        assert s.brightness == 75

    def test_settings_none(self):
        s = AppState(settings=None)
        assert s.theme_index == 0
        assert s.brightness == 50

    def test_mode_constants(self):
        assert AppState.MODE_MENU == 0
        assert AppState.MODE_READER == 1
        assert AppState.MODE_DISPLAY == 2

    def test_mode_jump_constant(self):
        assert AppState.MODE_JUMP == 3

    def test_jump_pct_default(self):
        s = AppState()
        assert s.jump_pct == 0

    def test_menu_state_default(self):
        s = AppState()
        assert s.menu_state is None
