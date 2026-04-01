# Phase 3B: New Skins + ORP Highlighting

> **Dependency:** Phase 3A (skin system + default skin must be in place).

**Goal:** Add Terminal, RPG, and Typewriter skins, plus ORP (Optimal Recognition Point) highlighting that works with all skins.

---

## 1. ORP System (`pico_reader/orp.py`)

Shared helper used by all skins. Keeps ORP math in one place.

### ORP index calculation

```python
def calc_orp_index(word):
    """Return the index of the ORP letter (roughly 1/3 into the word)."""
    n = len(word)
    if n <= 1:
        return 0
    return min(n - 1, max(1, (n + 1) // 3 - 1))
```

### 3-label fixed-anchor positioning

The ORP letter sits at a fixed screen X (default X=80, horizontal center). Prefix extends left, suffix extends right. This creates the Spritz-style fixed focus point.

```python
def calc_orp_positions(word, font, anchor_x=80):
    """Return (prefix, orp_char, suffix, prefix_x, orp_x, suffix_x).

    Uses font glyph metrics to calculate pixel positions.
    """
    idx = calc_orp_index(word)
    prefix = word[:idx]
    orp_char = word[idx]
    suffix = word[idx + 1:]

    # Get pixel widths from font glyph metrics
    prefix_width = sum(font.get_glyph(ord(c)).shift_x for c in prefix) if prefix else 0
    orp_width = font.get_glyph(ord(orp_char)).shift_x

    prefix_x = anchor_x - prefix_width - orp_width // 2
    orp_x = anchor_x - orp_width // 2
    suffix_x = anchor_x + orp_width // 2

    # Clamp to screen bounds
    prefix_x = max(0, prefix_x)
    suffix_x = min(155, suffix_x)  # Leave 5px margin

    return prefix, orp_char, suffix, prefix_x, orp_x, suffix_x
```

### ORP in show_word()

Each skin's `show_word(word, orp_mode)` checks `orp_mode`:
- `None` → single centered label (current behavior)
- `'color'` → 3 labels: prefix (text color), ORP letter (highlight color), suffix (text color)
- `'bold'` → 2 labels: first ~40% bright, rest dimmed

All 3 (or 4) labels are always present in the group to avoid rebuild on ORP toggle. When ORP is off, prefix and suffix labels have empty text.

### Bold-Fade split point

```python
def calc_bold_split(word):
    """Return (bold_part, fade_part) for Bold-Fade ORP mode."""
    split = max(1, int(len(word) * 0.4))
    return word[:split], word[split:]
```

---

## 2. Terminal Skin (`skins/terminal.py`)

### Palettes
```python
PALETTES = [
    {'name': 'Green Phosphor', 'bg': 0x000000, 'phosphor': 0x33ff33, 'dim': 0x1a8a1a},
    {'name': 'Amber Phosphor', 'bg': 0x000000, 'phosphor': 0x00b0ff, 'dim': 0x005880},  # BGR!
    {'name': 'Blue Phosphor',  'bg': 0x000000, 'phosphor': 0xff3300, 'dim': 0x801a00},  # BGR!
]
```

Note: Colors are BGR format per CLAUDE.md.

### Layout
| Group index | Widget | Purpose |
|---|---|---|
| 0 | TileGrid (background) | Black fill |
| 1 | Label (smallfont) | Path header: `C:\BOOKS\TITLE>` |
| 2 | Label (font) | Word display (or 3 labels for ORP) |
| 3 | Label (font) | Cursor `_` — **visible only when paused** |
| 4 | Label (smallfont) | ASCII progress: `[=====>    ] 38%` |
| 5 | Label (smallfont) | WPM display |

### Cursor behavior
- When `show_word()` is called, cursor visibility depends on external state
- Skin gets a `set_cursor_visible(visible)` method
- `main_loop` calls `skin.set_cursor_visible(not state.playing)` (or Display wraps this)

### ASCII progress bar
Progress rendered as text label, not bitmap:
```python
def update_progress(self, pct):
    filled = int(pct * 10)
    bar = '=' * filled + '>' + ' ' * (10 - filled)
    self._progress_label.text = "[{}] {}%".format(bar, int(pct * 100))
```

---

## 3. RPG Skin (`skins/rpg.py`)

### Palettes
```python
PALETTES = [
    {'name': 'Gold/Crimson', 'bg': 0x2e1a1a, 'border': 0x00c2e6, 'text': 0xeeeeee, 'hp_fill': 0x6045e9},  # BGR
    {'name': 'Ice/Blue',     'bg': 0x2e1a1a, 'border': 0xe6c200, 'text': 0xeeeeee, 'hp_fill': 0xe6c200},
    {'name': 'Forest/Green', 'bg': 0x1a2e1a, 'border': 0x00c200, 'text': 0xeeeeee, 'hp_fill': 0x00c200},
]
```

### Layout
| Group index | Widget | Purpose |
|---|---|---|
| 0 | TileGrid (background) | Dark blue fill |
| 1 | Rect | Dialogue box border (outline) |
| 2 | Rect | Dialogue box fill (inside border) |
| 3 | Label (smallfont) | Flavor text: `* A voice speaks... *` |
| 4 | Label (font) | Word display |
| 5 | Label (smallfont) | `PROG` label |
| 6 | Bitmap progress bar | HP-bar style fill |
| 7 | Label (smallfont) | WPM display |

### HP-bar progress
Uses a mutable Bitmap (same approach as current progress bar but taller, ~6px):
```python
def update_progress(self, pct):
    width = int(pct * 120)  # Bar is 120px wide inside box
    for x in range(self._last_width, width):
        for y in range(6):
            self._hp_bmp[x, y] = 1
```

---

## 4. Typewriter Skin (`skins/typewriter.py`)

### Palettes
```python
PALETTES = [
    {'name': 'Cream/Brown',  'bg': 0xd8ecf4, 'ink': 0x1f2b3d, 'dim': 0x557388},  # BGR
    {'name': 'Aged/Yellowed','bg': 0xb0d8e8, 'ink': 0x1a3040, 'dim': 0x507090},
    {'name': 'Night/Sepia',  'bg': 0x303848, 'ink': 0xa0b8c8, 'dim': 0x607080},
]
```

### Layout
| Group index | Widget | Purpose |
|---|---|---|
| 0 | TileGrid (background) | Cream fill |
| 1 | Label (font) | Word display (slight Y offset for analog feel) |
| 2 | Bitmap (160, 1, 2) | Simple underline progress |
| 3 | Label (smallfont) | WPM: `~ 200 wpm ~` |

### Analog offset
Word Y position has a small random jitter (1-2 pixels) for typewriter feel:
```python
def show_word(self, word, orp_mode=None):
    # Pseudo-random offset from word content
    offset = (ord(word[0]) % 3) - 1 if word else 0  # -1, 0, or +1
    self._word_label.anchored_position = (80, 70 + offset)
    self._word_label.text = "{:^30}".format(word)
```

---

## 5. Unit tests

- `test_orp.py`: ORP index for word lengths 1-15, position calculation doesn't overflow 160px
- `test_skins.py`: Parameterized across all 4 skins — `build_group()` returns a group, `apply_palette()` doesn't crash for each palette index, `show_word()` with each ORP mode

---

## Task order

1. Create `pico_reader/orp.py` with `calc_orp_index`, `calc_orp_positions`, `calc_bold_split`
2. Update Default skin to support ORP modes in `show_word()`
3. Create `skins/terminal.py`
4. Create `skins/rpg.py`
5. Create `skins/typewriter.py`
6. Wire Settings skin/orp cycling into `input_handlers.py`
7. Write `tests/unit/test_orp.py`
8. Write `tests/unit/test_skins.py`
9. Syntax-check, run tests
10. Commit
