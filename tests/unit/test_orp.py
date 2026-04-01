"""Tests for ORP (Optimal Recognition Point) helpers."""
import pytest
from pico_reader.orp import calc_orp_index, calc_orp_positions, calc_bold_split


# ---------------------------------------------------------------------------
# calc_orp_index
# ---------------------------------------------------------------------------

class TestCalcOrpIndex:
    """ORP index should be roughly 1/3 into the word."""

    def test_empty_string(self):
        assert calc_orp_index('') == 0

    def test_single_char(self):
        assert calc_orp_index('a') == 0

    def test_two_chars(self):
        # min(1, max(1, (3)//3 - 1)) = min(1, max(1, 0)) = min(1,1) = 1
        assert calc_orp_index('ab') == 1

    def test_three_chars(self):
        # min(2, max(1, (4)//3 - 1)) = min(2, max(1, 0)) = min(2,1) = 1
        assert calc_orp_index('abc') == 1

    def test_four_chars(self):
        # min(3, max(1, (5)//3 - 1)) = min(3, max(1, 0)) = min(3,1) = 1
        assert calc_orp_index('abcd') == 1

    def test_five_chars(self):
        # min(4, max(1, (6)//3 - 1)) = min(4, max(1, 1)) = min(4,1) = 1
        assert calc_orp_index('abcde') == 1

    def test_six_chars(self):
        # min(5, max(1, (7)//3 - 1)) = min(5, max(1, 1)) = min(5,1) = 1
        assert calc_orp_index('abcdef') == 1

    def test_seven_chars(self):
        # min(6, max(1, (8)//3 - 1)) = min(6, max(1, 1)) = min(6,1) = 1
        assert calc_orp_index('abcdefg') == 1

    def test_eight_chars(self):
        # min(7, max(1, (9)//3 - 1)) = min(7, max(1, 2)) = min(7,2) = 2
        assert calc_orp_index('abcdefgh') == 2

    def test_nine_chars(self):
        # min(8, max(1, (10)//3 - 1)) = min(8, max(1, 2)) = min(8,2) = 2
        assert calc_orp_index('abcdefghi') == 2

    def test_ten_chars(self):
        # min(9, max(1, (11)//3 - 1)) = min(9, max(1, 2)) = min(9,2) = 2
        assert calc_orp_index('abcdefghij') == 2

    def test_eleven_chars(self):
        # min(10, max(1, (12)//3 - 1)) = min(10, max(1, 3)) = min(10,3) = 3
        assert calc_orp_index('abcdefghijk') == 3

    def test_fifteen_chars(self):
        # min(14, max(1, (16)//3 - 1)) = min(14, max(1, 4)) = min(14,4) = 4
        assert calc_orp_index('abcdefghijklmno') == 4

    def test_index_never_zero_for_multi_char(self):
        """ORP index is always >= 1 for words with 2+ chars."""
        for length in range(2, 20):
            word = 'a' * length
            idx = calc_orp_index(word)
            assert idx >= 1, "length {} gave index {}".format(length, idx)

    def test_index_never_exceeds_last_char(self):
        """ORP index is always < len(word)."""
        for length in range(1, 20):
            word = 'a' * length
            idx = calc_orp_index(word)
            assert idx < length, "length {} gave index {}".format(length, idx)


# ---------------------------------------------------------------------------
# calc_orp_positions
# ---------------------------------------------------------------------------

class FakeGlyph:
    def __init__(self, shift_x):
        self.shift_x = shift_x


class FakeFont:
    """Font stub that returns fixed-width glyphs for testing."""
    def __init__(self, glyph_width=8):
        self._width = glyph_width

    def get_glyph(self, codepoint):
        return FakeGlyph(self._width)


class TestCalcOrpPositions:
    def test_returns_six_elements(self):
        font = FakeFont(8)
        result = calc_orp_positions('hello', font)
        assert len(result) == 6

    def test_prefix_orp_suffix_split(self):
        font = FakeFont(8)
        prefix, orp_char, suffix, _, _, _ = calc_orp_positions('hello', font)
        assert prefix == 'h'
        assert orp_char == 'e'
        assert suffix == 'llo'

    def test_single_char_word(self):
        font = FakeFont(8)
        prefix, orp_char, suffix, _, _, _ = calc_orp_positions('a', font)
        assert prefix == ''
        assert orp_char == 'a'
        assert suffix == ''

    def test_two_char_word(self):
        font = FakeFont(8)
        prefix, orp_char, suffix, _, _, _ = calc_orp_positions('ab', font)
        assert prefix == 'a'
        assert orp_char == 'b'
        assert suffix == ''

    def test_orp_anchored_at_center(self):
        font = FakeFont(8)
        _, _, _, _, orp_x, _ = calc_orp_positions('hello', font, anchor_x=80)
        # orp_x = 80 - 8//2 = 76
        assert orp_x == 76

    def test_prefix_x_no_overflow(self):
        """Prefix X should not go below 0 even for very long words."""
        font = FakeFont(8)
        long_word = 'a' * 30
        _, _, _, prefix_x, _, _ = calc_orp_positions(long_word, font, anchor_x=80)
        assert prefix_x >= 0

    def test_suffix_x_no_overflow(self):
        """Suffix X should not exceed 155 (5px margin)."""
        font = FakeFont(8)
        long_word = 'a' * 30
        _, _, _, _, _, suffix_x = calc_orp_positions(long_word, font, anchor_x=80)
        assert suffix_x <= 155

    def test_custom_anchor(self):
        font = FakeFont(10)
        _, _, _, _, orp_x, _ = calc_orp_positions('abc', font, anchor_x=100)
        # orp_x = 100 - 10//2 = 95
        assert orp_x == 95


# ---------------------------------------------------------------------------
# calc_bold_split
# ---------------------------------------------------------------------------

class TestCalcBoldSplit:
    def test_single_char(self):
        bold, fade = calc_bold_split('a')
        assert bold == 'a'
        assert fade == ''

    def test_two_chars(self):
        bold, fade = calc_bold_split('ab')
        # max(1, int(0.8)) = max(1, 0) = 1
        assert bold == 'a'
        assert fade == 'b'

    def test_five_chars(self):
        bold, fade = calc_bold_split('hello')
        # max(1, int(2.0)) = 2
        assert bold == 'he'
        assert fade == 'llo'

    def test_ten_chars(self):
        bold, fade = calc_bold_split('abcdefghij')
        # max(1, int(4.0)) = 4
        assert bold == 'abcd'
        assert fade == 'efghij'

    def test_bold_always_at_least_one(self):
        """Bold part should always have at least one character."""
        for length in range(1, 20):
            word = 'a' * length
            bold, fade = calc_bold_split(word)
            assert len(bold) >= 1
            assert bold + fade == word
