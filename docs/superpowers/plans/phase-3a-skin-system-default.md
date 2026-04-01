# Phase 3A: Skin System Architecture + Default Skin

> **Dependency:** Phase 1 (module split, settings).

**Goal:** Build the skin/palette architecture and migrate the existing display into the Default skin. After this phase, the app looks and works exactly the same but Display delegates to a skin object.

---

## 1. Skin interface contract

Every skin class implements (duck-typed, no ABC):

```python
class Skin:
    PALETTES = [...]  # List of palette dicts

    def __init__(self, font, smallfont):
        """Store fonts. Do NOT build displayio objects here."""

    def build_group(self, display_width, display_height):
        """Create and return a displayio.Group. Called once on skin activation."""

    def show_word(self, word, orp_mode=None):
        """Update word display. orp_mode: None, 'color', or 'bold'."""

    def show_wpm(self, wpm):
        """Update WPM indicator."""

    def update_progress(self, pct):
        """Update progress. pct is 0.0-1.0 float."""

    def reset_progress(self):
        """Reset progress to zero."""

    def apply_palette(self, palette_index):
        """Apply colors without rebuilding group."""

    def get_highlight_color(self):
        """Return current palette's highlight/accent color."""
```

Takes dimensions (not display reference) so skins are testable without hardware.

---

## 2. Skin registry

### File: `pico_reader/skins/__init__.py`

```python
SKIN_NAMES = ['default', 'terminal', 'rpg', 'typewriter']

def load_skin(name):
    """Lazy-import and return Skin class. Only one skin in RAM at a time."""
    if name == 'default':
        from .default import Skin
    elif name == 'terminal':
        from .terminal import Skin
    elif name == 'rpg':
        from .rpg import Skin
    elif name == 'typewriter':
        from .typewriter import Skin
    else:
        from .default import Skin
    return Skin
```

No `importlib` — explicit conditionals are more RAM-friendly on CircuitPython.

---

## 3. Default skin (`skins/default.py`)

Preserves the EXACT current layout from `Display._build_reader_group()`:

| Group index | Widget | Purpose |
|---|---|---|
| 0 | TileGrid (full-screen Bitmap(1)) | Background fill |
| 1 | label.Label (font) | Word display |
| 2-5 | Rect x4 | Guide marks (crosshair) |
| 6 | TileGrid (Bitmap(160, 2, 2)) | Mutable progress bar |
| 7 | label.Label (smallfont) | WPM display |

### 5 palettes (existing THEMES preserved as-is, BGR values):

```python
PALETTES = [
    {'name': 'Dark',       'bg': 0x000000, 'text': 0xe7e7e7, 'wpm': 0x4c4c4c, 'highlight': 0x7c7c7c},
    {'name': 'Light',      'bg': 0xf3f3f3, 'text': 0x000000, 'wpm': 0xa1a1a1, 'highlight': 0x949494},
    {'name': 'Gray',       'bg': 0x696969, 'text': 0x000000, 'wpm': 0x272727, 'highlight': 0x403f3f},
    {'name': 'Crimson',    'bg': 0x460808, 'text': 0xbdbdbd, 'wpm': 0x898888, 'highlight': 0x0e8ee6},
    {'name': 'Muted Dark', 'bg': 0x000000, 'text': 0x696969, 'wpm': 0x4c4c4c, 'highlight': 0x696969},
]
```

The `build_group()` method is essentially the current `_build_reader_group()` code moved into the skin. `apply_palette()` is the current `apply_theme()` logic.

---

## 4. Display class changes

`Display` becomes a thin coordinator:

```python
class Display:
    def __init__(self, hw_display, backlight, font, smallfont, skin_name='default'):
        self.display = hw_display
        self.backlight = backlight
        self._font = font
        self._smallfont = smallfont
        self._set_skin(skin_name)
        self._build_menu_group()  # Menu unchanged for now

    def _set_skin(self, skin_name):
        SkinClass = load_skin(skin_name)
        self.skin = SkinClass(self._font, self._smallfont)
        self.reader_group = self.skin.build_group(DISPLAY_WIDTH, DISPLAY_HEIGHT)

    def show_word(self, word, orp_mode=None):
        self.skin.show_word(word, orp_mode)

    def show_wpm(self, wpm):
        self.skin.show_wpm(wpm)

    def update_progress(self, line_num, book_len):
        if book_len > 0:
            self.skin.update_progress(line_num / book_len)

    def reset_progress(self):
        self.skin.reset_progress()

    def apply_theme(self, theme):
        # BACKWARD COMPAT: map old THEMES[i] call to palette
        # Find matching palette index
        pass  # Handled by callers switching to set_palette()

    def set_skin(self, skin_name):
        self._set_skin(skin_name)

    def set_palette(self, index):
        self.skin.apply_palette(index)

    # show_reader_screen, show_menu_screen, set_brightness, refresh — unchanged
```

### Migration path for callers

Current callers use `disp.apply_theme(THEMES[state.theme_index])`. After this phase:
- `input_handlers.py` changes `apply_theme(THEMES[idx])` → `set_palette(idx)`
- `select_and_play()` changes `disp.apply_theme(THEMES[state.theme_index])` → `disp.set_palette(state.theme_index)`

---

## 5. What this does NOT include

- Terminal, RPG, Typewriter skins (Phase 3B)
- ORP highlighting (Phase 3B)
- Menu skinning (deferred)
- Font switching (Phase 5)

After this phase, the app looks identical but the architecture supports adding new skins by dropping a file in `skins/`.

---

## Task order

1. Create `pico_reader/skins/` directory with `__init__.py`
2. Create `skins/default.py` — extract `_build_reader_group()` and `apply_theme()` logic from Display
3. Refactor `display.py` to delegate to skin
4. Update `input_handlers.py` to use `set_palette()` instead of `apply_theme(THEMES[...])`
5. Update `__init__.py` re-exports if needed
6. Syntax-check all files
7. Run existing unit tests (should still pass)
8. Commit
