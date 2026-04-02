"""Integration test fixtures and SimulatorHelper for Playwright-driven tests.

Requires: simulator running at http://localhost:5173 (cd simulator && npm run dev)
"""
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import Page

SIMULATOR_URL = "http://localhost:5173"

# How long to wait for Pyodide cold-start (downloading WASM, loading shims, etc.)
PYODIDE_TIMEOUT = 30_000  # ms


@pytest.fixture(scope="session")
def simulator_url():
    """Base URL of the running Vite dev server."""
    return SIMULATOR_URL


@pytest.fixture(scope="session", autouse=True)
def install_test_books():
    """Copy test book fixtures to the simulator's public assets directory."""
    src = Path(__file__).parent / "fixtures" / "books"
    dst = Path(__file__).parent.parent.parent / "simulator" / "public" / "assets" / "books"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for book_file in src.glob("*.txt"):
        target = dst / book_file.name
        shutil.copy2(book_file, target)
        copied.append(target)
    yield
    for target in copied:
        target.unlink(missing_ok=True)


@pytest.fixture
def page(browser, simulator_url):
    """Fresh browser page with simulator loaded and ready.

    Each test gets its own page (browser context). The fixture waits
    for the Pyodide worker to fully initialize and the main loop to
    start sending state before yielding.
    """
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(simulator_url)
    # Wait for Pyodide to finish loading
    pg.wait_for_function(
        "() => window.__picoReaderApp?.isReady()",
        timeout=PYODIDE_TIMEOUT,
    )
    # Wait for the main loop to start and send initial state
    pg.wait_for_function(
        "() => window.__picoReaderApp?.getLastState() !== null",
        timeout=PYODIDE_TIMEOUT,
    )
    yield pg
    ctx.close()


@pytest.fixture
def sim(page):
    """SimulatorHelper wrapping common test operations."""
    return SimulatorHelper(page)


class SimulatorHelper:
    """High-level interface for driving the picoReader simulator in tests."""

    # Button name -> key number mapping (matches firmware constants)
    BUTTONS = {
        "CENTER": 0,
        "UP": 1,
        "LEFT": 2,
        "RIGHT": 3,
        "DOWN": 4,
    }

    # Firmware mode constants
    MODE_MENU = 0
    MODE_READER = 1
    MODE_DISPLAY = 2
    MODE_JUMP = 3

    def __init__(self, page: Page):
        self.page = page
        self._encoder_position = 0

    def press_button(self, button_name: str):
        """Send a button press event to the worker.

        Args:
            button_name: One of CENTER, UP, DOWN, LEFT, RIGHT.
        """
        key_number = self.BUTTONS[button_name]
        self.page.evaluate(
            f"window.__picoReaderApp.pressButton({key_number})"
        )

    def turn_encoder(self, steps: int):
        """Send encoder rotation. Positive = clockwise, negative = counter-clockwise.

        Sends a single position update (not individual steps), matching
        how the real encoder reports cumulative position changes.
        """
        self._encoder_position += steps
        self.page.evaluate(
            f"window.__picoReaderApp.setEncoderPosition({self._encoder_position})"
        )

    def get_state(self) -> dict | None:
        """Read the latest state snapshot from the state tracker.

        Returns a dict with keys: mode, wpm, playing, finished, bookId,
        lineNum, wordIdx, themeIndex, brightness, bookTitle, bookAuthor,
        bookLen, menuBreadcrumb, menuCursor, menuDepth, etc.
        Returns None if no state has been received yet.
        """
        return self.page.evaluate(
            "window.__picoReaderApp.getLastState()"
        )

    def wait_for_state(self, js_predicate: str, timeout: int = 5000):
        """Wait until the state tracker reports a state matching the predicate.

        Args:
            js_predicate: A JS expression that receives `state` and returns bool.
                Example: "state => state.mode === 1 && state.playing"
            timeout: Maximum wait time in milliseconds.

        Raises:
            TimeoutError: If the predicate isn't satisfied within timeout.
        """
        self.page.wait_for_function(
            f"""() => {{
                const state = window.__picoReaderApp?.getLastState();
                if (!state) return false;
                return ({js_predicate})(state);
            }}""",
            timeout=timeout,
        )

    def get_console_output(self) -> list[str]:
        """Get all console messages accumulated since page load."""
        return self.page.evaluate(
            "window.__picoReaderApp.getConsoleMessages()"
        )

    def wait_for_console(self, substring: str, timeout: int = 5000):
        """Wait until a console message containing the substring appears."""
        escaped = substring.replace("'", "\\'")
        self.page.wait_for_function(
            f"""() => {{
                const msgs = window.__picoReaderApp?.getConsoleMessages() || [];
                return msgs.some(m => m.includes('{escaped}'));
            }}""",
            timeout=timeout,
        )

    def restart(self, saves: dict[str, str] | None = None):
        """Reload the simulator, optionally pre-loading save data.

        Args:
            saves: Dict mapping filenames to save data strings.
                Example: {"save_book.txt": "42"}
                If None, starts with whatever is in localStorage.
        """
        if saves is not None:
            # Clear existing saves and inject new ones
            self.page.evaluate("localStorage.clear()")
            for filename, data in saves.items():
                # Use page.evaluate with argument passing to avoid JS escaping issues
                self.page.evaluate(
                    """([key, val]) => localStorage.setItem(key, val)""",
                    [f"picoReader_save_{filename}", data],
                )

        self.page.reload()
        self.page.wait_for_function(
            "() => window.__picoReaderApp?.isReady()",
            timeout=PYODIDE_TIMEOUT,
        )
        # Wait for the first state message from the worker's main loop
        self.page.wait_for_function(
            "() => window.__picoReaderApp?.getLastState() !== null",
            timeout=PYODIDE_TIMEOUT,
        )
        self._encoder_position = 0

    def sleep(self, ms: int):
        """Wait for a fixed duration. Use sparingly -- prefer wait_for_state."""
        self.page.wait_for_timeout(ms)

    def enter_all_books(self):
        """From root menu, navigate to 'All Books' (cursor 0) and drill into it.

        Ensures we're at the root menu first, then scrolls cursor to 0 if needed.
        """
        self.wait_for_state("state => state.mode === 0")

        state = self.get_state()
        depth = state.get("menuDepth", 0) if state else 0

        # If we're in a sub-menu, go back to root first
        while depth > 0:
            self.press_button("UP")
            self.sleep(300)
            state = self.get_state()
            depth = state.get("menuDepth", 0) if state else 0

        # Scroll to cursor 0 (All Books)
        cursor = state.get("menuCursor", 0) if state else 0
        if cursor != 0:
            # Scroll backwards to reach 0
            for _ in range(cursor):
                self.turn_encoder(-1)
                self.sleep(150)
            self.wait_for_state(
                "state => state.menuCursor === 0",
                timeout=3000,
            )

        self.press_button("CENTER")
        self.sleep(300)
        # Verify we drilled into a sub-menu (still in menu mode, depth > 0)
        self.wait_for_state("state => state.mode === 0 && state.menuDepth > 0", timeout=3000)

    def select_book_at_cursor(self, target_cursor: int):
        """From within a book list menu, scroll to a specific cursor position and select.

        Args:
            target_cursor: The cursor index of the book to select.
        """
        state = self.get_state()
        current = state.get("menuCursor", 0) if state else 0

        # Scroll to the target position
        diff = target_cursor - current
        for _ in range(abs(diff)):
            self.turn_encoder(1 if diff > 0 else -1)
            self.sleep(200)

        self.wait_for_state(
            f"state => state.menuCursor === {target_cursor}",
            timeout=3000,
        )
        self.press_button("CENTER")

    def start_reading_first_book(self):
        """Navigate through menu and start reading the first available book.

        Enters All Books, selects the first book, and waits for reader mode.
        """
        self.enter_all_books()
        self.press_button("CENTER")
        self.wait_for_state(
            "state => state.mode === 1",
            timeout=5000,
        )

    # Sorted book positions within "All Books" (alphabetical by title):
    # 0: A Wizard Of Earthsea
    # 1: Chapter Book
    # 2: Five Lines
    # 3: Golden Son
    # 4: Morning Star
    # 5: Short Story
    BOOK_CURSOR = {
        "Earthsea": 0,
        "Chapter Book": 1,
        "Five Lines": 2,
        "Golden Son": 3,
        "Morning Star": 4,
        "Short Story": 5,
    }

    def start_reading_book(self, book_name: str):
        """Navigate through menu, find a specific book by name, and start reading.

        Args:
            book_name: Key from BOOK_CURSOR dict (e.g. 'Short Story').
        """
        cursor = self.BOOK_CURSOR.get(book_name)
        if cursor is None:
            raise ValueError(f"Unknown book name '{book_name}'. Known: {list(self.BOOK_CURSOR.keys())}")
        self.enter_all_books()
        self.select_book_at_cursor(cursor)
        self.wait_for_state(
            "state => state.mode === 1",
            timeout=5000,
        )
