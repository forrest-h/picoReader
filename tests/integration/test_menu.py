"""Integration tests for menu navigation.

Tests root menu visibility, scrolling, book selection, hierarchical drill-down,
and back navigation.
"""
import pytest

pytestmark = pytest.mark.integration


def test_starts_in_menu_mode(sim):
    """After load, the simulator is in menu mode."""
    state = sim.get_state()
    assert state is not None
    assert state["mode"] == sim.MODE_MENU
    assert state["menuDepth"] == 0


def test_root_menu_has_breadcrumb(sim):
    """The root menu breadcrumb shows 'picoReader'."""
    state = sim.get_state()
    assert state["menuBreadcrumb"] == "picoReader"


def test_menu_scroll_changes_cursor(sim):
    """Encoder rotation in menu mode changes the cursor position."""
    state = sim.get_state()
    initial_cursor = state["menuCursor"]

    sim.turn_encoder(1)
    sim.wait_for_state(
        f"state => state.menuCursor !== {initial_cursor}",
        timeout=3000,
    )
    state = sim.get_state()
    assert state["menuCursor"] != initial_cursor


def test_drill_into_all_books(sim):
    """Selecting 'All Books' (first root item) drills into the book list."""
    # Cursor starts at 0, which is "All Books"
    sim.press_button("CENTER")
    sim.wait_for_state(
        "state => state.mode === 0 && state.menuDepth > 0",
        timeout=3000,
    )
    state = sim.get_state()
    assert state["menuDepth"] >= 1
    assert state["menuBreadcrumb"] == "All Books"


def test_select_book_enters_reader(sim):
    """Selecting a book from the All Books list enters reader mode."""
    sim.start_reading_first_book()
    state = sim.get_state()
    assert state["mode"] == sim.MODE_READER


def test_return_to_menu_from_reader(sim):
    """UP while paused in reader mode returns to menu."""
    sim.start_reading_first_book()
    sim.wait_for_state("state => state.mode === 1 && state.playing")

    # Pause first
    sim.press_button("CENTER")
    sim.wait_for_state("state => state.playing === false", timeout=3000)

    # Go back to menu
    sim.press_button("UP")
    sim.wait_for_state("state => state.mode === 0", timeout=3000)

    state = sim.get_state()
    assert state["mode"] == sim.MODE_MENU


def test_back_navigation_from_submenu(sim):
    """UP in a sub-menu goes back to root."""
    # Drill into All Books
    sim.press_button("CENTER")
    sim.wait_for_state(
        "state => state.mode === 0 && state.menuDepth > 0",
        timeout=3000,
    )

    # Go back to root
    sim.press_button("UP")
    sim.wait_for_state(
        "state => state.mode === 0 && state.menuDepth === 0",
        timeout=3000,
    )
    state = sim.get_state()
    assert state["menuDepth"] == 0
    assert state["menuBreadcrumb"] == "picoReader"


def test_drill_into_authors(sim):
    """Navigating to 'Authors' and selecting drills into author list."""
    # Authors is at cursor position 2 (All Books=0, Recently Read=1, Authors=2)
    sim.turn_encoder(1)  # -> Recently Read
    sim.sleep(200)
    sim.turn_encoder(1)  # -> Authors
    sim.sleep(200)

    sim.press_button("CENTER")
    sim.wait_for_state(
        "state => state.mode === 0 && state.menuDepth > 0",
        timeout=3000,
    )
    state = sim.get_state()
    assert state["menuDepth"] >= 1
    assert "Authors" in state.get("menuBreadcrumb", "")


def test_drill_into_series(sim):
    """Navigating to 'Series' and selecting drills into series list."""
    # Series is at cursor position 3
    for _ in range(3):
        sim.turn_encoder(1)
        sim.sleep(200)

    sim.press_button("CENTER")
    sim.wait_for_state(
        "state => state.mode === 0 && state.menuDepth > 0",
        timeout=3000,
    )
    state = sim.get_state()
    assert state["menuDepth"] >= 1
    assert "Series" in state.get("menuBreadcrumb", "")


def test_scroll_wraps_around(sim):
    """Scrolling past the last menu item wraps to the first."""
    # The root menu has 6 items: All Books, Recently Read, Authors,
    # Series, Genres, Settings.
    # Scroll forward 6 times to wrap around.
    for _ in range(6):
        sim.turn_encoder(1)
        sim.sleep(200)

    state = sim.get_state()
    # Cursor should have wrapped back to 0
    assert state["menuCursor"] == 0
