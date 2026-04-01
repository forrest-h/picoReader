# Phase 5A: Smart Pacing

> **Dependency:** Phase 1 (module split).

**Goal:** Add dynamic word display duration based on word complexity, with a 50%→100% ramp-up over 10 seconds on each play action.

---

## 1. `calculate_word_delay()` in `state.py`

```python
def calculate_word_delay(word, base_wpm, is_paragraph_start, ramp_factor):
    effective_wpm = base_wpm * ramp_factor
    delay = 60.0 / effective_wpm
    multiplier = 1.0

    stripped = word.rstrip('"\')')
    if not stripped:
        return delay

    if len(word) > 8:
        multiplier *= 1.3
    elif len(word) <= 3:
        multiplier *= 0.8

    last_char = stripped[-1]
    if last_char in '.!?':
        multiplier *= 1.8
    elif last_char in ',;:':
        multiplier *= 1.5

    if is_paragraph_start:
        multiplier *= 1.4

    return delay * multiplier
```

Multipliers stack multiplicatively. Example: long sentence-ending word = 1.3 * 1.8 = 2.34x.

---

## 2. AppState additions

```python
class AppState:
    def __init__(self, settings=None):
        # ... existing ...
        self.smart_pacing = False
        self.play_start_time = 0.0

    def start_playing(self):
        self.playing = True
        self.play_start_time = time.monotonic()

    def get_ramp_factor(self):
        if not self.smart_pacing:
            return 1.0
        elapsed = time.monotonic() - self.play_start_time
        ramp = min(1.0, elapsed / 10.0)
        return 0.5 + 0.5 * ramp
```

Load `smart_pacing` from settings: `self.smart_pacing = settings.get('smart_pacing', 'off') == 'on'`

---

## 3. Handler change

`toggle_play()` calls `state.start_playing()` instead of `state.playing = True`:

```python
def toggle_play(state, book, disp):
    if state.finished:
        # restart logic...
        state.start_playing()
        return
    if state.playing:
        book.save_place()
        state.playing = False
    else:
        state.start_playing()
```

---

## 4. main_loop integration

Replace `if now - last_word_time >= state.speed:` with:

```python
if smart_pacing_enabled:
    ramp = state.get_ramp_factor()
    word_delay = calculate_word_delay(cleaned, state.wpm, is_para_start, ramp)
else:
    word_delay = state.speed
```

Paragraph start detection:
```python
is_para_start = (book.word_idx == 1 and
                 book.line_num > 0 and
                 book._get_words(book.line_num - 1) == [])
```

---

## 5. Unit tests (`test_smart_pacing.py`)

| Test | Expected |
|------|----------|
| Short word, no punctuation | 0.8x multiplier |
| Long word (>8 chars) | 1.3x multiplier |
| Comma ending | 1.5x |
| Sentence end (`.`) | 1.8x |
| Long + sentence end | 1.3 * 1.8 = 2.34x |
| Paragraph start + long + sentence end | 1.4 * 1.3 * 1.8 = 3.276x |
| Trailing quote `said."` | Sentence end detected |
| Empty string | Base delay, no crash |
| Ramp at t=0 | factor = 0.5 |
| Ramp at t=5 | factor = 0.75 |
| Ramp at t=10 | factor = 1.0 |
| Ramp at t=15 | factor = 1.0 (clamped) |

---

## Task order

1. Add `calculate_word_delay()` to `state.py`
2. Add `start_playing()`, `get_ramp_factor()`, `smart_pacing`, `play_start_time` to AppState
3. Update `toggle_play()` in `input_handlers.py`
4. Update `main_loop` in `main.py`
5. Write `tests/unit/test_smart_pacing.py`
6. Run tests
7. Commit
