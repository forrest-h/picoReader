"""Integration tests for core RSVP reading flow.

Tests start/pause/resume, WPM adjustment, word progression, and end-of-book.
"""
import pytest

pytestmark = pytest.mark.integration


def test_select_book_starts_reading(sim):
    """Selecting a book from the menu enters reader mode with playing=true."""
    sim.start_reading_first_book()
    state = sim.get_state()
    assert state["mode"] == sim.MODE_READER
    assert state["playing"] is True
    assert state["finished"] is False


def test_pause_resume(sim):
    """CENTER toggles play/pause in reader mode."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)
    state = sim.get_state()
    assert state["playing"] is False

    # Resume
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === true", timeout=3000)
    state = sim.get_state()
    assert state["playing"] is True


def test_wpm_adjustment_while_playing(sim):
    """Encoder rotation while playing adjusts WPM."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    state = sim.get_state()
    initial_wpm = state["wpm"]
    assert initial_wpm == 200  # DEFAULT_WPM

    # Increase WPM (clockwise encoder)
    sim.turn_encoder(1)
    sim.wait_for_state(f"state => state.wpm > {initial_wpm}", timeout=3000)
    state = sim.get_state()
    assert state["wpm"] > initial_wpm

    higher_wpm = state["wpm"]

    # Decrease WPM (counter-clockwise, 2 steps to go below initial)
    sim.turn_encoder(-1)
    sim.sleep(100)
    sim.turn_encoder(-1)
    sim.wait_for_state(f"state => state.wpm < {higher_wpm}", timeout=3000)
    state = sim.get_state()
    assert state["wpm"] < higher_wpm


def test_word_display_progresses(sim):
    """While playing, lineNum or wordIdx should advance over time."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    state = sim.get_state()
    initial_line = state["lineNum"]
    initial_word = state["wordIdx"]

    # Wait for a few words to be displayed (at 200 WPM, ~300ms per word)
    sim.sleep(2000)

    state = sim.get_state()
    # Either line or word index should have advanced
    assert (state["lineNum"] > initial_line or
            state["wordIdx"] > initial_word), \
        f"Position did not advance: line {initial_line}->{state['lineNum']}, " \
        f"word {initial_word}->{state['wordIdx']}"


def test_end_of_short_book(sim):
    """Reading the Short Story test book (20 words) should reach finished state."""
    sim.start_reading_book("Short Story")

    # Should now be in reader mode, playing
    sim.wait_for_state("state => state.mode === 1 && state.playing", timeout=5000)

    # At 200 WPM, 20 words ~= 6 seconds. With smart pacing overhead, allow 20s.
    sim.wait_for_state("state => state.finished === true", timeout=25000)

    state = sim.get_state()
    assert state["playing"] is False
    assert state["finished"] is True


def test_finished_book_restart(sim):
    """After finishing a book, CENTER should restart from the beginning."""
    sim.start_reading_book("Short Story")

    sim.wait_for_state("state => state.mode === 1 && state.playing", timeout=5000)
    sim.wait_for_state("state => state.finished === true", timeout=25000)

    # Press CENTER to restart
    sim.press_button("CENTER")
    sim.wait_for_state(
        "state => state.playing === true && state.finished === false",
        timeout=5000,
    )
    state = sim.get_state()
    assert state["lineNum"] == 0
