# picoReader v3 Design Spec

## Context

picoReader is a working RSVP eReader on Raspberry Pi Pico (CircuitPython 8.0.5, 160x128 ST7735R LCD, rotary encoder, 5-button keypad). The core reading experience is solid but has pain points: imprecise saves, flat menu with no hierarchy, no fast navigation, manual epub conversion, limited UI variety, and no automated testing. This spec designs solutions for all of these plus new features (smart pacing, reading analytics, ORP highlighting, UI skins, animations).

The firmware was recently refactored (commit 86e1c10) into three classes (AppState, BookReader, Display) with dispatch-table input handling. This spec extends that architecture into a multi-module design.

---

## 1. Module Architecture

Split firmware into focused modules stored on internal flash, compiled to `.mpy` via `mpy-cross` for deployment.

```
firmware/
  code.py                   # Entry point: imports and calls main()
  pico_reader/
    __init__.py
    state.py                # AppState + smart pacing delay calculation
    book_reader.py          # BookReader: file I/O, caching, position, chapters
    display.py              # Display base: delegates to active skin
    menu.py                 # Hierarchical iPod-style menu system
    input_handlers.py       # Button/encoder dispatch tables + handlers
    themes.py               # Theme registry: palettes + ORP + animation configs
    analytics.py            # Per-book and per-session reading stats
    skins/
      __init__.py
      default.py            # Current clean RSVP display
      terminal.py           # Retro CRT green/amber-on-black
      rpg.py                # Pixel RPG dialogue box
      typewriter.py         # Vintage sepia typewriter
    animations/
      __init__.py
      walker.py             # Walking character sprite on progress bar
      particles.py          # Ambient drifting particles in margins
      page_turn.py          # Page counter with turn indicator

tools/
  epub2pico/                # Standalone CLI tool (pipx-installable)
    pyproject.toml
    epub2pico/
      __init__.py
      cli.py                # Click-based CLI entry point
      converter.py          # Epub parsing + text extraction
      stripper.py           # Junk content detection + removal
      formatter.py          # picoReader filename generation

tests/
  unit/                     # Pure pytest, no browser needed
  integration/              # Playwright-driven simulator tests
  conftest.py               # Shared fixtures
  pytest.ini
```

**Deployment workflow:**
1. Develop in `.py` files as normal
2. Run `mpy-cross` to compile `pico_reader/` modules to `.mpy`
3. Copy `code.py` + `pico_reader/*.mpy` to Pico internal flash
4. Books, saves, fonts remain where they are

**RAM budget:** Current `code.py` is ~23KB. Split modules total ~30-35KB `.py`, which compiles to ~15-20KB `.mpy`. Import overhead well within the ~150-190KB free RAM on Pico with CP 8.0.5.

---

## 2. Save System

### Exact-position saves

**Format change:** Save files store `line_num:word_idx` instead of just `line_num`.

- File: `saves/save_<filename>` contains e.g. `1423:7`
- Backup: `saves/save_prev_<filename>` (written when reading starts)
- **Backward compatible:** If no `:` found when loading, defaults to `word_idx=0`

**Save triggers (expanded):**
- Every pause/stop (immediate)
- Every mode transition (menu, settings)
- Every `SAVE_INTERVAL` lines during playback (crash protection)
- On encoder step during word-by-word navigation

### Recently Read

- File: `saves/recent_order.txt` -- ordered list of filenames, one per line, most recent first
- **Capped at 10 entries** -- truncated on write
- Updated when a book is opened: remove if present, insert at position 0, write back
- No RTC needed -- order is implicit

---

## 3. Hierarchical Menu System

### Structure

```
picoReader (root)
├── All Books           → A-Z by title
├── Recently Read       → From recent_order.txt (up to 10)
├── Authors             → Unique authors, sorted
│   └── <Author>        → That author's books
├── Series              → Unique series names, sorted
│   └── <Series>        → Books in series, sorted by number
├── Genres              → Unique genres, sorted
│   └── <Genre>         → Books in that genre
└── Settings
    ├── Skin            → Cycle: Default, Terminal, RPG, Typewriter
    ├── Color           → Cycle through active skin's palettes
    ├── ORP Mode        → Cycle: Off, Color Highlight, Bold-Fade
    ├── Animation       → Cycle: Off, Walker, Particles, Page Turn
    ├── Font            → Cycle through available PCF fonts
    ├── Smart Pacing    → On / Off
    └── Brightness      → Encoder adjusts, display shows %
```

### Navigation

- **Encoder:** Scroll current list (wraps)
- **CENTER:** Select / drill into item / start reading (at book level)
- **UP:** Back one level (or to root)

### Display

Same 3-slot carousel layout. Title bar shows breadcrumb path (e.g., "Authors > Pratchett"). Each slot shows either a category name or book metadata depending on depth.

### Genre in filenames

Extended format: `(Series) [Genre] Author - Title (wordcount).txt`

- Example: `(Earthsea 1) [Fantasy] Ursula K Le Guin - A Wizard Of Earthsea (1835).txt`
- Genre is optional -- missing `[Genre]` maps to "Uncategorized"
- `parse_book_filename()` updated to extract `[Genre]` token between `)` and author name

---

## 4. Reader Controls

Settings moved to menu hierarchy. Reader buttons reorganized:

| Input | Playing | Paused |
|-------|---------|--------|
| CENTER | Pause | Play |
| UP | -- | Go to menu |
| DOWN | -- | Enter jump mode |
| LEFT | -- | Previous chapter |
| RIGHT | -- | Next chapter |
| Encoder turn | WPM +/- 2 | Step word-by-word |

### Jump mode (DOWN when paused)

- Display shows: `Jump: 35%`
- Encoder scrolls by 5% increments
- CENTER: confirm jump, return to paused reader
- UP: cancel, return to paused reader
- Calculates target line from `total_lines * percentage`

### Chapter navigation (LEFT/RIGHT when paused)

- Jumps to start of previous/next `---CHAPTER:` marker
- Briefly flashes chapter title on display before showing first word
- No-op if book has no chapter markers

### Chapter markers in text files

Format: `---CHAPTER: Chapter Title Here---` on its own line.

- Scanned at book load time to build chapter index: `[(line_num, title), ...]`
- Stored in memory per-book (rebuilt on book switch)
- Epub converter inserts these automatically

---

## 5. UI Skins

### Skin vs Palette separation

**Skins** control layout and structure (guide marks, dialogue box, terminal aesthetic). **Palettes** control colors within that skin. Each skin defines its own set of palettes. In Settings, Skin and Color are cycled independently.

### Skin interface

Each skin class implements:

```python
class Skin:
    PALETTES = [...]  # List of palette dicts for this skin
    def build_group(self, display) -> displayio.Group
    def show_word(self, word, orp_mode=None)
    def show_wpm(self, wpm)
    def update_progress(self, pct)
    def apply_palette(self, palette_index)
```

Display class delegates to the active skin. Skin change triggers `build_group()` once, then uses update methods. Palette change calls `apply_palette()` without rebuilding.

### Default skin

Current clean RSVP look. Guide marks, centered word, bottom progress bar.

**Palettes (existing 5 themes preserved):**
- Dark: black bg, light text, gray WPM, gray highlight
- Light: white bg, dark text, gray WPM, gray highlight
- Gray: mid-gray bg, dark text, dark WPM, dark highlight
- Crimson: dark red bg, light text, gray WPM, cyan highlight
- Muted Dark: black bg, gray text, gray WPM, gray highlight

### Terminal skin

**Palettes:** Green phosphor, Amber phosphor, Blue phosphor

- Green-on-black (#33ff33 on #000000) or amber variant (#ffb000 on #000000)
- ASCII progress bar: `[=====>    ] 38%`
- Path header: `C:\BOOKS\TITLE>`
- Blinking cursor `_` after displayed word only when paused (like a terminal waiting for input). Hidden during playback.
- Menu styled as DOS file listing

### RPG skin

**Palettes:** Gold/Crimson, Ice/Blue, Forest/Green

- Dark blue background (#1a1a2e) with gold border (#e6c200) dialogue box
- Word appears as "spoken text" in the dialogue box
- HP-bar style progress: `PROG [████░░░░] 38%` with crimson fill
- Menu styled as inventory screen

### Typewriter skin

**Palettes:** Cream/Brown (classic), Aged/Yellowed, Night/Sepia

- Cream/sepia background (#f4ecd8)
- Dark brown ink text (#3d2b1f)
- Slight positional offset for analog feel
- Simple underline progress bar
- Menu styled as library card catalog

---

## 6. ORP (Optimal Recognition Point)

Two modes, toggleable in Settings. Works with any skin.

### ORP position calculation

```python
orp_index = min(len(word) - 1, max(1, (len(word) + 1) // 3 - 1))
```

Roughly 1/3 into the word, clamped to valid range.

### Color Highlight mode

Three labels positioned relative to a fixed ORP anchor point on screen:
- **Prefix** (before ORP letter): text color, right-anchored to ORP point
- **ORP letter**: highlight color, centered at fixed screen X
- **Suffix** (after ORP letter): text color, left-anchored from ORP point

Pixel widths calculated from font glyph metrics to prevent overlap. The ORP letter stays at a fixed screen X position (e.g., X=80, the horizontal center) regardless of word length. Prefix extends leftward from that point, suffix extends rightward. This is the Spritz-style fixed focus point -- your eye never moves.

### Bold-Fade mode

Two labels:
- **Bold part** (~first 40% of characters): full-brightness text color
- **Fade part** (remaining ~60%): dimmed version of text color

Same fixed-anchor positioning as Color mode.

---

## 7. Animations

Optional overlays that update between words. Each implements `tick(state, display)`.

### Walker

- 5x5 pixel sprite at bottom of screen, positioned at `x = (words_read / book_wordcount) * screen_width`
- Sprite X tracks reading progress: walks from left edge (0%) to right edge (100%) of the book
- Speed-dependent appearance (animation frames cycle, position is progress-based):
  - <=150 WPM: walking (2-frame alternation)
  - 150-300 WPM: jogging (2 frames)
  - 300+ WPM: running (2 frames)
- Sprite stored as small Bitmap (6 frames total, ~150 bytes)
- Single TileGrid moved each tick

### Particles

- 3-5 single-pixel TileGrids in the margins (outside word area)
- Drift downward 1px per tick
- Reset to random X at top when reaching bottom
- Minimal CPU: just y-position updates on existing TileGrids

### Page Turn

- Small "pg XX" label in corner
- Page counter: `words_read // 250`
- On page increment: brief highlight flash (1 frame) as visual "turn" indicator
- More tangible progress feel than percentage

---

## 8. Smart Pacing

Dynamic word display duration based on word complexity. Base speed from user's WPM setting.

### Word delay multipliers

| Condition | Multiplier | Stacks |
|-----------|-----------|--------|
| Long word (>8 chars) | 1.3x | Yes |
| Comma/semicolon/colon ending | 1.5x | Yes |
| Sentence end (. ! ?) | 1.8x | Yes |
| Paragraph start (after empty line) | 1.4x | Yes |
| Short common word (<=3 chars) | 0.8x | Yes |

Multipliers are multiplicative. Example: long word at sentence end = 1.3 * 1.8 = 2.34x base delay.

### Ramp-up

When playback starts (play pressed), effective WPM begins at 50% of set WPM and linearly ramps to 100% over 10 seconds using `time.monotonic()`. Resets on each pause/play cycle.

### Implementation

`calculate_word_delay(word, base_speed, is_paragraph_start, ramp_factor)` in `state.py`. Returns adjusted delay in seconds. Called in main loop instead of flat `state.speed`.

### Toggle

On/Off in Settings menu. When off, flat WPM with no ramp-up (current behavior).

---

## 9. Reading Analytics

### Per-book stats (persisted)

File: `saves/stats_<filename>` -- simple key:value format.

```
words_read:12450
sessions:7
```

- `words_read`: total words read across all sessions (incremented during reading)
- `sessions`: incremented each time reading starts

### Per-session stats (in-memory, reset on power cycle)

- Words read this session
- Average WPM this session (rolling average)
- Time reading this session (via `time.monotonic()` deltas)

### Derived values (calculated on demand)

- Words remaining: `book_wordcount - words_read`
- Estimated time to finish: `words_remaining / current_wpm` (displayed as "~X min")
- Completion percentage: `words_read / book_wordcount * 100`

### Display

Accessible from the menu when a book is selected (before starting to read) or from a "Book Stats" option. Shows per-book stats + session stats on a simple info screen.

---

## 10. Epub Converter (epub2pico)

### Package structure

```
tools/epub2pico/
  pyproject.toml          # Package metadata, dependencies, entry point
  epub2pico/
    __init__.py
    cli.py                # Click CLI: epub2pico [--auto|--review] <path>
    converter.py          # Epub → ordered chapter text extraction
    stripper.py           # Content stripping heuristics
    formatter.py          # Filename generation from metadata
```

### Installation

```bash
pipx install ./tools/epub2pico    # Global CLI, isolated venv, no activation needed
# OR
pip install -e ./tools/epub2pico  # Editable install in current venv
```

After install: `epub2pico` available as CLI command anywhere.

### Auto mode (default)

```bash
epub2pico book.epub                    # Single file
epub2pico --auto books_dir/            # Batch (all .epub files)
epub2pico book.epub --output-dir /sd/books/  # Custom output
```

Processing pipeline:
1. Parse epub with `ebooklib`
2. Extract chapters in spine order
3. Convert HTML to plain text with `BeautifulSoup`
4. Insert `---CHAPTER: <title>---` markers from TOC
5. Strip junk content (see heuristics below)
6. Generate filename from epub metadata
7. Count words, append to filename
8. Write output .txt file

### Review mode

```bash
epub2pico --review book.epub           # Interactive single file
epub2pico --review books_dir/          # Interactive batch (one at a time)
```

Before writing, shows:
- Colored diff of stripped content (red=removed, green=kept)
- Generated filename
- Chapter markers found
- Prompt: Accept / Edit filename / Re-run with adjustments / Skip

### Stripping heuristics

| Pattern | Detection |
|---------|-----------|
| Copyright pages | "Copyright", "All rights reserved", "ISBN", "Published by" |
| Page numbers | Standalone numeric lines, `- \d+ -` patterns |
| Dividers | Lines of only `---`, `***`, `===`, `* * *`, etc. |
| TOC text | Matches epub TOC section content |
| Front/back matter | Epub content typed as `frontmatter`/`backmatter` |
| Headers/footers | Repeated short lines at chapter boundaries |

### Metadata extraction

- **Author**: epub `dc:creator` metadata
- **Title**: epub `dc:title` metadata
- **Series**: epub `calibre:series` + `calibre:series_index` (Calibre adds these)
- **Genre**: epub `dc:subject` metadata (first entry)
- **Word count**: calculated from extracted text

---

## 11. Font Switcher

Settings menu entry cycles through available PCF fonts in `fonts/`.

Available fonts:
- Toronto_14.pcf (current default)
- Aleo-Regular-14.pcf
- Bitter-Regular-14.pcf
- BreeSerif-Regular-14.pcf
- CreteRound-Regular-14.pcf
- IBMPlexSerif-SemiBold-14.pcf
- Merriweather-Regular-14.pcf
- SpecialElite-Regular-14.pcf

**Persistence:** Selected font name stored in `saves/settings.txt` (general settings file). Applied on next book open or skin change (not mid-word -- would be jarring).

**Settings file format** (`saves/settings.txt`):
```
skin:default
palette:0
orp:off
animation:off
font:Toronto_14.pcf
smart_pacing:off
brightness:50
```

Simple key:value pairs. Loaded at startup, written on change.

---

## 12. Test Suite

### Layer 1: Unit tests (`tests/unit/`)

Run with: `pytest tests/unit/`

| File | Coverage |
|------|----------|
| `test_book_reader.py` | step_forward/backward, cache behavior, save/load (line+word), chapter index building, empty lines, long words, EOF |
| `test_state.py` | WPM floor, speed calculation, smart pacing delays, ramp-up |
| `test_parse.py` | Filename parsing: series, genre, author, title, wordcount, malformed names, missing fields |
| `test_clean_word.py` | Smart quote replacement, long word splitting on hyphens |
| `test_analytics.py` | Stats accumulation, file persistence, derived calculations |
| `test_menu.py` | Hierarchy building from metadata, navigation (drill in/out), recently read ordering |

**Fixtures:** Temp directories with sample .txt book files, temp save directories, mock hardware modules (displayio, keypad, rotaryio stubs).

### Layer 2: Integration tests (`tests/integration/`)

Run with: `pytest tests/integration/` (requires simulator running via `npm run dev`)

Uses Playwright to drive the browser simulator.

| File | Coverage |
|------|----------|
| `test_reading_flow.py` | Start/pause/resume, word display verification, WPM adjustment, end-of-book |
| `test_navigation.py` | Chapter jump, % jump, word stepping, save accuracy after nav |
| `test_menu.py` | Hierarchy navigation, book selection from categories, settings changes |
| `test_persistence.py` | Exact position restore across sim restart, per-book independence, recently read updates |
| `test_themes.py` | Skin cycling, ORP mode toggling, animation enable/disable |

**Infrastructure:**
- Playwright sends button/encoder events via `page.evaluate()` to the worker
- Canvas pixel sampling for display verification
- `pytest.ini` with markers: `@pytest.mark.unit`, `@pytest.mark.integration`

---

## 13. Simulator Updates

The simulator needs updates to support new features:

- **Menu hierarchy:** Shims already support displayio groups. Menu rendering should work as-is.
- **Chapter markers:** BookReader changes are pure Python -- work in Pyodide unchanged.
- **Settings persistence:** Map `saves/settings.txt` to localStorage (same pattern as save files).
- **New skins:** Displayio group changes render through existing canvas renderer.
- **ORP labels:** Multiple labels per word -- renderer already handles labels at arbitrary positions.
- **Animations:** TileGrid position updates render through existing renderer.
- **State inspector:** Update to show new state fields (skin, ORP mode, animation, chapter info).

---

## Verification Plan

### Unit tests
```bash
cd /path/to/picoReader
pip install -e tools/epub2pico   # For converter tests
pytest tests/unit/ -v
```

### Integration tests
```bash
# Terminal 1: start simulator
cd simulator && npm run dev

# Terminal 2: run tests
pytest tests/integration/ -v
```

### Manual verification on hardware
1. Compile modules: `mpy-cross pico_reader/*.py`
2. Copy to Pico: `code.py` + `pico_reader/*.mpy` + fonts
3. Verify: menu hierarchy navigation, book selection, reading with ORP, chapter jump, skin switching, save/load exact position

### Epub converter
```bash
epub2pico --review test_book.epub     # Verify stripping and filename
epub2pico --auto test_books_dir/      # Verify batch processing
```
