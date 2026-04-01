# Phase 5B: Reading Analytics

> **Dependency:** Phase 1 (module split).

**Goal:** Track per-book persistent stats (words read, sessions) and per-session in-memory stats (rolling WPM, reading time).

---

## 1. BookStats (persisted)

File: `saves/stats_<filename>` — key:value format:
```
words_read:12450
sessions:7
```

```python
class BookStats:
    def __init__(self, book_filename):
        self._path = "saves/stats_{}".format(book_filename)
        self.words_read = 0
        self.sessions = 0
        self._load()

    def _load(self):
        try:
            with open(self._path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line:
                        key, val = line.split(':', 1)
                        if key == 'words_read':
                            self.words_read = int(val)
                        elif key == 'sessions':
                            self.sessions = int(val)
        except (OSError, ValueError):
            pass

    def save(self):
        with open(self._path, 'w') as f:
            f.write("words_read:{}\n".format(self.words_read))
            f.write("sessions:{}\n".format(self.sessions))

    def increment_word(self):
        self.words_read += 1

    def start_session(self):
        self.sessions += 1
        self.save()

    def words_remaining(self, total_wordcount):
        return max(0, total_wordcount - self.words_read)

    def estimated_minutes(self, current_wpm, total_wordcount):
        remaining = self.words_remaining(total_wordcount)
        if current_wpm <= 0:
            return 0
        return remaining // current_wpm

    def completion_pct(self, total_wordcount):
        if total_wordcount <= 0:
            return 0
        return min(100, self.words_read * 100 // total_wordcount)
```

---

## 2. SessionStats (in-memory)

```python
class SessionStats:
    def __init__(self):
        self.words = 0
        self.start_time = time.monotonic()
        self._wpm_samples = []
        self._max_samples = 60

    def record_word(self, wpm):
        self.words += 1
        self._wpm_samples.append(wpm)
        if len(self._wpm_samples) > self._max_samples:
            self._wpm_samples.pop(0)

    def average_wpm(self):
        if not self._wpm_samples:
            return 0
        return sum(self._wpm_samples) // len(self._wpm_samples)

    def reading_time_minutes(self):
        return int((time.monotonic() - self.start_time) // 60)
```

Memory: ~600 bytes (60 ints rolling window).

---

## 3. Integration points

**In `select_and_play()`:**
```python
book_stats = BookStats(book.book)
book_stats.start_session()
session_stats = SessionStats()
state.book_stats = book_stats  # For display access
```

**In `main_loop`, after displaying a word:**
```python
if state.book_stats:
    state.book_stats.increment_word()
```

**In periodic save (every SAVE_INTERVAL):**
```python
book.save_place()
if state.book_stats:
    state.book_stats.save()
```

**Stats display screen** (accessible from menu, Phase 2):
Simple label-based info screen showing words read, sessions, completion %, estimated time remaining, session words, avg WPM, session time. Dismissed with CENTER or UP.

---

## 4. Unit tests (`test_analytics.py`)

| Test | Expected |
|------|----------|
| Fresh BookStats | words_read=0, sessions=0 |
| increment_word x5 | words_read=5 |
| start_session | sessions=1, file written |
| save + load round-trip | Values preserved |
| Missing file | Defaults (0, 0) |
| Corrupted file | Defaults |
| words_remaining(10000) with 3000 read | 7000 |
| words_remaining with over-read | 0 (clamped) |
| estimated_minutes(200, 10000) with 3000 | 35 |
| estimated_minutes(0, ...) | 0 (no div by zero) |
| completion_pct(10000) with 5000 | 50 |
| completion_pct(0) | 0 |
| SessionStats.record_word | words incremented |
| SessionStats.average_wpm([200,220,180]) | 200 |
| Rolling window caps at 60 | Oldest dropped |

---

## Task order

1. Create `pico_reader/analytics.py` with BookStats + SessionStats
2. Wire into `select_and_play` and `main_loop`
3. Add `book_stats` attribute to AppState
4. Update `__init__.py` re-exports
5. Write `tests/unit/test_analytics.py`
6. Run tests
7. Commit
