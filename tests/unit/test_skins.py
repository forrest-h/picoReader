"""Parameterized tests for all skins: build_group, apply_palette, show_word with ORP modes."""
import pytest
import displayio
from adafruit_display_text import label
from pico_reader.skins import SKIN_NAMES, load_skin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeGlyph:
    def __init__(self, shift_x=8):
        self.shift_x = shift_x


class FakeFont:
    """Font stub with get_glyph support for ORP position calculations."""
    def __init__(self):
        self._glyph = FakeGlyph(8)

    def get_glyph(self, codepoint):
        return self._glyph


def _make_skin(skin_name):
    """Create and return a skin instance by name."""
    SkinClass = load_skin(skin_name)
    font = FakeFont()
    smallfont = FakeFont()
    return SkinClass(font, smallfont)


# ---------------------------------------------------------------------------
# Parameterized across all 4 skins
# ---------------------------------------------------------------------------

@pytest.fixture(params=SKIN_NAMES)
def skin_name(request):
    return request.param


@pytest.fixture
def built_skin(skin_name):
    """Return a skin instance with build_group() already called."""
    skin = _make_skin(skin_name)
    skin.build_group(160, 128)
    return skin


class TestBuildGroup:
    def test_returns_displayio_group(self, skin_name):
        skin = _make_skin(skin_name)
        group = skin.build_group(160, 128)
        assert isinstance(group, displayio.Group)

    def test_group_has_children(self, skin_name):
        skin = _make_skin(skin_name)
        group = skin.build_group(160, 128)
        assert len(group) >= 4, "skin {} has only {} children".format(
            skin_name, len(group))

    def test_first_child_is_background(self, skin_name):
        skin = _make_skin(skin_name)
        group = skin.build_group(160, 128)
        child = group[0]
        assert isinstance(child, displayio.TileGrid)
        assert child.bitmap.width == 160
        assert child.bitmap.height == 128


class TestApplyPalette:
    def test_all_palettes_apply_without_error(self, skin_name):
        skin = _make_skin(skin_name)
        skin.build_group(160, 128)
        SkinClass = load_skin(skin_name)
        for idx in range(len(SkinClass.PALETTES)):
            skin.apply_palette(idx)

    def test_palette_changes_bg(self, skin_name):
        skin = _make_skin(skin_name)
        skin.build_group(160, 128)
        SkinClass = load_skin(skin_name)
        if len(SkinClass.PALETTES) >= 2:
            skin.apply_palette(1)
            assert skin._bg_palette[0] == SkinClass.PALETTES[1]['bg']


class TestShowWord:
    def test_show_word_no_orp(self, built_skin):
        """show_word with orp_mode=None should not raise."""
        built_skin.show_word('hello')

    def test_show_word_color_orp(self, built_skin):
        """show_word with orp_mode='color' should not raise."""
        built_skin.show_word('hello', orp_mode='color')

    def test_show_word_bold_orp(self, built_skin):
        """show_word with orp_mode='bold' should not raise."""
        built_skin.show_word('hello', orp_mode='bold')

    def test_show_word_empty(self, built_skin):
        """show_word with empty string should not raise."""
        built_skin.show_word('')

    def test_show_word_single_char(self, built_skin):
        """show_word with single char should not raise even in ORP modes."""
        built_skin.show_word('a', orp_mode='color')
        built_skin.show_word('a', orp_mode='bold')

    def test_show_word_long(self, built_skin):
        """show_word with long word should not raise."""
        built_skin.show_word('supercalifragilistic', orp_mode='color')

    def test_color_orp_sets_orp_label(self, built_skin, skin_name):
        """In color ORP mode, the ORP label should have the ORP character."""
        built_skin.show_word('hello', orp_mode='color')
        # ORP for 'hello' is index 1 => 'e'
        assert built_skin._word_orp.text == 'e'

    def test_no_orp_clears_orp_labels(self, built_skin, skin_name):
        """In normal mode, the ORP and suffix labels should be empty."""
        built_skin.show_word('hello')
        assert built_skin._word_orp.text == ''
        assert built_skin._word_suffix.text == ''


class TestShowWpm:
    def test_show_wpm(self, built_skin, skin_name):
        built_skin.show_wpm(300)
        # Typewriter has a special format
        if skin_name == 'typewriter':
            assert '300' in built_skin._wpm_label.text
        else:
            assert built_skin._wpm_label.text == '300'


class TestProgress:
    def test_update_progress(self, built_skin):
        """update_progress should not raise."""
        built_skin.update_progress(0.5)

    def test_reset_progress(self, built_skin):
        """reset_progress after update should not raise."""
        built_skin.update_progress(0.5)
        built_skin.reset_progress()

    def test_progress_full(self, built_skin):
        """Progress at 100% should not raise."""
        built_skin.update_progress(1.0)

    def test_progress_zero(self, built_skin):
        """Progress at 0% should not raise."""
        built_skin.update_progress(0.0)

    def test_progress_backward(self, built_skin):
        """Going backward in progress should not raise."""
        built_skin.update_progress(0.7)
        built_skin.update_progress(0.3)


class TestGetHighlightColor:
    def test_returns_int(self, built_skin):
        color = built_skin.get_highlight_color()
        assert isinstance(color, int)


# ---------------------------------------------------------------------------
# Skin-specific tests
# ---------------------------------------------------------------------------

class TestTerminalSkin:
    def test_cursor_hidden_by_default(self):
        skin = _make_skin('terminal')
        skin.build_group(160, 128)
        # Cursor should be hidden (color matches bg)
        assert skin._cursor_label.color == 0x000000

    def test_set_cursor_visible(self):
        skin = _make_skin('terminal')
        skin.build_group(160, 128)
        skin.set_cursor_visible(True)
        assert skin._cursor_label.color != 0x000000

    def test_set_cursor_hidden(self):
        skin = _make_skin('terminal')
        skin.build_group(160, 128)
        skin.set_cursor_visible(True)
        skin.set_cursor_visible(False)
        assert skin._cursor_label.color == 0x000000

    def test_set_book_title(self):
        skin = _make_skin('terminal')
        skin.build_group(160, 128)
        skin.set_book_title('My Great Book')
        assert 'MY_GREAT_BO' in skin._path_label.text

    def test_ascii_progress_format(self):
        skin = _make_skin('terminal')
        skin.build_group(160, 128)
        skin.update_progress(0.5)
        text = skin._progress_label.text
        assert '[' in text
        assert ']' in text
        assert '50%' in text

    def test_has_three_palettes(self):
        from pico_reader.skins.terminal import PALETTES
        assert len(PALETTES) == 3


class TestRpgSkin:
    def test_has_dialogue_box(self):
        skin = _make_skin('rpg')
        group = skin.build_group(160, 128)
        from adafruit_display_shapes.rect import Rect
        # Indices 1 and 2 should be Rects (border and inner)
        assert isinstance(group[1], Rect)
        assert isinstance(group[2], Rect)

    def test_flavor_text_present(self):
        skin = _make_skin('rpg')
        skin.build_group(160, 128)
        assert skin._flavor_label.text != ''

    def test_hp_bar_progress(self):
        skin = _make_skin('rpg')
        skin.build_group(160, 128)
        skin.update_progress(0.5)
        # Check some pixels are filled
        filled = sum(1 for x in range(120) if skin._hp_bmp[x, 0] == 1)
        assert filled == 60

    def test_has_three_palettes(self):
        from pico_reader.skins.rpg import PALETTES
        assert len(PALETTES) == 3

    def test_prog_label_text(self):
        skin = _make_skin('rpg')
        skin.build_group(160, 128)
        assert skin._prog_label.text == 'PROG'


class TestTypewriterSkin:
    def test_wpm_format(self):
        skin = _make_skin('typewriter')
        skin.build_group(160, 128)
        skin.show_wpm(250)
        assert skin._wpm_label.text == '~ 250 wpm ~'

    def test_y_jitter_varies(self):
        """Different words should produce different Y positions."""
        skin = _make_skin('typewriter')
        skin.build_group(160, 128)
        positions = set()
        for ch in 'abcdefghijklmnop':
            skin.show_word(ch)
            positions.add(skin._word_prefix.anchored_position[1])
        # Should have at least 2 different Y positions across the alphabet
        assert len(positions) >= 2

    def test_underline_progress(self):
        skin = _make_skin('typewriter')
        skin.build_group(160, 128)
        skin.update_progress(0.5)
        filled = sum(1 for x in range(160) if skin._underline_bmp[x, 0] == 1)
        assert filled == 80

    def test_has_three_palettes(self):
        from pico_reader.skins.typewriter import PALETTES
        assert len(PALETTES) == 3


# ---------------------------------------------------------------------------
# Palette key validation
# ---------------------------------------------------------------------------

class TestPaletteKeys:
    def test_default_palette_keys(self):
        from pico_reader.skins.default import PALETTES
        required = {'name', 'bg', 'text', 'wpm', 'highlight'}
        for pal in PALETTES:
            assert set(pal.keys()) == required

    def test_terminal_palette_keys(self):
        from pico_reader.skins.terminal import PALETTES
        required = {'name', 'bg', 'phosphor', 'dim'}
        for pal in PALETTES:
            assert set(pal.keys()) == required

    def test_rpg_palette_keys(self):
        from pico_reader.skins.rpg import PALETTES
        required = {'name', 'bg', 'border', 'text', 'hp_fill'}
        for pal in PALETTES:
            assert set(pal.keys()) == required

    def test_typewriter_palette_keys(self):
        from pico_reader.skins.typewriter import PALETTES
        required = {'name', 'bg', 'ink', 'dim'}
        for pal in PALETTES:
            assert set(pal.keys()) == required
