"""Tests for the Display class delegation pattern."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from pico_reader.display import Display
from pico_reader.constants import DISPLAY_WIDTH, DISPLAY_HEIGHT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeGlyph:
    def __init__(self, shift_x=8):
        self.shift_x = shift_x


class FakeFont:
    """Minimal font stand-in for label.Label and ORP calculations."""
    def __init__(self):
        self._glyph = FakeGlyph(8)

    def get_glyph(self, codepoint):
        return self._glyph


def _make_hw_display():
    """Create a mock hardware display."""
    hw = MagicMock()
    hw.refresh = MagicMock()
    hw.show = MagicMock()
    return hw


def _make_display(skin_name='default'):
    """Create a real Display using simulator shims."""
    hw = _make_hw_display()
    backlight = MagicMock()
    backlight.duty_cycle = 0
    font = FakeFont()
    smallfont = FakeFont()
    disp = Display(hw, backlight, font, smallfont, skin_name=skin_name)
    return disp, hw, backlight


# ---------------------------------------------------------------------------
# show_word delegation
# ---------------------------------------------------------------------------

class TestShowWord:
    def test_delegates_to_skin(self):
        disp, hw, bl = _make_display()
        disp.skin = MagicMock()
        disp.show_word("hello")
        disp.skin.show_word.assert_called_once_with("hello", None)

    def test_passes_orp_mode(self):
        disp, hw, bl = _make_display()
        disp.skin = MagicMock()
        disp.show_word("hello", orp_mode='color')
        disp.skin.show_word.assert_called_once_with("hello", 'color')

    def test_real_skin_updates_text(self):
        """Integration check: real default skin actually updates its label."""
        disp, hw, bl = _make_display()
        disp.show_word("testing")
        assert "testing" in disp.skin._word_prefix.text


# ---------------------------------------------------------------------------
# show_wpm delegation
# ---------------------------------------------------------------------------

class TestShowWpm:
    def test_delegates_to_skin(self):
        disp, hw, bl = _make_display()
        disp.skin = MagicMock()
        disp.show_wpm(300)
        disp.skin.show_wpm.assert_called_once_with(300)

    def test_real_skin_updates_wpm(self):
        disp, hw, bl = _make_display()
        disp.show_wpm(350)
        assert disp.skin._wpm_label.text == "350"


# ---------------------------------------------------------------------------
# set_palette delegation
# ---------------------------------------------------------------------------

class TestSetPalette:
    def test_delegates_to_skin_apply_palette(self):
        disp, hw, bl = _make_display()
        disp.skin = MagicMock()
        disp.set_palette(2)
        disp.skin.apply_palette.assert_called_once_with(2)

    def test_real_skin_changes_palette(self):
        disp, hw, bl = _make_display()
        from pico_reader.skins.default import PALETTES
        disp.set_palette(3)
        assert disp.skin._bg_palette[0] == PALETTES[3]['bg']


# ---------------------------------------------------------------------------
# set_skin
# ---------------------------------------------------------------------------

class TestSetSkin:
    def test_loads_new_skin_and_rebuilds_group(self):
        disp, hw, bl = _make_display(skin_name='default')
        old_skin = disp.skin
        old_group = disp.reader_group
        disp.set_skin('default')
        # Skin instance should be replaced (new object)
        assert disp.skin is not old_skin
        # Reader group should be rebuilt
        assert disp.reader_group is not old_group

    def test_switch_to_terminal_skin(self):
        disp, hw, bl = _make_display(skin_name='default')
        disp.set_skin('terminal')
        from pico_reader.skins.terminal import Skin as TerminalSkin
        assert isinstance(disp.skin, TerminalSkin)

    def test_switch_back_to_default(self):
        disp, hw, bl = _make_display(skin_name='terminal')
        disp.set_skin('default')
        from pico_reader.skins.default import Skin as DefaultSkin
        assert isinstance(disp.skin, DefaultSkin)


# ---------------------------------------------------------------------------
# set_cursor_visible
# ---------------------------------------------------------------------------

class TestSetCursorVisible:
    def test_delegates_when_skin_has_method(self):
        disp, hw, bl = _make_display()
        # Replace skin with a mock that has set_cursor_visible
        disp.skin = MagicMock(spec=['set_cursor_visible'])
        disp.set_cursor_visible(True)
        disp.skin.set_cursor_visible.assert_called_once_with(True)

    def test_noops_when_skin_lacks_method(self):
        disp, hw, bl = _make_display()
        # Default skin does NOT have set_cursor_visible
        from pico_reader.skins.default import Skin as DefaultSkin
        assert not hasattr(DefaultSkin, 'set_cursor_visible')
        # Should not raise
        disp.set_cursor_visible(True)

    def test_terminal_skin_has_method(self):
        disp, hw, bl = _make_display(skin_name='terminal')
        assert hasattr(disp.skin, 'set_cursor_visible')
        # Should not raise
        disp.set_cursor_visible(False)


# ---------------------------------------------------------------------------
# update_progress / reset_progress
# ---------------------------------------------------------------------------

class TestProgress:
    def test_update_progress_delegates(self):
        disp, hw, bl = _make_display()
        disp.skin = MagicMock()
        disp.update_progress(50, 100)
        disp.skin.update_progress.assert_called_once_with(0.5)

    def test_update_progress_zero_book_len(self):
        disp, hw, bl = _make_display()
        disp.skin = MagicMock()
        disp.update_progress(50, 0)
        disp.skin.update_progress.assert_not_called()

    def test_reset_progress_delegates(self):
        disp, hw, bl = _make_display()
        disp.skin = MagicMock()
        disp.reset_progress()
        disp.skin.reset_progress.assert_called_once()


# ---------------------------------------------------------------------------
# set_brightness
# ---------------------------------------------------------------------------

class TestSetBrightness:
    def test_sets_backlight_duty_cycle(self):
        disp, hw, bl = _make_display()
        disp.set_brightness(100)
        assert bl.duty_cycle == 65535

    def test_brightness_50_percent(self):
        disp, hw, bl = _make_display()
        disp.set_brightness(50)
        assert bl.duty_cycle == int(50 / 100 * 65535)

    def test_brightness_1_percent(self):
        disp, hw, bl = _make_display()
        disp.set_brightness(1)
        assert bl.duty_cycle == int(1 / 100 * 65535)


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------

class TestRefresh:
    def test_delegates_to_hw_display(self):
        disp, hw, bl = _make_display()
        disp.refresh()
        hw.refresh.assert_called_once()


# ---------------------------------------------------------------------------
# show_reader_screen
# ---------------------------------------------------------------------------

class TestShowReaderScreen:
    def test_shows_reader_group(self):
        disp, hw, bl = _make_display()
        disp.show_reader_screen()
        hw.show.assert_called_once_with(disp.reader_group)
        hw.refresh.assert_called_once()

    def test_font_dirty_triggers_rebuild(self):
        disp, hw, bl = _make_display()
        old_group = disp.reader_group
        disp.set_font(FakeFont())
        assert disp._font_dirty is True
        disp.show_reader_screen()
        assert disp._font_dirty is False
        # Group should be rebuilt
        assert disp.reader_group is not old_group


# ---------------------------------------------------------------------------
# set_font
# ---------------------------------------------------------------------------

class TestSetFont:
    def test_marks_font_dirty(self):
        disp, hw, bl = _make_display()
        assert disp._font_dirty is False
        disp.set_font(FakeFont())
        assert disp._font_dirty is True

    def test_stores_new_font(self):
        disp, hw, bl = _make_display()
        new_font = FakeFont()
        disp.set_font(new_font)
        assert disp._font is new_font


# ---------------------------------------------------------------------------
# show_jump_screen
# ---------------------------------------------------------------------------

class TestShowJumpScreen:
    def test_shows_jump_text(self):
        disp, hw, bl = _make_display()
        disp.show_jump_screen(42)
        assert "Jump: 42%" in disp.skin._word_prefix.text
        hw.show.assert_called_once_with(disp.reader_group)
        hw.refresh.assert_called_once()
