# Phase 1A: Module Split (Mechanical)

> **Dependency:** None. This is the very first step.

**Goal:** Split `firmware/code.py` (662 lines) into focused modules under `firmware/pico_reader/`. Purely mechanical — no logic changes whatsoever. Every function and class is copy-pasted as-is with only import statements adjusted.

---

## Files to create

```
firmware/
  code.py                    # Rewritten as thin entry point
  pico_reader/
    __init__.py              # Re-exports everything for backward compat
    constants.py             # All constants, pin mappings, theme data
    hardware.py              # init_hardware()
    state.py                 # AppState class
    book_reader.py           # BookReader class
    display.py               # Display class
    input_handlers.py        # All handler functions + dispatch tables
    utils.py                 # parse_book_filename(), clean_word()
    main.py                  # main_loop() + main()
```

---

## Source mapping

Each section in `code.py` is clearly marked with `# =====` banners. Cut each section verbatim:

| Source (code.py lines) | Target file | What moves |
|---|---|---|
| 1-16: imports | Distributed — each module imports what it needs |
| 17-66: Constants block | `constants.py` | `DEFAULT_WPM`, `DEFAULT_BRIGHTNESS`, `PWM_FREQ`, `SAVE_INTERVAL`, `THEMES`, display geometry, pin assignments, button constants |
| 73-96: `init_hardware()` | `hardware.py` | The function verbatim |
| 103-128: `parse_book_filename()` | `utils.py` | The function verbatim |
| 131-132: `clean_word()` | `utils.py` | The function verbatim |
| 139-156: `AppState` class | `state.py` | The class verbatim |
| 162-255: `BookReader` class | `book_reader.py` | The class verbatim |
| 261-424: `Display` class | `display.py` | The class verbatim |
| 430-549: handlers + dispatch tables | `input_handlers.py` | All handler functions + `BUTTON_HANDLERS` + `ENCODER_HANDLERS` |
| 556-662: `main_loop()` + `main()` | `main.py` | Both functions verbatim |

---

## Import wiring

Each module imports only what it needs from siblings:

**`constants.py`** — no local imports, only stdlib:
```python
import board
```

**`hardware.py`**:
```python
import digitalio, busio, sdcardio, storage, displayio, pwmio, rotaryio
from adafruit_st7735r import ST7735R
from .constants import (PIN_SPI_CLK, PIN_SPI_MOSI, PIN_SPI_MISO,
    PIN_DISPLAY_DC, PIN_DISPLAY_RST, PIN_DISPLAY_CS, PIN_SD_CS,
    PIN_ENC_A, PIN_ENC_B, PIN_BACKLIGHT, PIN_COM,
    DISPLAY_WIDTH, DISPLAY_HEIGHT, DEFAULT_BRIGHTNESS, PWM_FREQ)
```

**`state.py`**:
```python
from .constants import DEFAULT_WPM, DEFAULT_BRIGHTNESS
```

**`book_reader.py`**:
```python
# No local imports — BookReader only uses builtins (open, int, str)
```

**`utils.py`**:
```python
# No local imports — pure functions
```

**`display.py`**:
```python
import displayio
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font
from adafruit_display_shapes.rect import Rect
from .constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT, WORD_CENTER, WPM_POS,
    GUIDE_RECTS, THEMES, DEFAULT_WPM, MENU_TITLE_POS, MENU_SLOTS,
    MENU_SELECT_COLORS, MENU_OTHER_COLORS, MENU_BG)
```

**`input_handlers.py`**:
```python
from .state import AppState
from .constants import (THEMES, BTN_CENTER, BTN_UP, BTN_LEFT, BTN_RIGHT, BTN_DOWN)
from .utils import clean_word
```

**`main.py`**:
```python
import time, os, keypad
from adafruit_bitmap_font import bitmap_font
from .constants import PIN_BUTTONS, SAVE_INTERVAL
from .hardware import init_hardware
from .state import AppState
from .book_reader import BookReader
from .display import Display
from .input_handlers import BUTTON_HANDLERS, ENCODER_HANDLERS
from .utils import parse_book_filename, clean_word
```

---

## `__init__.py` — re-export everything

This is critical for simulator compatibility. `worker.ts` does `import code` then accesses `code.AppState`, `code.BUTTON_HANDLERS`, `code.time`, etc. Since `code.py` does `from pico_reader import *`, the `__init__.py` must re-export everything the worker accesses:

```python
from .constants import *
from .hardware import init_hardware
from .state import AppState
from .book_reader import BookReader
from .display import Display
from .input_handlers import (BUTTON_HANDLERS, ENCODER_HANDLERS,
    toggle_play, goto_menu, goto_display, select_and_play,
    goto_reader_toggle, cycle_theme_fwd, cycle_theme_back,
    wpm_up_or_step_fwd, wpm_down_or_step_back,
    menu_next, menu_prev, brightness_up, brightness_down)
from .utils import parse_book_filename, clean_word
from .main import main, main_loop

# Re-export stdlib modules that worker.ts accesses as code.X
import time
import os
import keypad
from adafruit_bitmap_font import bitmap_font
```

---

## `code.py` — thin entry point

```python
from pico_reader import *

main()
```

That's it. Two lines.

---

## Verification

After splitting, verify each file compiles:

```bash
for f in firmware/pico_reader/*.py; do
    python3 -c "import py_compile; py_compile.compile('$f', doraise=True)"
done
python3 -c "import py_compile; py_compile.compile('firmware/code.py', doraise=True)"
```

Note: These won't pass full import checks (missing CircuitPython modules) but will catch syntax errors.

---

## What this does NOT change

- No logic changes — every function body is identical
- No save format changes (that's Phase 1B)
- No new features
- No tests yet (that's Phase 1C)
- No simulator changes yet (that's Phase 1D)

---

## Task order

1. Create `firmware/pico_reader/` directory
2. Create `constants.py` (copy constants block, add `import board`)
3. Create `utils.py` (copy `parse_book_filename` + `clean_word`)
4. Create `state.py` (copy `AppState`, add import from constants)
5. Create `book_reader.py` (copy `BookReader`)
6. Create `display.py` (copy `Display`, add imports from constants)
7. Create `input_handlers.py` (copy all handlers + dispatch tables, add imports)
8. Create `hardware.py` (copy `init_hardware`, add imports)
9. Create `main.py` (copy `main_loop` + `main`, add imports)
10. Create `__init__.py` with all re-exports
11. Rewrite `code.py` as thin entry point
12. Syntax-check all files
13. Commit
