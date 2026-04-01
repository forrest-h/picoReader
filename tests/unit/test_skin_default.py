"""Tests for the default skin and skin registry."""
import pytest
import displayio
from adafruit_display_text import label
from pico_reader.skins import SKIN_NAMES, load_skin
from pico_reader.skins.default import Skin, PALETTES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeGlyph:
    def __init__(self, shift_x=8):
        self.shift_x = shift_x


class FakeFont:
    """Minimal font stand-in for label.Label with get_glyph for ORP."""
    def __init__(self):
        self._glyph = FakeGlyph(8)

    def get_glyph(self, codepoint):
        return self._glyph


def _make_skin():
    font = FakeFont()
    smallfont = FakeFont()
    return Skin(font, smallfont)


# ---------------------------------------------------------------------------
# Skin registry tests
# ---------------------------------------------------------------------------

class TestSkinRegistry:
    def test_skin_names_contains_default(self):
        assert 'default' in SKIN_NAMES

    def test_load_default_returns_skin_class(self):
        cls = load_skin('default')
        assert cls is Skin

    def test_load_unknown_falls_back_to_default(self):
        cls = load_skin('nonexistent')
        assert cls is Skin


# ---------------------------------------------------------------------------
# Default skin: build_group
#
# Group indices: 0=bg, 1=word_prefix, 2=word_orp, 3=word_suffix,
#                4-7=guides, 8=progress, 9=wpm.
# ---------------------------------------------------------------------------

class TestBuildGroup:
    def test_returns_group(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        assert isinstance(group, displayio.Group)

    def test_group_has_10_children(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        assert len(group) == 10

    def test_index_0_is_background_tilegrid(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        child = group[0]
        assert isinstance(child, displayio.TileGrid)
        assert child.bitmap.width == 160
        assert child.bitmap.height == 128

    def test_index_1_is_word_prefix_label(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        child = group[1]
        assert isinstance(child, label.Label)

    def test_index_2_is_orp_label(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        child = group[2]
        assert isinstance(child, label.Label)

    def test_index_3_is_suffix_label(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        child = group[3]
        assert isinstance(child, label.Label)

    def test_indices_4_to_7_are_guide_rects(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        from adafruit_display_shapes.rect import Rect
        for i in range(4, 8):
            assert isinstance(group[i], Rect)

    def test_index_8_is_progress_tilegrid(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        child = group[8]
        assert isinstance(child, displayio.TileGrid)
        assert child.bitmap.width == 160
        assert child.bitmap.height == 2

    def test_index_9_is_wpm_label(self):
        skin = _make_skin()
        group = skin.build_group(160, 128)
        child = group[9]
        assert isinstance(child, label.Label)


# ---------------------------------------------------------------------------
# Default skin: apply_palette
# ---------------------------------------------------------------------------

class TestApplyPalette:
    def test_all_five_palettes_apply_without_error(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        for idx in range(len(PALETTES)):
            skin.apply_palette(idx)

    def test_palette_changes_bg_color(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.apply_palette(1)  # Light theme
        assert skin._bg_palette[0] == PALETTES[1]['bg']

    def test_palette_changes_word_color(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.apply_palette(3)  # Crimson
        assert skin._word_prefix.color == PALETTES[3]['text']

    def test_palette_changes_wpm_color(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.apply_palette(2)  # Gray
        assert skin._wpm_label.color == PALETTES[2]['wpm']

    def test_palette_changes_guide_fills(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.apply_palette(4)  # Muted Dark
        for guide in skin._guides:
            assert guide.fill == PALETTES[4]['highlight']

    def test_palette_changes_progress_colors(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.apply_palette(3)
        assert skin._progress_palette[0] == PALETTES[3]['bg']
        assert skin._progress_palette[1] == PALETTES[3]['highlight']

    def test_get_highlight_color(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.apply_palette(2)
        assert skin.get_highlight_color() == PALETTES[2]['highlight']

    def test_palettes_have_five_entries(self):
        assert len(PALETTES) == 5

    def test_each_palette_has_required_keys(self):
        required = {'name', 'bg', 'text', 'wpm', 'highlight'}
        for pal in PALETTES:
            assert set(pal.keys()) == required


# ---------------------------------------------------------------------------
# Default skin: show_word
# ---------------------------------------------------------------------------

class TestShowWord:
    def test_updates_text(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.show_word("hello")
        assert "hello" in skin._word_prefix.text

    def test_centers_text(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.show_word("hi")
        # 30-char centered
        assert len(skin._word_prefix.text) == 30

    def test_empty_word(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.show_word("")
        assert len(skin._word_prefix.text) == 30

    def test_orp_color_mode(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.show_word("hello", orp_mode='color')
        assert skin._word_orp.text == 'e'
        assert skin._word_prefix.text == 'h'
        assert skin._word_suffix.text == 'llo'

    def test_orp_bold_mode(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.show_word("hello", orp_mode='bold')
        assert "hello" in skin._word_prefix.text

    def test_orp_clears_on_normal(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.show_word("hello", orp_mode='color')
        skin.show_word("world")
        assert skin._word_orp.text == ''
        assert skin._word_suffix.text == ''


# ---------------------------------------------------------------------------
# Default skin: show_wpm
# ---------------------------------------------------------------------------

class TestShowWpm:
    def test_updates_wpm(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.show_wpm(300)
        assert skin._wpm_label.text == "300"


# ---------------------------------------------------------------------------
# Default skin: progress
# ---------------------------------------------------------------------------

class TestProgress:
    def test_update_progress_fills_pixels(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.update_progress(0.5)
        # Should have filled ~80 pixels
        filled = sum(1 for x in range(160) if skin._progress_bmp[x, 0] == 1)
        assert filled == 80

    def test_reset_progress_clears(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.update_progress(0.5)
        skin.reset_progress()
        filled = sum(1 for x in range(160) if skin._progress_bmp[x, 0] == 1)
        assert filled == 0

    def test_progress_backward_clears_extra(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.update_progress(0.5)
        skin.update_progress(0.25)
        filled = sum(1 for x in range(160) if skin._progress_bmp[x, 0] == 1)
        assert filled == 40

    def test_update_progress_no_change_same_pct(self):
        skin = _make_skin()
        skin.build_group(160, 128)
        skin.update_progress(0.5)
        # Calling again with same value should be a no-op
        skin.update_progress(0.5)
        filled = sum(1 for x in range(160) if skin._progress_bmp[x, 0] == 1)
        assert filled == 80
