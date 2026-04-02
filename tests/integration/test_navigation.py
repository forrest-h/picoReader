"""Integration tests for word stepping and navigation.

Tests encoder-based word stepping when paused, chapter jumping, and jump mode.
"""
import pytest

pytestmark = pytest.mark.integration


def test_word_step_forward_while_paused(sim):
    """Encoder clockwise while paused steps forward one word."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    state = sim.get_state()
    initial_word = state["wordIdx"]
    initial_line = state["lineNum"]

    # Step forward
    sim.turn_encoder(1)
    sim.sleep(300)

    state = sim.get_state()
    # Either wordIdx advanced or we moved to next line (wordIdx reset to 0)
    advanced = (state["wordIdx"] > initial_word or
                state["lineNum"] > initial_line)
    assert advanced, (
        f"Expected position to advance from line={initial_line} word={initial_word}, "
        f"got line={state['lineNum']} word={state['wordIdx']}"
    )


def test_word_step_backward_while_paused(sim):
    """Encoder counter-clockwise while paused steps backward one word."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    # Step forward a few times first to get past position 0
    for _ in range(3):
        sim.turn_encoder(1)
        sim.sleep(200)

    state = sim.get_state()
    fwd_word = state["wordIdx"]
    fwd_line = state["lineNum"]

    # Step backward
    sim.turn_encoder(-1)
    sim.sleep(300)

    state = sim.get_state()
    went_back = (state["wordIdx"] < fwd_word or
                 state["lineNum"] < fwd_line)
    assert went_back, (
        f"Expected position to go back from line={fwd_line} word={fwd_word}, "
        f"got line={state['lineNum']} word={state['wordIdx']}"
    )


def test_multiple_word_steps(sim):
    """Multiple encoder steps while paused move through multiple words."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    state = sim.get_state()
    start_word = state["wordIdx"]
    start_line = state["lineNum"]

    # Step forward 5 times
    for _ in range(5):
        sim.turn_encoder(1)
        sim.sleep(200)

    state = sim.get_state()
    # Should have advanced at least a few positions
    total_advance = ((state["lineNum"] - start_line) * 5 +
                     (state["wordIdx"] - start_word))
    assert total_advance > 0, "Position should have advanced after 5 steps"


def test_jump_mode_enter_and_exit(sim):
    """DOWN enters jump mode, UP cancels back to reader."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause first (jump mode requires paused)
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    # Enter jump mode
    sim.press_button("DOWN")
    sim.wait_for_state("state => state.mode === 3", timeout=3000)

    state = sim.get_state()
    assert state["mode"] == sim.MODE_JUMP

    # Cancel jump mode
    sim.press_button("UP")
    sim.wait_for_state("state => state.mode === 1", timeout=3000)

    state = sim.get_state()
    assert state["mode"] == sim.MODE_READER


def test_chapter_jump_forward(sim):
    """RIGHT while paused jumps to the next chapter (Chapter Book fixture)."""
    sim.start_reading_book("Chapter Book")
    sim.wait_for_state("state => state.mode === 1 && state.playing", timeout=5000)

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    state = sim.get_state()
    initial_line = state["lineNum"]

    # Jump to next chapter
    sim.press_button("RIGHT")
    sim.sleep(500)

    state = sim.get_state()
    # Position should have advanced past initial
    assert state["lineNum"] > initial_line, (
        f"Expected line to advance past {initial_line}, got {state['lineNum']}"
    )


def test_chapter_jump_backward(sim):
    """LEFT while paused jumps to the previous chapter."""
    sim.start_reading_book("Chapter Book")
    sim.wait_for_state("state => state.mode === 1 && state.playing", timeout=5000)

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    # Jump forward first
    sim.press_button("RIGHT")
    sim.sleep(500)

    state = sim.get_state()
    after_fwd_line = state["lineNum"]

    # Jump backward
    sim.press_button("LEFT")
    sim.sleep(500)

    state = sim.get_state()
    assert state["lineNum"] < after_fwd_line, (
        f"Expected line to go back from {after_fwd_line}, got {state['lineNum']}"
    )
