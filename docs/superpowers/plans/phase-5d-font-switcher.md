# Phase 5D: Font Switcher

> **Dependency:** Phase 1 (settings), Phase 3A (skin system — fonts passed to skin).

**Goal:** Let users cycle through 8 PCF fonts in Settings, persisted across power cycles.

---

## 1. Available fonts

All 14px PCF files in `fonts/`:

```python
# In constants.py
AVAILABLE_FONTS = [
    'Toronto_14.pcf',
    'Aleo-Regular-14.pcf',
    'Bitter-Regular-14.pcf',
    'BreeSerif-Regular-14.pcf',
    'CreteRound-Regular-14.pcf',
    'IBMPlexSerif-SemiBold-14.pcf',
    'Merriweather-Regular-14.pcf',
    'SpecialElite-Regular-14.pcf',
]
```

---

## 2. Font loading utility

```python
def load_reading_font(font_name):
    try:
        return bitmap_font.load_font("fonts/{}".format(font_name))
    except OSError:
        return bitmap_font.load_font("fonts/Toronto_14.pcf")
```

Fallback prevents crash if font file missing.

---

## 3. Settings persistence

- Stored as `font:Toronto_14.pcf` in `saves/settings.txt`
- Loaded at startup, stored in `AppState.font_name`
- Applied on next `build_group()` (not mid-reading)

---

## 4. When font takes effect

1. User selects font in Settings menu
2. Setting persisted to `settings.txt`
3. `AppState.font_name` updated
4. User returns to reader → skin's `build_group()` uses new font
5. Old font object garbage collected

Only one reading font loaded at a time. `_smallfont` (Toronto_9.pcf) stays constant for UI.

---

## 5. Settings handler

```python
def cycle_font(state, book, disp):
    current = state.font_name
    idx = AVAILABLE_FONTS.index(current) if current in AVAILABLE_FONTS else 0
    idx = (idx + 1) % len(AVAILABLE_FONTS)
    state.font_name = AVAILABLE_FONTS[idx]
    set_setting(state.settings, 'font', state.font_name)
    # Preview: show font name in current font
    disp.show_word(state.font_name.split('.')[0])
    disp.refresh()
```

---

## 6. ORP interaction

ORP glyph width calculations use `font.get_glyph(ord(c)).shift_x`. Since ORP code references the skin's font, and font changes on next `build_group()`, both update together. No special handling needed.

---

## Task order

1. Add `AVAILABLE_FONTS` to `constants.py`
2. Add `load_reading_font()` utility
3. Add `font_name` to AppState (from settings)
4. Add `cycle_font` handler, wire to Settings
5. Update skin `build_group` to use `state.font_name`
6. Syntax-check, manual test
7. Commit
