# Phase 1C: Test Infrastructure + Unit Tests

> **Dependency:** Phase 1B (save system + settings must be in place to test).

**Goal:** Set up pytest with CircuitPython mock modules so `pico_reader` can be imported on desktop Python, then write unit tests for all Phase 1 modules.

---

## 1. Directory structure

```
tests/
  __init__.py
  conftest.py               # Mock modules + shared fixtures
  pytest.ini                # Config
  unit/
    __init__.py
    test_utils.py            # parse_book_filename, clean_word
    test_state.py            # AppState
    test_book_reader.py      # BookReader with temp files
    test_settings.py         # Settings load/save
```

---

## 2. pytest.ini

```ini
[pytest]
testpaths = tests
markers =
    unit: Unit tests (no browser)
    integration: Integration tests (requires simulator)
```

---

## 3. Mock strategy (the hard part)

CircuitPython modules don't exist on desktop Python. We need stubs injected into `sys.modules` BEFORE any `pico_reader` import.

### What needs mocking

`pico_reader` modules import these CircuitPython packages:
- `board` — pin constants (GP2, GP3, etc.)
- `digitalio` — DigitalInOut
- `busio` — SPI
- `sdcardio` — SDCard
- `storage` — VfsFat, mount
- `displayio` — Group, Bitmap, Palette, TileGrid, FourWire, release_displays
- `rotaryio` — IncrementalEncoder
- `keypad` — Keys
- `pwmio` — PWMOut
- `adafruit_st7735r` — ST7735R
- `adafruit_display_text` / `adafruit_display_text.label` — Label
- `adafruit_bitmap_font` / `adafruit_bitmap_font.bitmap_font` — load_font
- `adafruit_display_shapes` / `adafruit_display_shapes.rect` — Rect

### Approach: conftest.py auto-use fixture

Use a session-scoped auto-use fixture that creates `MagicMock` or simple stub objects and inserts them into `sys.modules`. This runs before any test imports `pico_reader`.

```python
# tests/conftest.py
import sys
from types import ModuleType
from unittest.mock import MagicMock

@pytest.fixture(autouse=True, scope='session')
def mock_circuitpython():
    """Inject CircuitPython module stubs so pico_reader can be imported."""
    stubs = {}

    # board — needs GP* attributes
    board = ModuleType('board')
    for pin_num in range(28):
        setattr(board, 'GP{}'.format(pin_num), 'GP{}'.format(pin_num))
    stubs['board'] = board

    # Simple mock modules
    for mod_name in ['digitalio', 'busio', 'sdcardio', 'storage',
                     'rotaryio', 'keypad', 'pwmio']:
        stubs[mod_name] = MagicMock()

    # displayio — needs Group, Bitmap, Palette, TileGrid, FourWire
    displayio = MagicMock()
    displayio.Group = MagicMock
    displayio.Bitmap = MagicMock
    displayio.Palette = MagicMock
    displayio.TileGrid = MagicMock
    displayio.FourWire = MagicMock
    stubs['displayio'] = displayio

    # adafruit packages
    stubs['adafruit_st7735r'] = MagicMock()
    stubs['adafruit_display_text'] = MagicMock()
    stubs['adafruit_display_text.label'] = MagicMock()
    stubs['adafruit_bitmap_font'] = MagicMock()
    stubs['adafruit_bitmap_font.bitmap_font'] = MagicMock()
    stubs['adafruit_display_shapes'] = MagicMock()
    stubs['adafruit_display_shapes.rect'] = MagicMock()

    for name, mod in stubs.items():
        sys.modules[name] = mod

    yield

    # Cleanup
    for name in stubs:
        sys.modules.pop(name, None)
```

### What this enables

After mocks are in place, tests can do:
```python
from pico_reader.utils import parse_book_filename, clean_word
from pico_reader.state import AppState
from pico_reader.book_reader import BookReader
from pico_reader.settings import load_settings, save_settings, set_setting
```

---

## 4. Test fixtures

```python
@pytest.fixture
def tmp_book_dir(tmp_path):
    """Create temp directory with sample book files."""
    books_dir = tmp_path / "sd" / "books"
    books_dir.mkdir(parents=True)

    book1 = "(Earthsea 1) Ursula K Le Guin - A Wizard Of Earthsea (1835).txt"
    (books_dir / book1).write_text("The island of Gont\na single mountain\nthat lifts\n")

    book2 = "Pierce Brown - Red Rising (5000).txt"
    (books_dir / book2).write_text("I would have\nlived in peace\nbut my enemies\nbrought me war\n")

    return tmp_path

@pytest.fixture
def tmp_save_dir(tmp_path):
    """Create empty saves directory."""
    saves = tmp_path / "saves"
    saves.mkdir()
    return saves
```

For `BookReader` tests, we need to monkeypatch the file paths since BookReader uses hardcoded `/sd/books/` and `saves/` paths. Options:
- Monkeypatch `open()` to redirect paths
- Or pass a base path to BookReader (minor constructor change)
- Simplest: use `os.chdir(tmp_path)` in tests so relative paths resolve to temp dir

---

## 5. Unit tests

### test_utils.py

| Test | Input | Expected |
|------|-------|----------|
| Series + author + title + wordcount | `"(Earthsea 1) Ursula K Le Guin - A Wizard Of Earthsea (1835).txt"` | `("A Wizard Of Earthsea", "Ursula K Le Guin", "Earthsea 1", 1835)` |
| No series | `"Pierce Brown - Red Rising (5000).txt"` | `("Red Rising", "Pierce Brown", "", 5000)` |
| Missing wordcount | `"Author - Title.txt"` | `("Title", "Author", "", 10000)` |
| Malformed | `"garbage.txt"` | `("garbage", "", "", 10000)` |
| Smart quotes replaced | `"\u201cHello\u201d"` | `'"Hello"'` |
| Normal text unchanged | `"hello"` | `"hello"` |
| Empty string | `""` | `""` |

### test_state.py

| Test | Action | Expected |
|------|--------|----------|
| Default values | `AppState()` | `mode=0, wpm=200, speed=0.3, brightness=50` |
| set_wpm | `set_wpm(300)` | `wpm=300, speed=0.2` |
| WPM floor | `set_wpm(5)` | `wpm=10` |
| Settings applied | `AppState(settings={'palette': '2', 'brightness': '75'})` | `theme_index=2, brightness=75` |

### test_book_reader.py

Needs temp files. Use `os.chdir(tmp_path)` + create `sd/books/` and `saves/` inside.

| Test | Action | Expected |
|------|--------|----------|
| step_forward reads words | Read from 3-word line | Returns word1, word2, word3 in order |
| step_forward crosses lines | Read past line boundary | Continues to next line |
| step_forward at EOF | Read past last word | Returns None |
| step_backward | After stepping forward 3 times | Returns previous word |
| step_backward at start | At line 0, word 0 | Returns None |
| save_place format | After stepping to line 5, word 3 | File contains `"5:3"` |
| load_place new format | File contains `"5:3"` | `line_num=5, word_idx=3` |
| load_place old format | File contains `"5"` | `line_num=5, word_idx=0` |
| load_place missing file | No save file | `line_num=0, word_idx=0` |
| select_book | Switch to book 1 | `book` updated, position loaded |

### test_settings.py

| Test | Action | Expected |
|------|--------|----------|
| No file | `load_settings()` | Returns DEFAULTS dict |
| Partial file | File has `skin:terminal` only | Returns defaults + `skin:terminal` |
| Full round-trip | Save then load | All values preserved |
| set_setting | `set_setting(s, 'brightness', '75')` | Dict updated, file written |
| Unknown keys ignored | File has `bogus:value` | Key not in returned dict |

---

## Task order

1. Create `tests/` directory, `__init__.py`, `pytest.ini`
2. Create `tests/conftest.py` with CircuitPython mock fixture + test fixtures
3. Create `tests/unit/__init__.py`
4. Write `tests/unit/test_utils.py`
5. Write `tests/unit/test_state.py`
6. Write `tests/unit/test_book_reader.py`
7. Write `tests/unit/test_settings.py`
8. Run `pytest tests/unit/ -v`, fix any issues
9. Commit
