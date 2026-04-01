# Phase 6: Integration Tests — Playwright-Driven Simulator Testing

> **Dependency:** Phase 1 (module split, test infra). Phases 2-5 add features that Phase 6 tests, but the test infrastructure itself only requires Phase 1's module structure and the simulator's state tracker.

**Goal:** Build a Playwright-driven integration test suite that exercises the picoReader firmware through the browser simulator. Tests interact exclusively via button presses and encoder turns (same as real hardware), and verify behavior through the state tracker's postMessage snapshots. No pixel-level assertions except for targeted visual spot-checks.

---

## 1. Simulator Prerequisites

Phase 6 tests run against the simulator, which must be updated to support everything that earlier phases add. Some of these updates happen naturally during Phases 1-5; this section documents what must be in place before integration tests can pass.

### 1.1 Worker.ts must mount `pico_reader/` modules

Phase 1 splits `code.py` into `pico_reader/*.py` modules. Worker.ts currently fetches a single `code.py` and writes it to `/app/code.py`. After Phase 1, it must also fetch and mount the module files:

```
/app/pico_reader/__init__.py
/app/pico_reader/constants.py
/app/pico_reader/hardware.py
/app/pico_reader/state.py
/app/pico_reader/book_reader.py
/app/pico_reader/display.py
/app/pico_reader/input_handlers.py
/app/pico_reader/utils.py
/app/pico_reader/main.py
/app/pico_reader/settings.py
```

The file list can be hardcoded in worker.ts (a manifest approach is unnecessary for 10 files). The fetch loop mirrors the existing shim-loading pattern: `fetch('/firmware/pico_reader/${name}.py')` for each file, then `pyodide.FS.writeFile()`.

### 1.2 Settings file mirrored to/from localStorage

Phase 1 adds `saves/settings.txt`. The existing save-mirroring in worker.ts already catches all `/saves/*` writes and posts them as `{type: 'save', filename, data}` messages. The main thread's handler already persists these under `picoReader_save_${filename}` in localStorage. On init, all `picoReader_save_*` keys are loaded and written to `/saves/` in Pyodide FS.

**This means settings persistence is already covered by the existing plumbing** -- `settings.txt` is just another file in `/saves/`. No additional worker.ts changes needed for settings mirroring, as long as the monkey-patched save functions (or a new settings-save hook) post the file contents.

However, `settings.py` writes directly via `open()`, not through `BookReader.save_place()`. The monkey-patched save intercept only catches `BookReader.save_place` and `BookReader.save_backup`. We need one of:

- **Option A:** Monkey-patch `settings.save_settings()` in the same pattern. Simple, but requires adding a new patch every time a new save function appears.
- **Option B:** Intercept at the filesystem level -- override Python's built-in `open()` for writes to `/saves/*`. More robust but more invasive.
- **Option C:** Have `save_settings()` call a bridge function if available. The settings module checks for `_bridge.post_message` and posts save data itself.

**Decision: Option A.** It matches the existing pattern, is explicit, and settings saves are infrequent. The worker's Python wrapper already monkey-patches two functions; adding a third for `settings.save_settings` is straightforward.

### 1.3 State tracker expanded fields

The current `_state_tracker.py` sends: `mode`, `wpm`, `playing`, `finished`, `themeIndex`, `brightness`, `bookId`, `lineNum`, `wordIdx`, `bookLen`, `bookTitle`, `bookAuthor`.

Phases 2-5 add features that require new state fields for integration tests to verify. The state tracker must be extended to include:

| Field | Type | Source | Added by |
|---|---|---|---|
| `skinName` | string | `settings['skin']` | Phase 3 |
| `orpMode` | bool | `settings['orp']` | Phase 3 |
| `animationEnabled` | bool | `settings['animation']` | Phase 5 |
| `chapterIndex` | int | `book_reader.chapter_index` | Phase 2 |
| `chapterTitle` | string | `book_reader.current_chapter_title()` | Phase 2 |
| `menuDepth` | int | `state.menu_depth` or menu stack length | Phase 2 |
| `menuType` | string | `state.menu_type` (e.g. 'root', 'authors', 'books') | Phase 2 |
| `jumpMode` | bool | `state.jump_mode` | Phase 2 |
| `jumpPercent` | int | computed from position | Phase 2 |
| `paletteIndex` | int | `state.theme_index` (already present as `themeIndex`) | -- |
| `currentWord` | string | last word displayed | Phase 6 |
| `recentBooks` | list | recently read book titles | Phase 2 |

The `currentWord` field deserves special attention. The state tracker currently has no access to the displayed word -- it only tracks `AppState` and `BookReader`. To expose the current word, either:

- **Option A:** Add `state.current_word` to AppState, updated in the main loop when a word is shown.
- **Option B:** Read it from the display's word label text.

**Decision: Option A.** The word label text is padded with spaces (`:^30` format), and reading display internals couples the tracker to display implementation. A simple `state.current_word = cleaned` in the main loop is cleaner.

### 1.4 Test book files

Integration tests need tiny, deterministic book files. Real books are too large (1835-12557 words) for tests that need to reach end-of-book or verify specific positions.

Create test-specific books in `simulator/public/assets/books/` (or a `tests/fixtures/books/` directory that gets copied):

```
Test Author - Short Story (20).txt     # 20 words across 5 lines
Test Author - Five Lines (25).txt      # 25 words, for multi-book tests
(TestSeries 1) Test Author - Chapter Book (50).txt  # 50 words with chapter markers
```

**Decision:** Test books live in `tests/integration/fixtures/books/`. The test fixtures configure the simulator to load these instead of (or alongside) the real books. The `sim.restart(books=[...])` helper handles this by injecting book data into the worker's virtual filesystem before code.py runs.

### 1.5 Exposing a test API on the main thread

Tests need a JavaScript bridge to interact with the simulator. The current `App` class in `main.ts` is a module-scoped singleton with no global handle. Tests communicating via `page.evaluate()` need access to it.

Add to `main.ts`:

```typescript
// Expose for integration tests
(window as any).__picoReaderApp = app;
```

And add public methods to `App`:

```typescript
class App {
  // ... existing code ...

  /** Send a button press to the worker. Called by tests via page.evaluate(). */
  pressButton(keyNumber: number) {
    this.sendToWorker({ type: 'button', keyNumber, pressed: true });
  }

  /** Send an encoder position change to the worker. */
  setEncoderPosition(position: number) {
    this.sendToWorker({ type: 'encoder', position });
  }

  /** Get the latest state snapshot received from the worker. */
  getLastState(): StateMessage | null {
    return this._lastState;
  }

  /** Get accumulated console messages. */
  getConsoleMessages(): string[] {
    return this._consoleLog;
  }

  /** Check if the simulator is ready (worker has sent 'ready' message). */
  isReady(): boolean {
    return this._ready;
  }
}
```

The `App` class must cache `_lastState` (updated on every `state` message), `_consoleLog` (appended on every `console` message), and `_ready` (set on `ready` message).

---

## 2. Test Infrastructure

### 2.1 Directory structure

```
tests/
  integration/
    __init__.py
    conftest.py               # Playwright fixtures, SimulatorHelper
    fixtures/
      books/
        Test Author - Short Story (20).txt
        Test Author - Five Lines (25).txt
        (TestSeries 1) Test Author - Chapter Book (50).txt
    test_reading_flow.py
    test_navigation.py
    test_menu.py
    test_persistence.py
    test_themes.py
```

### 2.2 Dependencies

```
# requirements-test.txt (or added to pyproject.toml [test] extras)
pytest>=7.0
pytest-playwright>=0.4
```

Installation:

```bash
pip install pytest pytest-playwright
playwright install chromium
```

### 2.3 pytest configuration

In the project's `pytest.ini` (or `pyproject.toml`):

```ini
[pytest]
testpaths = tests
markers =
    unit: Unit tests (no browser required)
    integration: Integration tests (requires running simulator)
asyncio_mode = auto
```

All integration tests are implicitly marked via their location in `tests/integration/`. The marker allows selective runs:

```bash
# Run only integration tests
pytest tests/integration/ -v

# Run only unit tests
pytest tests/unit/ -v

# Run everything
pytest -v
```

---

## 3. conftest.py -- Fixtures and SimulatorHelper

### 3.1 Fixtures

```python
import pytest
from playwright.sync_api import Page

SIMULATOR_URL = "http://localhost:5173"

@pytest.fixture(scope="session")
def simulator_url():
    """Base URL of the running Vite dev server."""
    return SIMULATOR_URL

@pytest.fixture
def page(browser, simulator_url):
    """Fresh browser page with simulator loaded and ready.

    Each test gets its own page (browser context). The fixture waits
    for the Pyodide worker to send the 'ready' message before yielding.
    """
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(simulator_url)
    # Wait for Pyodide to finish loading (the loading overlay hides on 'ready')
    pg.wait_for_function(
        "() => window.__picoReaderApp?.isReady()",
        timeout=15000  # Pyodide cold-start can take 5-10s
    )
    yield pg
    ctx.close()

@pytest.fixture
def sim(page):
    """SimulatorHelper wrapping common test operations."""
    return SimulatorHelper(page)
```

**Why `scope="function"` for `page`:** Each test gets a clean simulator state. No leftover save data, no stale mode. The cost is Pyodide reinit per test (~3-5s), but correctness matters more than speed. If this becomes a bottleneck, we can add a `sim.reset()` that reloads the worker without a full page reload.

**Why `scope="session"` for `browser`:** pytest-playwright provides this by default. A single Chromium instance handles all tests.

### 3.2 SimulatorHelper class

```python
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
        """Send encoder rotation. Positive = clockwise, negative = counter.

        Sends a single position update (not individual steps), matching
        how the real encoder reports cumulative position changes.
        """
        self._encoder_position += steps
        self.page.evaluate(
            f"window.__picoReaderApp.setEncoderPosition({self._encoder_position})"
        )

    def get_state(self) -> dict:
        """Read the latest state snapshot from the state tracker.

        Returns a dict with keys: mode, wpm, playing, finished, bookId,
        lineNum, wordIdx, themeIndex, brightness, bookTitle, bookAuthor,
        bookLen, plus any Phase 2-5 additions.
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
        self.page.wait_for_function(
            f"""() => {{
                const msgs = window.__picoReaderApp?.getConsoleMessages() || [];
                return msgs.some(m => m.includes("{substring}"));
            }}""",
            timeout=timeout,
        )

    def restart(self, saves: dict[str, str] | None = None):
        """Reload the simulator, optionally pre-loading save data.

        Args:
            saves: Dict mapping filenames to save data strings.
                Example: {"save_book.txt": "42:7"}
                If None, starts with whatever is in localStorage.
        """
        if saves is not None:
            # Clear existing saves and inject new ones
            self.page.evaluate("localStorage.clear()")
            for filename, data in saves.items():
                self.page.evaluate(
                    f"localStorage.setItem('picoReader_save_{filename}', '{data}')"
                )

        self.page.reload()
        self.page.wait_for_function(
            "() => window.__picoReaderApp?.isReady()",
            timeout=15000,
        )
        self._encoder_position = 0

    def sleep(self, ms: int):
        """Wait for a fixed duration. Use sparingly -- prefer wait_for_state."""
        self.page.wait_for_timeout(ms)
```

### 3.3 Design decisions in the helper

**Why JS predicates for `wait_for_state` instead of Python lambdas:** Playwright's `wait_for_function` runs the predicate in the browser. If we polled from Python with `get_state()` in a loop, each poll would be a round-trip across the browser-Python boundary (~5ms each). Using a JS predicate lets the browser check at 60fps natively, and Python blocks until it resolves. This is both faster and more reliable for detecting transient states.

**Why track `_encoder_position` client-side:** The real encoder reports absolute position, not relative steps. The simulator's worker reads `__encoderPosition` and compares to its previous read. Our helper must maintain and increment a cumulative position, just like the real encoder hardware.

**Why `restart()` uses localStorage instead of postMessage:** The worker reads saves from the `init` message, which reads from localStorage. By writing to localStorage before reload, we ensure the worker picks up the right saves on its next `startPyodide()` call. This avoids the complexity of terminating and restarting the worker mid-page.

---

## 4. Test Suites

### 4.1 test_reading_flow.py

Tests the core RSVP reading experience: starting, pausing, resuming, WPM changes, end-of-book.

#### Test cases

**`test_select_book_starts_reading`**
1. Simulator starts in menu mode (mode=0)
2. Press CENTER to select the first book
3. `wait_for_state`: mode=1 (reader), playing=true
4. Assert bookTitle matches the first book's parsed title

**`test_pause_resume`**
1. Select book (CENTER), wait for playing state
2. Press CENTER to pause
3. `wait_for_state`: playing=false
4. Press CENTER again
5. `wait_for_state`: playing=true

**`test_wpm_adjustment_while_playing`**
1. Select book, wait for playing
2. Record initial WPM from state (should be DEFAULT_WPM=200)
3. Turn encoder clockwise (+1 step)
4. `wait_for_state`: wpm > initial_wpm
5. Turn encoder counter-clockwise (-2 steps)
6. `wait_for_state`: wpm < initial_wpm

**`test_word_display_progresses`**
1. Select book, wait for playing
2. Record lineNum and wordIdx
3. Wait 2 seconds (enough for several words at 200 WPM)
4. Read state again
5. Assert lineNum > initial or wordIdx > initial (position has advanced)

**`test_end_of_book`**
This test needs the Short Story test book (20 words). At 200 WPM, 20 words takes ~6 seconds.
1. Select the short book (may need encoder turns to navigate menu to it)
2. Press CENTER to start reading
3. `wait_for_state` with timeout=15000: finished=true
4. Assert state.playing is false

**`test_finished_book_restart`**
1. Reach end of book (reuse short book)
2. Press CENTER (should restart from beginning)
3. `wait_for_state`: playing=true, finished=false
4. Assert lineNum=0

#### Pseudocode for the most complex test

```python
def test_end_of_book(sim):
    # Navigate to the short test book -- it may not be the first book
    # in the menu, so we need to scroll to it.
    # Strategy: turn encoder until state shows the right bookTitle
    for _ in range(10):  # max attempts
        state = sim.get_state()
        if state and "Short Story" in (state.get("bookTitle") or ""):
            break
        sim.turn_encoder(1)
        sim.sleep(200)  # wait for menu to update

    sim.press_button("CENTER")
    sim.wait_for_state("state => state.mode === 1 && state.playing", timeout=5000)

    # At 200 WPM, 20 words ~= 6 seconds. Add margin.
    sim.wait_for_state("state => state.finished === true", timeout=15000)

    state = sim.get_state()
    assert state["playing"] is False
    assert state["finished"] is True
```

### 4.2 test_navigation.py

Tests word stepping, chapter jumping (Phase 2), jump mode (Phase 2), and position accuracy.

#### Test cases

**`test_word_step_forward_while_paused`**
1. Select book, wait for reader mode
2. Press CENTER to pause
3. Record wordIdx
4. Turn encoder clockwise (+1 step)
5. `wait_for_state`: wordIdx = previous + 1

**`test_word_step_backward_while_paused`**
1. Select book, pause
2. Step forward a few times to get past position 0
3. Record wordIdx
4. Turn encoder counter-clockwise (-1 step)
5. `wait_for_state`: wordIdx = previous - 1 (or lineNum decreased)

**`test_chapter_jump_forward`** (Phase 2 feature)
1. Select Chapter Book (has chapter markers), pause
2. Record chapterIndex from state
3. Press RIGHT (chapter next, when paused in Phase 2 reader mode)
4. `wait_for_state`: chapterIndex > previous

**`test_chapter_jump_backward`** (Phase 2 feature)
1. Jump forward first (to chapter > 0)
2. Press LEFT
3. `wait_for_state`: chapterIndex < previous

**`test_jump_mode`** (Phase 2 feature)
1. Select book, pause
2. Press DOWN to enter jump mode
3. `wait_for_state`: jumpMode=true
4. Turn encoder to change position
5. `wait_for_state`: jumpPercent changed
6. Press CENTER to confirm jump
7. `wait_for_state`: jumpMode=false, lineNum changed

**`test_save_accuracy_across_restart`**
1. Select book, pause
2. Step forward exactly 5 times (tracking each word)
3. Record lineNum and wordIdx from state
4. Restart simulator (no explicit saves -- the save should have persisted)
5. Select same book
6. Pause immediately
7. Assert lineNum and wordIdx match the recorded values

### 4.3 test_menu.py

Tests menu navigation, book selection, and hierarchical menu (Phase 2).

#### Test cases

**`test_starts_in_menu_mode`**
1. Page loads, wait for ready
2. Assert state.mode = 0 (MENU)

**`test_menu_scroll_changes_book`**
1. Record bookId from state
2. Turn encoder clockwise
3. `wait_for_state`: bookId != previous

**`test_select_book_enters_reader`**
1. Press CENTER
2. `wait_for_state`: mode=1 (READER)

**`test_return_to_menu_from_reader`**
1. Select book (CENTER), wait for reader mode
2. Pause (CENTER)
3. Press UP
4. `wait_for_state`: mode=0 (MENU)

**`test_hierarchical_menu_root_items`** (Phase 2 feature)
1. Wait for menu mode
2. Assert menuType = 'root'
3. Scroll through items, verify expected root categories appear in state (All Books, Recently Read, Authors, Series, etc.)

**`test_drill_into_authors`** (Phase 2 feature)
1. Navigate to "Authors" in root menu
2. Press CENTER
3. `wait_for_state`: menuType = 'authors'
4. Assert menuDepth = 1

**`test_back_navigation`** (Phase 2 feature)
1. Drill into Authors
2. Press UP
3. `wait_for_state`: menuType = 'root', menuDepth = 0

**`test_settings_menu_entry_exit`** (Phase 2 feature)
1. Navigate to Settings in root menu
2. Press CENTER
3. `wait_for_state`: menuType contains 'settings'
4. Press UP
5. `wait_for_state`: menuType = 'root'

### 4.4 test_persistence.py

Tests that saves, settings, and recently-read lists survive simulator restarts.

#### Test cases

**`test_save_position_persists`**
1. Select book, let it play for 2 seconds
2. Pause, record lineNum and wordIdx
3. `sim.restart()`
4. Select same book, pause
5. Assert lineNum and wordIdx match (within tolerance of +/- 1 word, since the periodic save might lag slightly)

**`test_per_book_independence`**
1. Select book A, play briefly, pause. Record position A.
2. Go to menu, select book B, play briefly, pause. Record position B.
3. `sim.restart()`
4. Select book A, pause. Assert position matches A.
5. Go to menu, select book B, pause. Assert position matches B.

**`test_recently_read_order`** (Phase 2 feature)
1. Open book A, then book B, then book C (via menu selections)
2. `sim.restart()`
3. Navigate to Recently Read menu
4. Assert order is C, B, A (most recent first)

**`test_settings_persist_across_restart`**
1. Change theme (go to display mode, cycle theme)
2. Record themeIndex
3. `sim.restart()`
4. Select a book to enter reader mode
5. Assert themeIndex matches the saved value

**`test_explicit_save_data_injection`**
1. `sim.restart(saves={"save_TestBook.txt": "10:3", "settings.txt": "skin:default\npalette:2"})`
2. Wait for ready
3. Assert the simulator loaded with the injected data (palette=2 should be reflected in themeIndex)

### 4.5 test_themes.py

Tests skin selection, palette cycling, ORP mode, and animation toggles.

#### Test cases

**`test_theme_cycle_in_display_mode`**
1. Select book, pause, go to display mode (LEFT or RIGHT)
2. Record themeIndex
3. Press RIGHT (cycle theme forward)
4. `wait_for_state`: themeIndex = (previous + 1) % num_themes

**`test_theme_cycle_backward`**
1. Go to display mode
2. Press LEFT (cycle theme backward)
3. Assert themeIndex changed

**`test_brightness_adjustment`**
1. Go to display mode
2. Record brightness from state
3. Turn encoder clockwise
4. `wait_for_state`: brightness > previous

**`test_brightness_floor`**
1. Go to display mode
2. Turn encoder counter-clockwise many times
3. Assert brightness >= 1 (never reaches 0)

**`test_brightness_ceiling`**
1. Go to display mode
2. Turn encoder clockwise many times
3. Assert brightness <= 100

**`test_return_to_reader_from_display`**
1. Go to display mode
2. Press CENTER
3. `wait_for_state`: mode=1 (READER)

**`test_skin_cycling`** (Phase 3 feature)
1. Navigate to Settings > Skin
2. Cycle through skins
3. `wait_for_state`: skinName changed

**`test_orp_mode_toggle`** (Phase 3 feature)
1. Navigate to Settings > ORP
2. Toggle
3. `wait_for_state`: orpMode changed

**`test_animation_toggle`** (Phase 5 feature)
1. Navigate to Settings > Animation
2. Toggle
3. `wait_for_state`: animationEnabled changed

---

## 5. Timing and Reliability

### 5.1 The Pyodide cold-start problem

Pyodide takes 2-5 seconds to download and initialize WebAssembly. The first test in a session is always slower. The `page` fixture handles this with a 15-second timeout on `wait_for_function("isReady()")`. Subsequent tests (in separate pages) also pay this cost.

**Mitigation strategy:** If test suite runtime becomes a problem (e.g., 20 tests x 5s = 100s just for init), we can:

1. **Share a page across tests in a module** using `scope="module"` on the page fixture, with a `sim.restart()` between tests instead of full page reload. This reuses the Pyodide instance.
2. **Preload Pyodide via service worker caching.** After the first load, the browser cache serves the WASM binary.

Start with per-test isolation (correct by default) and optimize only if slow.

### 5.2 State propagation delay

The worker's main loop runs at ~100 iterations/second (10ms setTimeout). State snapshots are sent every 50 iterations (~500ms). A button press or encoder turn is processed within one iteration (~10ms), but the state message reflecting that change may take up to 500ms to arrive.

**Implications for tests:**
- After `press_button()`, the state change is applied immediately in the worker's Python loop, but `get_state()` won't reflect it for up to 500ms.
- `wait_for_state()` polls the cached `_lastState` which only updates when a `state` message arrives.

**Solution:** Reduce the state send interval during tests. The `_async_main_loop` in worker.ts sends state every 50 iterations. We can either:

- **Option A:** Reduce to every 5 iterations (~50ms) always. The overhead is negligible -- it's a small JSON message.
- **Option B:** Send state after every button/encoder handler call, not just on a timer. This guarantees the state reflects the last input.
- **Option C:** Send state immediately whenever it changes (dirty flag).

**Decision: Option B for handler-triggered sends, plus keep the periodic timer at a reduced interval (every 10 iterations / ~100ms).** After each `handler(state, book, disp)` call in the main loop, insert `_state_tracker.send_state()`. This ensures that any button press or encoder turn results in an immediate state update.

Pseudocode for the modified main loop section:

```python
# In _async_main_loop (worker.ts Python section):

# After button handler:
if handler:
    handler(state, book, disp)
    _state_tracker.send_state()  # immediate update

# After encoder handler:
if handler:
    handler(state, book, disp)
    _state_tracker.send_state()  # immediate update
```

With this change, `wait_for_state()` will resolve within ~20ms of a button press (10ms loop tick + message propagation).

### 5.3 Default timeouts

| Operation | Default timeout | Rationale |
|---|---|---|
| Page ready (Pyodide init) | 15,000ms | Cold-start can take 5-10s |
| State after button press | 5,000ms | Should resolve in <100ms; 5s is generous safety margin |
| End of book (20 words) | 15,000ms | 20 words at 200 WPM = 6s, plus overhead |
| Console message appear | 5,000ms | Messages are near-instant |
| Restart + ready | 15,000ms | Full page reload + Pyodide reinit |

All timeouts are configurable per-call. The defaults are generous to avoid flaky failures on slow CI machines.

---

## 6. Test Book Fixtures

### 6.1 Short Story (20 words)

Filename: `Test Author - Short Story (20).txt`

```
The quick brown fox jumped
over the lazy dog sleeping
in the warm afternoon sun
and then ran quickly home
```

Four lines, 20 words total. Designed so end-of-book is reachable in ~6 seconds at 200 WPM. All ASCII, no smart quotes, no long words.

### 6.2 Five Lines (25 words)

Filename: `Test Author - Five Lines (25).txt`

```
One two three four five
six seven eight nine ten
eleven twelve thirteen fourteen fifteen
sixteen seventeen eighteen nineteen twenty
twenty-one twenty-two twenty-three twenty-four twenty-five
```

Five lines, 25 words. Useful for testing multi-book independence (a second book with different content). The `twenty-three` style words test hyphen splitting (words >17 chars).

### 6.3 Chapter Book (50 words)

Filename: `(TestSeries 1) Test Author - Chapter Book (50).txt`

```
CHAPTER 1
The first chapter has ten
words in it for testing
purposes and nothing more here

CHAPTER 2
The second chapter also has
ten words here for testing
the chapter navigation feature now

CHAPTER 3
The third chapter is the
last chapter with ten words
for testing end of book
```

Includes chapter markers (lines starting with `CHAPTER`) for Phase 2 chapter navigation tests. The series prefix `(TestSeries 1)` tests metadata parsing.

### 6.4 Loading test books

Test books need to be available to the simulator. Two approaches:

**Option A: Copy to simulator's public directory.** Test setup copies fixture books to `simulator/public/assets/books/` before starting the dev server. Simple but mutates the project.

**Option B: Inject via JavaScript before worker starts.** The test fixture uses `page.evaluate()` to write book data into the worker's virtual filesystem. This requires the test API to support injecting books before `code.py` runs.

**Decision: Option A with gitignore.** Copy test books to the simulator's book directory. Add `*Test Author*` to the simulator's `.gitignore` so they don't get committed. The fixture's `conftest.py` copies them on session setup and removes them on teardown:

```python
@pytest.fixture(scope="session", autouse=True)
def install_test_books():
    """Copy test book fixtures to the simulator's public assets directory."""
    src = Path(__file__).parent / "fixtures" / "books"
    dst = Path(__file__).parent.parent.parent / "simulator" / "public" / "assets" / "books"
    copied = []
    for book_file in src.glob("*.txt"):
        target = dst / book_file.name
        shutil.copy2(book_file, target)
        copied.append(target)
    yield
    for target in copied:
        target.unlink(missing_ok=True)
```

---

## 7. Required main.ts Changes

The test infrastructure depends on `main.ts` exposing a test API. Here is the full set of changes needed.

### 7.1 State caching

```typescript
class App {
  // New fields for test observability
  private _lastState: StateMessage | null = null;
  private _consoleLog: string[] = [];
  private _ready = false;

  // In handleWorkerMessage, add caching:
  //   case 'state':  this._lastState = msg; ...
  //   case 'console':  this._consoleLog.push(msg.message); ...
  //   case 'ready':  this._ready = true; ...
}
```

### 7.2 Public API methods

```typescript
pressButton(keyNumber: number) {
    this.sendToWorker({ type: 'button', keyNumber, pressed: true });
}

setEncoderPosition(position: number) {
    this.sendToWorker({ type: 'encoder', position });
}

getLastState(): StateMessage | null {
    return this._lastState;
}

getConsoleMessages(): string[] {
    return [...this._consoleLog];
}

isReady(): boolean {
    return this._ready;
}
```

### 7.3 Global exposure

```typescript
const app = new App();
app.start();
(window as any).__picoReaderApp = app;
```

These changes are small and non-invasive. They don't affect normal simulator operation -- they just make internal state readable from the outside.

---

## 8. Running the Tests

### 8.1 Prerequisites

```bash
# 1. Install test dependencies
pip install pytest pytest-playwright
playwright install chromium

# 2. Start the simulator dev server (in a separate terminal)
cd simulator && npm run dev

# 3. Copy test books (handled by fixture, but can be done manually)
cp tests/integration/fixtures/books/*.txt simulator/public/assets/books/
```

### 8.2 Running

```bash
# All integration tests
pytest tests/integration/ -v

# Single test file
pytest tests/integration/test_reading_flow.py -v

# Single test
pytest tests/integration/test_reading_flow.py::test_pause_resume -v

# With visible browser (for debugging)
pytest tests/integration/ -v --headed

# Slow motion (for demos)
pytest tests/integration/ -v --headed --slowmo 500
```

### 8.3 CI considerations

The tests require a running Vite dev server. In CI:

```yaml
# GitHub Actions example
- name: Start simulator
  run: |
    cd simulator && npm install && npm run dev &
    sleep 5  # Wait for Vite to start

- name: Install test deps
  run: |
    pip install pytest pytest-playwright
    playwright install chromium --with-deps

- name: Run integration tests
  run: pytest tests/integration/ -v
```

The `sleep 5` is a simple approach. A more robust approach would be to poll `http://localhost:5173` until it responds.

---

## 9. Key Design Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Interaction method | Button/encoder events only | Tests should exercise the same input path as real hardware. No shortcuts. |
| State verification | State tracker messages | Faster and more reliable than pixel sampling. State is structured data, not visual artifacts. |
| Pixel sampling | Reserved for skin color verification only | Only needed to confirm that theme colors actually reached the canvas. Keep to 1-2 tests max. |
| Test isolation | Fresh page per test | Guarantees clean state. Pyodide reinit cost is acceptable for correctness. |
| State propagation | Send immediately after handler calls | Eliminates up to 500ms polling delay. Tests resolve in <100ms after action. |
| Test books | Tiny fixture files (20-50 words) | Fast, deterministic. End-of-book reachable in seconds, not minutes. |
| Simulator not auto-started | Manual `npm run dev` required | Avoids complexity of process management in tests. CI scripts handle startup. |
| Settings save interception | Monkey-patch `save_settings()` | Matches existing pattern for `save_place`/`save_backup`. Explicit and simple. |
| JS predicates in wait_for_state | Browser-side evaluation | Eliminates per-poll round-trip overhead. Native 60fps checking. |

---

## 10. What Phase 6 Does NOT Include

- **Visual regression testing** (screenshot comparisons, pixel-perfect layout assertions). Canvas rendering is tested manually and by the renderer unit tests (if any).
- **Performance benchmarks** (WPM timing accuracy, frame rate). These are better measured with browser DevTools, not Playwright.
- **Epub converter tests** (Phase 4). The converter is a standalone CLI tool with its own unit tests.
- **Firmware unit tests** (Phase 1). Unit tests for `parse_book_filename`, `clean_word`, `BookReader`, etc. are in `tests/unit/`, established in Phase 1.
- **Mobile/touch testing.** The simulator's touch events work via the same postMessage path as clicks. If the JS UI works, the Python code doesn't care how the event arrived.
- **Multi-browser testing.** Chromium only. The simulator's rendering uses standard Canvas 2D and Web Workers -- there's no browser-specific behavior to catch.

---

## Task Order

1. Add test API to `main.ts` (state caching, public methods, global exposure)
2. Add immediate `_state_tracker.send_state()` calls after handler execution in the worker's `_async_main_loop`
3. Reduce periodic state send interval from 50 iterations to 10
4. Create `tests/integration/` directory structure and fixture books
5. Write `conftest.py` with fixtures and `SimulatorHelper`
6. Write `test_reading_flow.py` (most fundamental -- validates the entire pipeline)
7. Write `test_themes.py` (exercises display mode, simple state transitions)
8. Write `test_navigation.py` (word stepping first, chapter features when Phase 2 lands)
9. Write `test_menu.py` (basic menu first, hierarchical when Phase 2 lands)
10. Write `test_persistence.py` (depends on save system working end-to-end)
11. Run full suite, fix timing issues, adjust timeouts
12. Add pytest marker configuration
13. Document CI setup

Tests for Phase 2-5 features (chapter navigation, jump mode, hierarchical menus, skins, ORP, animations) should be written as stubs (`@pytest.mark.skip(reason="Phase N not yet implemented")`) and unskipped as each phase lands.
