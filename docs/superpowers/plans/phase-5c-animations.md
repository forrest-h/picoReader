# Phase 5C: Animations

> **Dependency:** Phase 3A (skin system — animations append to skin's reader group).

**Goal:** Add optional Walker, Particles, and Page Turn animations that overlay the reader display.

---

## 1. Animation interface

Each animation implements:

```python
class Animation:
    def build(self, display):
        """Return list of displayio elements to append to reader group."""

    def tick(self, state, book, display):
        """Update positions/frames. Called after each word, before refresh."""

    def destroy(self):
        """Clean up references."""
```

Only one animation active at a time. Elements appended after reader group index 7.

### Swap logic (in Display or main_loop):
```python
# Remove old animation elements
while len(reader_group) > 8:
    reader_group.pop()
# Add new
if new_animation:
    for elem in new_animation.build(display):
        reader_group.append(elem)
```

---

## 2. Registry (`animations/__init__.py`)

```python
ANIMATION_NAMES = ['off', 'walker', 'particles', 'page_turn']

def load_animation(name):
    if name == 'walker':
        from .walker import Animation
    elif name == 'particles':
        from .particles import Animation
    elif name == 'page_turn':
        from .page_turn import Animation
    else:
        return None
    return Animation()
```

Lazy imports — only active animation's module loaded.

---

## 3. Walker (`animations/walker.py`)

- 5x5 sprite, 6 frames in a 30x5 Bitmap (~150 bytes)
- Single TileGrid, frame selected by `tilegrid[0] = frame_index`
- Position: `x = int(progress * (160 - 5))` where `progress = line_num / book_len`
- Y: `DISPLAY_HEIGHT - 6` (1px above bottom)
- Frame selection: <=150 WPM → walk (0-1), 150-300 → jog (2-3), 300+ → run (4-5)
- Alternates frames each tick

---

## 4. Particles (`animations/particles.py`)

- 4 single-pixel TileGrids in margins (leftmost/rightmost 12px)
- Drift down 1px per tick, wrap to top with pseudo-random X
- Pseudo-random via `time.monotonic()` mod arithmetic (avoids `random` import)
- Color matches theme highlight via `apply_theme()` callback
- ~120 bytes total

---

## 5. Page Turn (`animations/page_turn.py`)

- Label in bottom-right: `"pg XX"`
- Page = `words_read // 250 + 1`
- On page increment: flash label to highlight color for 3 ticks
- Reads `state.book_stats.words_read` (requires Phase 5B analytics)
- ~50 bytes

---

## 6. main_loop integration

```python
disp.show_word(cleaned)
disp.show_wpm(state.wpm)
if active_animation:
    active_animation.tick(state, book, disp)
disp.refresh()
```

---

## 7. Unit tests (`test_animations.py`)

| Test | Expected |
|------|----------|
| Walker at line 0/1000 | x = 0 |
| Walker at line 500/1000 | x ≈ 77 |
| Walker at line 1000/1000 | x = 155 |
| Walker WPM 100 | frames 0-1 (walk) |
| Walker WPM 200 | frames 2-3 (jog) |
| Walker WPM 400 | frames 4-5 (run) |
| Particle at y=127 wraps | y=0 after tick |
| Particles stay in bounds | 0 <= x < 160, 0 <= y < 128 |
| Page count 0 words | pg 1 |
| Page count 250 words | pg 2 |
| Page increment triggers flash | flash_ticks=3 |

---

## Task order

1. Create `pico_reader/animations/__init__.py` with registry
2. Create `animations/walker.py`
3. Create `animations/particles.py`
4. Create `animations/page_turn.py`
5. Wire animation lifecycle into main_loop and reader group
6. Write `tests/unit/test_animations.py`
7. Run tests
8. Commit
