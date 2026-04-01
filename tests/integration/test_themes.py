"""Integration tests for theme state, brightness, and WPM settings.

Tests observable state values and their defaults, plus WPM persistence.
Display mode theme cycling is not directly accessible in v2 firmware from
reader mode (LEFT/RIGHT are chapter navigation), so we test through
settings injection and state observation.
"""
import pytest

pytestmark = pytest.mark.integration


def test_default_brightness(sim):
    """Default brightness is 50%."""
    state = sim.get_state()
    assert state["brightness"] == 50  # DEFAULT_BRIGHTNESS


def test_brightness_in_valid_range(sim):
    """Brightness value is within 1-100."""
    state = sim.get_state()
    assert 1 <= state["brightness"] <= 100


def test_default_theme(sim):
    """Default theme index is 0."""
    state = sim.get_state()
    assert state["themeIndex"] == 0


def test_default_wpm(sim):
    """Default WPM is 200."""
    state = sim.get_state()
    assert state["wpm"] == 200


def test_theme_from_injected_settings(sim):
    """Theme index can be set via injected settings on restart."""
    sim.restart(saves={"settings.txt": "palette:3"})

    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1", timeout=5000)

    state = sim.get_state()
    assert state["themeIndex"] == 3, (
        f"Expected theme 3 from injected settings, got {state['themeIndex']}"
    )


def test_brightness_from_injected_settings(sim):
    """Brightness can be set via injected settings on restart."""
    sim.restart(saves={"settings.txt": "brightness:80"})

    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1", timeout=5000)

    state = sim.get_state()
    assert state["brightness"] == 80, (
        f"Expected brightness 80 from injected settings, got {state['brightness']}"
    )


def test_wpm_adjustment_while_playing(sim):
    """Encoder rotation while playing adjusts WPM."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    state = sim.get_state()
    initial_wpm = state["wpm"]

    # Increase WPM
    sim.turn_encoder(1)
    sim.wait_for_state(f"state => state.wpm > {initial_wpm}", timeout=3000)

    state = sim.get_state()
    assert state["wpm"] > initial_wpm


def test_wpm_changes_persist_in_session(sim):
    """WPM changes survive pause/resume within a session."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Adjust WPM up
    sim.turn_encoder(1)
    sim.sleep(200)
    sim.turn_encoder(1)
    sim.sleep(200)

    state = sim.get_state()
    adjusted_wpm = state["wpm"]
    assert adjusted_wpm > 200

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    # WPM should still be the adjusted value
    state = sim.get_state()
    assert state["wpm"] == adjusted_wpm

    # Resume
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === true", timeout=3000)

    state = sim.get_state()
    assert state["wpm"] == adjusted_wpm


def test_mode_transitions_preserve_state(sim):
    """Going to menu and back preserves mode state correctly."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    # Go to menu
    sim.press_button("UP")
    sim.wait_for_state("state => state.mode === 0", timeout=3000)

    state = sim.get_state()
    assert state["mode"] == sim.MODE_MENU

    # Re-enter by selecting a book
    sim.enter_all_books()
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.mode === 1", timeout=5000)

    state = sim.get_state()
    assert state["mode"] == sim.MODE_READER
