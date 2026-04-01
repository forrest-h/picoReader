# Phase 1B: Save System Upgrade + Settings Persistence

> **Dependency:** Phase 1A (module split must be complete).

**Goal:** Upgrade save format to `line:word` for exact position restoration, and add `settings.py` for persistent user preferences.

---

## 1. Save System — Exact Position

### Changes to `book_reader.py`

Three methods change. The rest of BookReader stays identical.

**`save_place()`** — write `line_num:word_idx`:
```python
def save_place(self):
    with open("saves/save_{}".format(self.book), 'w') as f:
        f.write("{}:{}".format(self.line_num, self.word_idx))
```

**`save_backup()`** — same format:
```python
def save_backup(self):
    with open("saves/save_prev_{}".format(self.book), 'w') as f:
        f.write("{}:{}".format(self.line_num, self.word_idx))
```

**`load_place()`** — backward-compatible parsing:
```python
def load_place(self):
    try:
        with open("saves/save_{}".format(self.book), 'r') as f:
            data = f.read().strip()
        if ':' in data:
            parts = data.split(':')
            self.line_num = int(parts[0])
            self.word_idx = int(parts[1])
        else:
            self.line_num = int(data)
            self.word_idx = 0
    except (OSError, ValueError):
        self.line_num = 0
        self.word_idx = 0
    self._cache_start = -1
    self._cache = []
```

### No other changes needed

- Existing save triggers (pause, menu, step) already call `save_place()` — the new format flows through automatically
- `worker.ts` monkey-patched `_patched_save_place` reads `f.read()` and posts the string — format-transparent, no changes needed

---

## 2. Settings Persistence

### New file: `pico_reader/settings.py`

```python
DEFAULTS = {
    'skin': 'default',
    'palette': '0',
    'orp': 'off',
    'animation': 'off',
    'font': 'Toronto_14.pcf',
    'smart_pacing': 'off',
    'brightness': '50',
}

def load_settings():
    settings = dict(DEFAULTS)
    try:
        with open("saves/settings.txt", 'r') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    key, val = line.split(':', 1)
                    if key in settings:
                        settings[key] = val
    except OSError:
        pass
    return settings

def save_settings(settings):
    with open("saves/settings.txt", 'w') as f:
        for key, val in settings.items():
            f.write("{}:{}\n".format(key, val))

def set_setting(settings, key, value):
    settings[key] = value
    save_settings(settings)
```

### Integration with AppState

In `state.py`, `AppState.__init__()` applies loaded settings:
```python
def __init__(self, settings=None):
    self.mode = self.MODE_MENU
    self.playing = False
    self.finished = False
    self.wpm = DEFAULT_WPM
    self.speed = 60.0 / DEFAULT_WPM
    self.brightness = DEFAULT_BRIGHTNESS
    self.theme_index = 0
    if settings:
        self.theme_index = int(settings.get('palette', '0'))
        self.brightness = int(settings.get('brightness', str(DEFAULT_BRIGHTNESS)))
```

In `main.py`, `main()` loads settings before creating AppState:
```python
from .settings import load_settings
# ...
settings = load_settings()
state = AppState(settings=settings)
```

### Add to `__init__.py` re-exports

```python
from .settings import load_settings, save_settings, set_setting
```

---

## Task order

1. Update `save_place()`, `save_backup()`, `load_place()` in `book_reader.py`
2. Create `pico_reader/settings.py`
3. Update `state.py` to accept settings in `__init__`
4. Update `main.py` to load settings and pass to AppState
5. Update `__init__.py` to re-export settings functions
6. Syntax-check all changed files
7. Commit
