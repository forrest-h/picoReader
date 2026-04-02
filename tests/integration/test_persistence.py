"""Integration tests for save/restore persistence.

Tests that reading positions survive simulator restarts via localStorage.
"""
import pytest

pytestmark = pytest.mark.integration


def test_save_position_persists(sim):
    """Reading position is restored after simulator restart."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Let it play for 2 seconds to advance position
    sim.sleep(2000)

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    state = sim.get_state()
    saved_line = state["lineNum"]
    saved_book_id = state["bookId"]

    # Go to menu to trigger save
    sim.press_button("UP")
    sim.wait_for_state("state => state.mode === 0", timeout=3000)
    sim.sleep(500)

    # Restart the simulator (saves persist via localStorage)
    sim.restart()

    # Verify we're back in menu mode
    state = sim.get_state()
    assert state["mode"] == sim.MODE_MENU

    # Select the same book again
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause immediately
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    state = sim.get_state()
    # Position should be at or very close to where we left off.
    # The periodic save might lag slightly, so allow tolerance.
    assert state["bookId"] == saved_book_id, "Book ID should match after restart"
    # lineNum should be within a few lines of where we saved
    assert abs(state["lineNum"] - saved_line) <= 10, (
        f"Expected lineNum near {saved_line}, got {state['lineNum']}"
    )


def test_explicit_save_data_injection(sim):
    """Restarting with explicit save data injects it correctly."""
    # Check what format the settings file uses
    # The settings module uses key:value per line
    sim.restart(saves={"settings.txt": "palette:2\nbrightness:75"})

    # Start reading to observe settings
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1", timeout=5000)

    state = sim.get_state()
    assert state["themeIndex"] == 2, (
        f"Expected theme 2 from injected settings, got {state['themeIndex']}"
    )
    assert state["brightness"] == 75, (
        f"Expected brightness 75 from injected settings, got {state['brightness']}"
    )


def test_clean_start_with_no_saves(sim):
    """Restarting with empty saves gives default state."""
    sim.restart(saves={})

    state = sim.get_state()
    assert state["mode"] == sim.MODE_MENU
    assert state["themeIndex"] == 0  # default
    assert state["wpm"] == 200  # DEFAULT_WPM


def test_per_book_save_independence(sim):
    """Saves for different books are independent."""
    # Select and read book A (first book)
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")
    sim.sleep(1500)  # Let it advance

    # Pause and record position
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)
    state_a = sim.get_state()
    line_a = state_a["lineNum"]

    # Go to menu
    sim.press_button("UP")
    sim.wait_for_state("state => state.mode === 0", timeout=3000)
    sim.sleep(500)

    # Now read a different book (second in all books = Chapter Book)
    sim.enter_all_books()
    sim.select_book_at_cursor(1)  # Chapter Book
    sim.wait_for_state("state => state.mode === 1", timeout=5000)
    sim.sleep(1000)

    # Pause
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    # Go to menu
    sim.press_button("UP")
    sim.wait_for_state("state => state.mode === 0", timeout=3000)
    sim.sleep(500)

    # Now go back to book A and verify position is preserved
    sim.enter_all_books()
    sim.select_book_at_cursor(0)  # First book (A Wizard of Earthsea)
    sim.wait_for_state("state => state.mode === 1", timeout=5000)

    # Pause to check position
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    state = sim.get_state()
    # Should be near where we left off on book A
    assert abs(state["lineNum"] - line_a) <= 10, (
        f"Expected lineNum near {line_a} for book A, got {state['lineNum']}"
    )
