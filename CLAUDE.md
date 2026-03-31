# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

picoReader is a Rapid Serial Visual Presentation (RSVP) speed-reading eReader built on a Raspberry Pi Pico running CircuitPython 8.0.5. It displays one word at a time from plain text books stored on an SD card, using a 160x128 ST7735R LCD, a rotary encoder clickwheel (Adafruit #6310), and a 5-button keypad.

## Development & Deployment

There is no build system. This is a CircuitPython project deployed by copying files directly to the Pico's USB mass-storage filesystem. The Pico runs `boot.py` first (remounts filesystem read-only), then `code.py` (the entire application).

To deploy changes: copy modified files to the Pico's mounted drive. The device auto-reloads on file change.

Libraries in `lib/` are precompiled Adafruit `.mpy` bytecode files -- do not edit them directly. Update them via `circup` or the Adafruit CircuitPython bundle.

To check for syntax errors: `python3 -c "import py_compile; py_compile.compile('code.py', doraise=True)"`

## Architecture

### Single-file application: `code.py`

The `eReader` class holds all hardware handles, application state, and class constants (`DEFAULT_WPM`, `BATCH_SIZE`, `SAVE_INTERVAL`, `THEMES`, etc.). Three async tasks run concurrently via `asyncio.gather()`:

- **`reader()`** -- Core RSVP engine. Reads `BATCH_SIZE` lines at a time from the book file using `islice()`. Displays words one at a time, saves position every `SAVE_INTERVAL` lines, and updates the progress bar. Snapshots `buttons[0]` as `playing` at the start of each batch to prevent mid-iteration state changes.
- **`monitor_buttons()`** -- Handles the 5-button keypad via `keypad.Keys`. Mode transitions go through `set_mode()` which handles exit/entry logic.
- **`monitor_rotary()`** -- Handles the clickwheel encoder. Paused-mode scroll operations are protected by `self.nav_lock` (`asyncio.Lock`) to prevent concurrent modification of `places` and `word_index`.

### Display architecture

The reader display uses a **persistent `displayio.Group`** (`self.reader_group`) built once in `_build_reader_group()`. Theme changes update existing widget properties (palette colors, label colors, rect fills) via `update_reader_theme()` instead of rebuilding. Switch to reader display with `show_reader()`.

The menu display still rebuilds its `displayio.Group` on each call to `menu_screen()`, but uses a `menu_dirty` flag to skip redundant redraws.

### Three operating modes

| Mode | Purpose | CENTER | UP | LEFT | RIGHT | Encoder |
|------|---------|--------|-----|------|-------|---------|
| `reader` | RSVP reading | Play/pause | Go to menu (paused) | Go to display mode (paused) | Go to display mode (paused) | Playing: adjust WPM (+/- 2). Paused: step word-by-word |
| `menu` | Book selection carousel | Select book & start reading | -- | -- | -- | Scroll through books |
| `display` | Theme/brightness | Return to reader + toggle play | Go to menu | Previous theme | Next theme | Adjust backlight (+/- 2%) |

### Book file format

Books are plain `.txt` files stored on the SD card at `/sd/books/`. Filenames encode metadata:
```
(Series) Author - Title (wordcount).txt
```
Parsed at startup by `parse_book_filename()` using `split(' - ', 1)` for the author/title boundary and `rsplit('(', 1)` for the wordcount suffix. Metadata cached in `self.book_metadata`.

### Save system

Reading positions are stored in `saves/save_<filename>` as a single integer (line number). A backup `saves/save_prev_<filename>` is written when reading begins. The filesystem must be remounted writable for saves to work -- `boot.py` handles this with `storage.remount("/", False)`.

## Hardware Pin Mapping

```
SPI (shared by display and SD card):
  GP2=CLK, GP3=MOSI, GP4=MISO

Display (ST7735R):  GP17=DC, GP18=RST, GP19=CS
SD Card:            GP15=CS
Encoder:            GP14=A, GP13=B
Backlight PWM:      GP16 (5kHz)
Buttons (5-way keypad):
  GP11=btn0 CENTER, GP9=btn1 UP, GP10=btn2 LEFT, GP8=btn3 RIGHT, GP6=btn4 DOWN
COM pins:           GP12=COMA, GP7=COMB (set to output, unused)
```

## Important Details

- **Display colors are BGR format**, not RGB. See https://wamingo.net/rgbbgr/ for conversion. Five themes are defined in `eReader.THEMES` as `[bg, text, wpm, highlight]` tuples.
- **Display is 160x128 with rotation=270** and `auto_refresh=False` -- you must call `self.display.refresh()` explicitly after changes.
- **Reader group indices**: 0=background, 1=text_area, 2-5=guide rects, 6=progress_rect, 7=wpm_text. Progress bar is replaced by index (`reader_group[6] = Rect(...)`) since Rect width isn't settable after creation.
- **5-way keypad buttons**: CENTER (btn0) = select/play/pause, UP (btn1) = back to menu, LEFT (btn2) = previous theme, RIGHT (btn3) = next theme, DOWN (btn4) = unused. Named constants `BTN_CENTER`, `BTN_UP`, `BTN_LEFT`, `BTN_RIGHT`, `BTN_DOWN` are defined in `code.py`.
- **`clean_word()`** replaces smart quotes (U+201C/201D/2018/2019) with ASCII equivalents before display. Words longer than 17 characters are split on hyphens.
- **Menu sub-types** (`authors`, `series`, `author_books`, `author_series`) are partially stubbed -- the `menu_type` routing exists but data structures aren't populated.
- **Fonts**: `Toronto_14.pcf` for reading text, `Toronto_9.pcf` for UI. Additional font files exist in `fonts/` but aren't currently selectable at runtime.
- **CircuitPython upgrade path**: Currently on 8.0.5. Upgrading to 9.x requires replacing all `.mpy` libs and changing `display.show()` to `display.root_group =`.
