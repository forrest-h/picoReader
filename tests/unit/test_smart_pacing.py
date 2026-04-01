import pytest
from unittest.mock import patch
from pico_reader.state import AppState, calculate_word_delay


class TestCalculateWordDelay:
    """Tests for calculate_word_delay() multiplier logic."""

    BASE_WPM = 200
    BASE_DELAY = 60.0 / 200  # 0.3s

    def test_normal_word(self):
        """4-8 char word with no punctuation: 1.0x multiplier."""
        delay = calculate_word_delay("hello", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY)

    def test_short_word(self):
        """<=3 char word: 0.8x multiplier."""
        delay = calculate_word_delay("the", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 0.8)

    def test_long_word(self):
        """>8 char word: 1.3x multiplier."""
        delay = calculate_word_delay("wonderful", self.BASE_WPM, False, 1.0)
        assert len("wonderful") > 8
        assert delay == pytest.approx(self.BASE_DELAY * 1.3)

    def test_comma_ending(self):
        """Word ending in comma: 1.5x multiplier."""
        delay = calculate_word_delay("hello,", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.5)

    def test_semicolon_ending(self):
        """Word ending in semicolon: 1.5x multiplier."""
        delay = calculate_word_delay("thus;", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.5)

    def test_colon_ending(self):
        """Word ending in colon: 1.5x multiplier."""
        delay = calculate_word_delay("said:", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.5)

    def test_sentence_end_period(self):
        """Word ending in period: 1.8x multiplier."""
        delay = calculate_word_delay("done.", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.8)

    def test_sentence_end_exclamation(self):
        """Word ending in !: 1.8x multiplier."""
        delay = calculate_word_delay("wow!", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.8)

    def test_sentence_end_question(self):
        """Word ending in ?: 1.8x multiplier."""
        delay = calculate_word_delay("what?", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.8)

    def test_long_plus_sentence_end(self):
        """Long word + sentence end: 1.3 * 1.8 = 2.34x."""
        delay = calculate_word_delay("wonderful.", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.3 * 1.8)

    def test_paragraph_start(self):
        """Paragraph start: 1.4x multiplier on normal word."""
        delay = calculate_word_delay("Hello", self.BASE_WPM, True, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.4)

    def test_paragraph_start_plus_long_plus_sentence_end(self):
        """All multipliers stacked: 1.4 * 1.3 * 1.8 = 3.276x."""
        delay = calculate_word_delay("wonderful.", self.BASE_WPM, True, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.4 * 1.3 * 1.8)

    def test_trailing_double_quote(self):
        """Trailing quote stripped before checking punctuation: said." -> sentence end."""
        delay = calculate_word_delay('said."', self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.8)

    def test_trailing_single_quote(self):
        """Trailing single quote stripped: done.' -> sentence end."""
        delay = calculate_word_delay("done.'", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.8)

    def test_trailing_paren(self):
        """Trailing paren stripped: end.) -> sentence end."""
        delay = calculate_word_delay("end.)", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 1.8)

    def test_empty_word(self):
        """Empty word returns base delay, no crash."""
        delay = calculate_word_delay("", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY)

    def test_punctuation_only(self):
        """Punctuation-only word like '...' has stripped become empty, returns base delay."""
        delay = calculate_word_delay('"', self.BASE_WPM, False, 1.0)
        # After stripping quotes, empty -> returns base delay
        assert delay == pytest.approx(self.BASE_DELAY)

    def test_ramp_factor_half(self):
        """Ramp factor 0.5 doubles the base delay."""
        delay = calculate_word_delay("hello", self.BASE_WPM, False, 0.5)
        expected = 60.0 / (self.BASE_WPM * 0.5)
        assert delay == pytest.approx(expected)

    def test_ramp_factor_with_multipliers(self):
        """Ramp factor applies to effective WPM, then multipliers stack on top."""
        delay = calculate_word_delay("wonderful.", self.BASE_WPM, False, 0.5)
        expected = 60.0 / (self.BASE_WPM * 0.5) * 1.3 * 1.8
        assert delay == pytest.approx(expected)

    def test_short_word_with_comma(self):
        """Short word (<=3) with comma: 0.8 * 1.5 = 1.2x."""
        delay = calculate_word_delay("so,", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY * 0.8 * 1.5)

    def test_exactly_8_chars_not_long(self):
        """8-char word is NOT >8, so no long multiplier."""
        word = "12345678"
        assert len(word) == 8
        delay = calculate_word_delay(word, self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY)

    def test_exactly_4_chars_not_short(self):
        """4-char word is NOT <=3, so no short multiplier."""
        delay = calculate_word_delay("word", self.BASE_WPM, False, 1.0)
        assert delay == pytest.approx(self.BASE_DELAY)


class TestRampFactor:
    """Tests for AppState.get_ramp_factor() time-based ramp."""

    def test_ramp_at_t0(self):
        """At t=0 seconds: factor = 0.5."""
        s = AppState(settings={'smart_pacing': 'on'})
        with patch('time.monotonic', return_value=100.0):
            s.start_playing()
        with patch('time.monotonic', return_value=100.0):
            assert s.get_ramp_factor() == pytest.approx(0.5)

    def test_ramp_at_t5(self):
        """At t=5 seconds: factor = 0.75."""
        s = AppState(settings={'smart_pacing': 'on'})
        with patch('time.monotonic', return_value=100.0):
            s.start_playing()
        with patch('time.monotonic', return_value=105.0):
            assert s.get_ramp_factor() == pytest.approx(0.75)

    def test_ramp_at_t10(self):
        """At t=10 seconds: factor = 1.0."""
        s = AppState(settings={'smart_pacing': 'on'})
        with patch('time.monotonic', return_value=100.0):
            s.start_playing()
        with patch('time.monotonic', return_value=110.0):
            assert s.get_ramp_factor() == pytest.approx(1.0)

    def test_ramp_at_t15_clamped(self):
        """At t=15 seconds: factor = 1.0 (clamped, not 1.25)."""
        s = AppState(settings={'smart_pacing': 'on'})
        with patch('time.monotonic', return_value=100.0):
            s.start_playing()
        with patch('time.monotonic', return_value=115.0):
            assert s.get_ramp_factor() == pytest.approx(1.0)

    def test_ramp_disabled(self):
        """When smart_pacing is off, factor is always 1.0."""
        s = AppState(settings={'smart_pacing': 'off'})
        with patch('time.monotonic', return_value=100.0):
            s.start_playing()
        with patch('time.monotonic', return_value=100.0):
            assert s.get_ramp_factor() == pytest.approx(1.0)

    def test_ramp_default_off(self):
        """Default settings have smart_pacing off."""
        s = AppState()
        assert s.smart_pacing is False
        assert s.get_ramp_factor() == pytest.approx(1.0)


class TestStartPlaying:
    """Tests for AppState.start_playing()."""

    def test_sets_playing_true(self):
        s = AppState()
        assert s.playing is False
        with patch('time.monotonic', return_value=42.0):
            s.start_playing()
        assert s.playing is True

    def test_records_start_time(self):
        s = AppState()
        with patch('time.monotonic', return_value=42.0):
            s.start_playing()
        assert s.play_start_time == pytest.approx(42.0)

    def test_smart_pacing_from_settings(self):
        s = AppState(settings={'smart_pacing': 'on'})
        assert s.smart_pacing is True

    def test_smart_pacing_off_from_settings(self):
        s = AppState(settings={'smart_pacing': 'off'})
        assert s.smart_pacing is False
