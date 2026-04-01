# Phase 2: Menu Navigation, Chapters, Jump Mode, Recently Read, Genre Parsing

> **Dependency:** Phase 1 must be complete. Assumes `firmware/pico_reader/` module structure exists with `state.py`, `book_reader.py`, `display.py`, `input_handlers.py`, `utils.py`, `constants.py`, `hardware.py`, `settings.py`, and `main.py`.

**Goal:** Replace the flat book carousel with a hierarchical iPod-style menu system, add chapter navigation and jump mode to the reader, track recently read books, and extend filename parsing to support genre tags.

---

## 1. Genre Parsing in Filenames

### What changes in `utils.py`

Extended filename format:

```
(Series) [Genre] Author - Title (wordcount).txt
```

Both `(Series)` and `[Genre]` are optional. Examples:

```
(Earthsea 1) [Fantasy] Ursula K Le Guin - A Wizard Of Earthsea (1835).txt
[Science Fiction] Andy Weir - The Martian (3500).txt
Terry Pratchett - Guards Guards (9200).txt
```

**Updated `parse_book_filename()` return value:** Changes from `(title, author, series, wordcount)` tuple to `(title, author, series, wordcount, genre)` tuple. The fifth element is a string; empty genre maps to `"Uncategorized"`.

### Parsing logic (pseudocode)

```python
def parse_book_filename(filename):
    name = filename.rsplit('.', 1)[0]
    parts = name.split(' - ', 1)
    # ... existing series extraction from (Series) prefix ...

    # After stripping series prefix, check for [Genre] token
    # in the remaining author_part before the ' - ' split
    if '[' in author_part:
        bracket_open = author_part.index('[')
        bracket_close = author_part.index(']', bracket_open)
        genre = author_part[bracket_open + 1 : bracket_close].strip()
        author = author_part[bracket_close + 1 :].strip()
    else:
        genre = ''

    # ... existing title/wordcount extraction ...
    if not genre:
        genre = 'Uncategorized'
    return (title, author, series, wordcount, genre)
```

### Backward compatibility

All consumers of metadata tuples must handle the new 5th element. Phase 1's `book_metadata` is a list of tuples indexed positionally. Adding `genre` at index 4 doesn't break existing `meta[0]`, `meta[1]`, `meta[2]`, `meta[3]` access.

Places that unpack all 4 elements need updating:
- `main.py` where `lens = [m[3] for m in metadata]` -- already works (index 3 unchanged)
- `Display.show_menu_screen()` where `title, author, series = book_metadata[book_idx][:3]` -- already works (slice)
- `_state_tracker.py` where `meta[0]` and `meta[1]` are accessed -- already works

### Verification

Unit tests in `tests/unit/test_utils.py`:
- Parse filename with series + genre + all fields
- Parse filename with genre but no series
- Parse filename with series but no genre (defaults to "Uncategorized")
- Parse filename with neither series nor genre
- Parse malformed bracket (missing closing `]`) falls back gracefully

---

## 2. Chapter Index in BookReader

### What changes in `book_reader.py`

New chapter marker format in text files:

```
---CHAPTER: Chapter Title Here---
```

A line is a chapter marker if it starts with `---CHAPTER:` and ends with `---`.

### New attributes on BookReader

```python
self.chapters = []       # [(line_num, title), ...] sorted by line_num
self.chapter_index = -1  # Index into self.chapters for current position, -1 = before first chapter
```

### `build_chapter_index()` method

Scanned at book load time (called from `select_book()` after `load_place()`). Reads the entire book file line by line, looking for chapter markers.

```python
def build_chapter_index(self):
    self.chapters = []
    try:
        with open("/sd/books/{}".format(self.book), 'r') as f:
            line_num = 0
            for line in f:
                stripped = line.strip()
                if stripped.startswith('---CHAPTER:') and stripped.endswith('---'):
                    title = stripped[11:-3].strip()
                    self.chapters.append((line_num, title))
                line_num += 1
    except OSError:
        self.chapters = []
    self._update_chapter_index()
```

**RAM concern:** This only stores `(int, str)` tuples, not entire file content. A book with 50 chapters uses ~2-3KB. Acceptable.

### `_update_chapter_index()` method

Finds which chapter the current `line_num` falls in:

```python
def _update_chapter_index(self):
    self.chapter_index = -1
    for i, (ch_line, _) in enumerate(self.chapters):
        if self.line_num >= ch_line:
            self.chapter_index = i
        else:
            break
```

Called after any position change (load_place, jump, chapter nav).

### `jump_to_chapter(direction)` method

```python
def jump_to_chapter(self, direction):
    """Jump to previous (-1) or next (+1) chapter. Returns chapter title or None."""
    if not self.chapters:
        return None
    target = self.chapter_index + direction
    if target < 0 or target >= len(self.chapters):
        return None
    line_num, title = self.chapters[target]
    self.line_num = line_num + 1  # Skip the marker line itself
    self.word_idx = 0
    self._cache_start = -1
    self._cache = []
    self.chapter_index = target
    return title
```

### Integration with `select_book()`

```python
def select_book(self, book_id):
    self.book_id = book_id
    self.book = self.books[book_id]
    self.book_len = self.book_lens[book_id]
    self.load_place()
    self.build_chapter_index()
```

### Verification

Unit tests in `tests/unit/test_book_reader.py`:
- `build_chapter_index()` with multiple markers returns correct `[(line, title)]` list
- `build_chapter_index()` with no markers returns empty list
- `jump_to_chapter(1)` advances to next chapter, returns title
- `jump_to_chapter(-1)` returns to previous chapter, returns title
- `jump_to_chapter(1)` at last chapter returns None (no-op)
- `jump_to_chapter(-1)` before first chapter returns None (no-op)
- `_update_chapter_index()` correctly identifies current chapter from line_num

---

## 3. Recently Read Tracking

### New file: `pico_reader/recent.py`

Manages `saves/recent_order.txt` -- ordered list of book filenames, one per line, most recent first. Capped at 10.

### Interface

```python
MAX_RECENT = 10

def load_recent():
    """Load recent order from file. Returns list of filenames, most recent first."""
    try:
        with open("saves/recent_order.txt", 'r') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        return lines[:MAX_RECENT]
    except OSError:
        return []

def update_recent(filename):
    """Add filename to top of recent list. Removes duplicate if present. Writes to disk."""
    recent = load_recent()
    if filename in recent:
        recent.remove(filename)
    recent.insert(0, filename)
    recent = recent[:MAX_RECENT]
    with open("saves/recent_order.txt", 'w') as f:
        for name in recent:
            f.write(name + '\n')
    return recent
```

### Integration points

- **`select_and_play()` in `input_handlers.py`:** After a book is selected from the menu, call `update_recent(book.book)` before starting playback.
- **Menu system:** The "Recently Read" submenu calls `load_recent()` to get the ordered filename list, then resolves each to its metadata for display.

### Simulator

The worker.ts save-mirroring mechanism already catches all writes to `/saves/*`. The `recent_order.txt` file is in `/saves/`, so it will be persisted to localStorage automatically. No worker.ts changes needed.

### Verification

Unit tests in `tests/unit/test_recent.py`:
- `load_recent()` with no file returns empty list
- `update_recent()` adds to front of list
- `update_recent()` moves existing entry to front (dedup)
- List is capped at 10 after 11 additions
- Round-trip: `update_recent()` then `load_recent()` returns correct order

---

## 4. Hierarchical Menu System

This is the largest piece of Phase 2. It replaces the current flat book carousel with an iPod-style drill-in/drill-out menu.

### New file: `pico_reader/menu.py`

### 4.1 Data Model

The menu is a tree of nodes. Each node is either a **category** (has children) or a **leaf** (selects a book). The tree is built once at startup from book metadata.

```python
class MenuNode:
    """A single node in the menu tree."""
    def __init__(self, label, children=None, book_id=None):
        self.label = label          # Display text
        self.children = children    # List[MenuNode] or None for leaves
        self.book_id = book_id      # int index into books[] or None for categories
```

A `MenuNode` with `children` is a category. A `MenuNode` with `book_id` is a selectable book. These are mutually exclusive: categories have `children != None, book_id == None`; books have `children == None, book_id != None`.

### 4.2 Menu State

```python
class MenuState:
    """Tracks current position in the menu tree."""
    def __init__(self, root):
        self.root = root              # The root MenuNode
        self.path = [root]            # Stack of MenuNodes from root to current level
        self.cursor = 0               # Selected index within current children list
```

Key properties:
- `current_node` -- `self.path[-1]` (the node whose children are displayed)
- `current_items` -- `self.current_node.children` (the list being scrolled)
- `depth` -- `len(self.path) - 1`

### 4.3 Building the Tree

```python
def build_menu_tree(books, book_metadata, recent_filenames):
    """Build the menu tree from book data. Returns root MenuNode.

    Args:
        books: list of filenames
        book_metadata: list of (title, author, series, wordcount, genre) tuples
        recent_filenames: list of filenames from recent_order.txt
    """
```

**Tree structure:**

```
picoReader (root)
 +-- All Books         -> children: one MenuNode per book, sorted A-Z by title
 +-- Recently Read     -> children: one MenuNode per recent book (up to 10), in recency order
 +-- Authors           -> children: one MenuNode per unique author, sorted
 |    +-- <Author>     -> children: that author's books, sorted by title
 +-- Series            -> children: one MenuNode per unique series, sorted
 |    +-- <Series>     -> children: books in that series, sorted by series number in filename
 +-- Genres            -> children: one MenuNode per unique genre, sorted
 |    +-- <Genre>      -> children: books in that genre, sorted by title
 +-- Settings          -> children: [] (empty, stub for Phase 3/5)
```

**Build steps (pseudocode):**

```python
def build_menu_tree(books, book_metadata, recent_filenames):
    # Index: book_id -> metadata
    # Sort books by title for "All Books"
    all_books_sorted = sorted(range(len(books)), key=lambda i: book_metadata[i][0].lower())
    all_books_node = MenuNode("All Books", children=[
        MenuNode(book_metadata[i][0], book_id=i) for i in all_books_sorted
    ])

    # Recently Read -- preserve order from recent_filenames
    recent_nodes = []
    filename_to_id = {}
    for i, fn in enumerate(books):
        filename_to_id[fn] = i
    for fn in recent_filenames:
        if fn in filename_to_id:
            bid = filename_to_id[fn]
            recent_nodes.append(MenuNode(book_metadata[bid][0], book_id=bid))
    recent_node = MenuNode("Recently Read", children=recent_nodes)

    # Authors -- group by author
    authors = {}  # author_name -> [(book_id, title)]
    for i, meta in enumerate(book_metadata):
        author = meta[1] if meta[1] else "Unknown"
        authors.setdefault(author, []).append((i, meta[0]))
    author_nodes = []
    for author in sorted(authors.keys(), key=str.lower):
        book_nodes = [MenuNode(title, book_id=bid)
                      for bid, title in sorted(authors[author], key=lambda x: x[1].lower())]
        author_nodes.append(MenuNode(author, children=book_nodes))
    authors_node = MenuNode("Authors", children=author_nodes)

    # Series -- group by series name, sort within by series number
    series_map = {}  # series_name -> [(book_id, filename)]
    for i, meta in enumerate(book_metadata):
        if meta[2]:  # series is non-empty
            series_map.setdefault(meta[2], []).append((i, books[i]))
    series_nodes = []
    for series_name in sorted(series_map.keys(), key=str.lower):
        # Sort by filename which encodes series number in the (Series N) prefix
        book_nodes = [MenuNode(book_metadata[bid][0], book_id=bid)
                      for bid, fn in sorted(series_map[series_name], key=lambda x: x[1])]
        series_nodes.append(MenuNode(series_name, children=book_nodes))
    series_node = MenuNode("Series", children=series_nodes)

    # Genres -- group by genre
    genres = {}  # genre_name -> [(book_id, title)]
    for i, meta in enumerate(book_metadata):
        genre = meta[4] if len(meta) > 4 and meta[4] else "Uncategorized"
        genres.setdefault(genre, []).append((i, meta[0]))
    genre_nodes = []
    for genre_name in sorted(genres.keys(), key=str.lower):
        book_nodes = [MenuNode(title, book_id=bid)
                      for bid, title in sorted(genres[genre_name], key=lambda x: x[1].lower())]
        genre_nodes.append(MenuNode(genre_name, children=book_nodes))
    genres_node = MenuNode("Genres", children=genre_nodes)

    # Settings stub
    settings_node = MenuNode("Settings", children=[])

    root = MenuNode("picoReader", children=[
        all_books_node,
        recent_node,
        authors_node,
        series_node,
        genres_node,
        settings_node,
    ])
    return root
```

### 4.4 Navigation Methods on MenuState

```python
def scroll(self, direction):
    """Scroll cursor by +1 or -1, wrapping around."""
    items = self.current_node.children
    if not items:
        return
    self.cursor = (self.cursor + direction) % len(items)

def select(self):
    """Select current item. Returns book_id if leaf, or None if drilled into category."""
    items = self.current_node.children
    if not items:
        return None
    selected = items[self.cursor]
    if selected.book_id is not None:
        return selected.book_id
    if selected.children is not None:
        self.path.append(selected)
        self.cursor = 0
        return None
    return None

def back(self):
    """Go back one level. Returns False if already at root."""
    if len(self.path) <= 1:
        return False
    self.path.pop()
    self.cursor = 0  # Reset cursor when returning to parent
    return True

def breadcrumb(self):
    """Return breadcrumb string for title bar, e.g. 'Authors > Pratchett'."""
    if len(self.path) <= 1:
        return self.root.label
    # Show last two levels to fit on 160px display
    parts = [n.label for n in self.path[1:]]
    text = " > ".join(parts)
    # Truncate if too long for display (roughly 18 chars at Toronto_9)
    if len(text) > 22:
        text = "..> " + parts[-1]
        if len(text) > 22:
            text = parts[-1][:20]
    return text

def visible_items(self):
    """Return (items_list, cursor_index) for the display to render."""
    return (self.current_node.children, self.cursor)
```

### 4.5 Refreshing the Recently Read Subtree

When a book is opened, `recent_order.txt` is updated. The "Recently Read" node in the tree becomes stale. Rather than rebuilding the entire tree, we replace just that node's children:

```python
def refresh_recent(self, books, book_metadata, recent_filenames):
    """Rebuild the Recently Read node's children in-place."""
    recent_node = self.root.children[1]  # Index 1 = Recently Read
    filename_to_id = {}
    for i, fn in enumerate(books):
        filename_to_id[fn] = i
    recent_node.children = []
    for fn in recent_filenames:
        if fn in filename_to_id:
            bid = filename_to_id[fn]
            recent_node.children.append(MenuNode(book_metadata[bid][0], book_id=bid))
```

### 4.6 Menu Display

The menu display replaces the current `Display.show_menu_screen()` and `Display._build_menu_group()`.

**Layout:** Same 3-slot carousel visual style as the current menu, but now shows menu items (categories or book titles) instead of only book metadata.

```
+---------------------------+
|  Authors > Pratchett      |  <-- breadcrumb title bar (smallfont)
+---------------------------+
| [  Guards! Guards!      ] |  <-- slot 0 (above selected)
| [* Night Watch          ] |  <-- slot 1 (selected, highlighted)
| [  Mort                 ] |  <-- slot 2 (below selected)
+---------------------------+
```

**Key display decisions:**

1. **Title bar** shows breadcrumb via `menu_state.breadcrumb()`. At root level, shows "picoReader".

2. **Three slots** display a window of 3 items centered on the cursor. Each slot shows:
   - For **category nodes**: just the label (e.g., "Authors", "Fantasy")
   - For **book nodes**: the book title on line 1, author on line 2. The third label slot (series) only shows for the top two slots (matching current behavior where slot 2 is shorter).

3. **Selected slot** uses `MENU_SELECT_COLORS`, others use `MENU_OTHER_COLORS` (unchanged from current constants).

4. **Empty categories** (Settings stub, empty Recently Read): Display shows "Empty" in the center slot.

### Persistent menu group

Replace `Display._build_menu_group()` with a group that has the same structure but updates labels/colors in place. The group indices:

```
[0]  Background TileGrid
[1]  Title/breadcrumb label
[2]  Slot 0 rect
[3]  Slot 0 label line 1
[4]  Slot 0 label line 2
[5]  Slot 0 label line 3
[6]  Slot 1 rect
[7]  Slot 1 label line 1
[8]  Slot 1 label line 2
[9]  Slot 1 label line 3
[10] Slot 2 rect
[11] Slot 2 label line 1
[12] Slot 2 label line 2
[13] Slot 2 label line 3
```

Total: 14 elements. Built once in `_build_menu_group()`, then updated by `show_menu_screen()`.

### Updated `Display.show_menu_screen()` signature

```python
def show_menu_screen(self, menu_state, book_metadata):
    """Update menu group from MenuState and refresh display.

    Args:
        menu_state: MenuState instance with current position
        book_metadata: full metadata list for resolving book details
    """
    items, cursor = menu_state.visible_items()
    breadcrumb_text = menu_state.breadcrumb()

    # Update title bar
    self._menu_title_label.text = breadcrumb_text

    # Calculate 3-item window centered on cursor
    if not items:
        # Empty category
        self._clear_menu_slots()
        self._menu_slots[1][1][0].text = "(Empty)"
        self.display.show(self.menu_group)
        self.display.refresh()
        return

    total = len(items)
    if cursor <= 1:
        window_start = 0
        highlighted_slot = cursor
    else:
        window_start = cursor - 1
        highlighted_slot = 1

    for slot_idx in range(3):
        item_idx = window_start + slot_idx
        rect, slot_labels = self._menu_slots[slot_idx]
        is_selected = (slot_idx == highlighted_slot)
        txt_c, bg_c, bdr_c = MENU_SELECT_COLORS if is_selected else MENU_OTHER_COLORS
        rect.fill = bg_c
        rect.outline = bdr_c
        for lbl in slot_labels:
            lbl.color = txt_c

        if 0 <= item_idx < total:
            node = items[item_idx]
            if node.book_id is not None:
                # Book leaf -- show title + author
                meta = book_metadata[node.book_id]
                slot_labels[0].text = meta[0]  # title
                slot_labels[1].text = meta[1]  # author
                slot_labels[2].text = meta[2] if slot_idx < 2 else ''  # series
            else:
                # Category node -- show label only
                slot_labels[0].text = node.label
                child_count = len(node.children) if node.children else 0
                slot_labels[1].text = "({})".format(child_count)
                slot_labels[2].text = ''
        else:
            for lbl in slot_labels:
                lbl.text = ''

    self.display.show(self.menu_group)
    self.display.refresh()
```

### What gets removed from `display.py`

The old `show_menu_screen(self, book_metadata, selected, total)` method is replaced. The `_build_menu_group()` structure stays the same (same indices), but `show_menu_screen` now takes a `MenuState` instead of raw indices.

---

## 5. Jump Mode

### New mode constant

In `state.py`:

```python
class AppState:
    MODE_MENU = 0
    MODE_READER = 1
    MODE_DISPLAY = 2
    MODE_JUMP = 3         # New
```

### New state attributes

```python
# In AppState.__init__():
self.jump_pct = 0         # Current jump percentage (0-100)
```

### Jump mode entry

When DOWN is pressed while paused in reader mode, the system enters jump mode:

```python
def enter_jump_mode(state, book, disp):
    """DOWN pressed while paused in reader mode."""
    if state.playing:
        return
    # Calculate current position as percentage
    if book.book_len > 0:
        state.jump_pct = int(book.line_num * 100 / book.book_len)
    else:
        state.jump_pct = 0
    state.jump_pct = max(0, min(100, state.jump_pct))
    state.mode = AppState.MODE_JUMP
    disp.show_jump_screen(state.jump_pct)
```

### Jump mode display

New method on `Display`:

```python
def show_jump_screen(self, pct):
    """Show jump mode overlay: 'Jump: XX%' centered on reader screen."""
    # Reuse reader_group but update word label to show jump text
    self._word_label.text = "{:^30}".format("Jump: {}%".format(pct))
    self._wpm_label.text = "CENTER=go UP=cancel"
    self.display.show(self.reader_group)
    self.display.refresh()
```

**Design decision:** Reuse the reader group rather than building a new group. The word label area shows the jump percentage, and the WPM label area shows control hints. This keeps the jump mode lightweight with zero additional displayio objects.

### Jump mode controls

| Input | Action |
|-------|--------|
| Encoder CW | +5% (capped at 100) |
| Encoder CCW | -5% (capped at 0) |
| CENTER | Confirm jump, return to paused reader |
| UP | Cancel, return to paused reader |

### Jump mode handlers

```python
def jump_confirm(state, book, disp):
    """CENTER in jump mode: jump to position and return to reader."""
    target_line = int(book.book_len * state.jump_pct / 100)
    book.line_num = target_line
    book.word_idx = 0
    book._cache_start = -1
    book._cache = []
    book._update_chapter_index()
    book.save_place()
    state.mode = AppState.MODE_READER
    # Show first word at new position
    word = book.step_forward()
    if word:
        disp.show_word(clean_word(word))
    disp.show_wpm(state.wpm)
    disp.update_progress(book.line_num, book.book_len)
    disp.show_reader_screen()

def jump_cancel(state, book, disp):
    """UP in jump mode: cancel and return to reader."""
    state.mode = AppState.MODE_READER
    disp.show_reader_screen()

def jump_adjust_up(state, book, disp):
    """Encoder CW in jump mode: increase by 5%."""
    state.jump_pct = min(100, state.jump_pct + 5)
    disp.show_jump_screen(state.jump_pct)

def jump_adjust_down(state, book, disp):
    """Encoder CCW in jump mode: decrease by 5%."""
    state.jump_pct = max(0, state.jump_pct - 5)
    disp.show_jump_screen(state.jump_pct)
```

### Calculating target line from percentage

The `total_lines` for a book is `book.book_len` (derived from wordcount in the filename, which approximates line count). The target line is:

```python
target_line = int(book.book_len * pct / 100)
```

**Known imprecision:** `book_len` comes from the filename wordcount, which is a word count not a line count. The percentage is therefore approximate. This is acceptable for a "jump to roughly this part of the book" feature. Exact line counts would require scanning the file at load time, which Phase 2 can skip.

### Verification

Unit tests in `tests/unit/test_state.py`:
- `jump_pct` defaults to 0
- Jump target calculation: 50% of 1000 lines = line 500
- Jump target at 0% = line 0
- Jump target at 100% = last line
- `jump_pct` clamped to [0, 100] range

---

## 6. Updated Input Handler Dispatch Tables

### Reader mode changes

Current:
```python
(MODE_READER, BTN_LEFT):  goto_display,   # paused only
(MODE_READER, BTN_RIGHT): goto_display,   # paused only
```

New:
```python
(MODE_READER, BTN_LEFT):  prev_chapter,   # paused only
(MODE_READER, BTN_RIGHT): next_chapter,   # paused only
(MODE_READER, BTN_DOWN):  enter_jump_mode, # paused only
```

### Display mode removal

The `MODE_DISPLAY` mode (theme/brightness) is removed from the reader controls. Theme cycling and brightness move to the Settings menu (Phase 3/5 stub). For Phase 2, the Display mode dispatch entries are removed entirely. The handlers `goto_display`, `goto_reader_toggle`, `cycle_theme_fwd`, `cycle_theme_back`, `brightness_up`, `brightness_down` remain as dead code for now (to be moved into Settings menu handlers in Phase 3).

### New jump mode entries

```python
(MODE_JUMP, BTN_CENTER): jump_confirm,
(MODE_JUMP, BTN_UP):     jump_cancel,

# Encoder
(MODE_JUMP, 1):  jump_adjust_up,
(MODE_JUMP, -1): jump_adjust_down,
```

### Chapter navigation handlers

```python
def prev_chapter(state, book, disp):
    """LEFT when paused: jump to previous chapter."""
    if state.playing:
        return
    title = book.jump_to_chapter(-1)
    if title is None:
        return  # No-op: no chapters or at first chapter
    book.save_place()
    # Flash chapter title briefly
    disp.show_word(title[:17])  # Truncate to fit display
    disp.refresh()
    # The next word display in the reader loop will overwrite this

def next_chapter(state, book, disp):
    """RIGHT when paused: jump to next chapter."""
    if state.playing:
        return
    title = book.jump_to_chapter(1)
    if title is None:
        return
    book.save_place()
    disp.show_word(title[:17])
    disp.refresh()
```

**Chapter title flash:** The chapter title is displayed immediately in the word label. It remains visible until the user presses play (which starts displaying words from the new position) or steps with the encoder. No timer-based flash needed -- the natural flow of user interaction handles it.

### Full updated dispatch tables

```python
BUTTON_HANDLERS = {
    # Reader mode
    (AppState.MODE_READER, BTN_CENTER): toggle_play,
    (AppState.MODE_READER, BTN_UP):     goto_menu,
    (AppState.MODE_READER, BTN_LEFT):   prev_chapter,
    (AppState.MODE_READER, BTN_RIGHT):  next_chapter,
    (AppState.MODE_READER, BTN_DOWN):   enter_jump_mode,
    # Menu mode
    (AppState.MODE_MENU, BTN_CENTER): menu_select,
    (AppState.MODE_MENU, BTN_UP):     menu_back,
    # Jump mode
    (AppState.MODE_JUMP, BTN_CENTER): jump_confirm,
    (AppState.MODE_JUMP, BTN_UP):     jump_cancel,
}

ENCODER_HANDLERS = {
    (AppState.MODE_READER, 1):  wpm_up_or_step_fwd,
    (AppState.MODE_READER, -1): wpm_down_or_step_back,
    (AppState.MODE_MENU, 1):    menu_scroll_down,
    (AppState.MODE_MENU, -1):   menu_scroll_up,
    (AppState.MODE_JUMP, 1):    jump_adjust_up,
    (AppState.MODE_JUMP, -1):   jump_adjust_down,
}
```

### New menu handler functions

```python
def menu_select(state, book, disp):
    """CENTER in menu: drill into category or select book."""
    book_id = state.menu_state.select()
    if book_id is not None:
        # A book was selected -- start reading
        book.select_book(book_id)
        recent.update_recent(book.book)
        state.menu_state.refresh_recent(book.books, book.book_metadata, recent.load_recent())
        state.mode = AppState.MODE_READER
        state.playing = True
        state.finished = False
        book.save_backup()
        disp.apply_theme(THEMES[state.theme_index])
        disp.show_reader_screen()
    else:
        # Drilled into a category -- redraw menu
        disp.show_menu_screen(state.menu_state, book.book_metadata)

def menu_back(state, book, disp):
    """UP in menu: go back one level."""
    state.menu_state.back()
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def menu_scroll_down(state, book, disp):
    """Encoder CW in menu: scroll down."""
    state.menu_state.scroll(1)
    disp.show_menu_screen(state.menu_state, book.book_metadata)

def menu_scroll_up(state, book, disp):
    """Encoder CCW in menu: scroll up."""
    state.menu_state.scroll(-1)
    disp.show_menu_screen(state.menu_state, book.book_metadata)
```

---

## 7. Integration: AppState Holds MenuState

### Changes to `state.py`

`AppState` gains a `menu_state` attribute:

```python
class AppState:
    MODE_MENU = 0
    MODE_READER = 1
    MODE_DISPLAY = 2
    MODE_JUMP = 3

    def __init__(self):
        self.mode = self.MODE_MENU
        self.playing = False
        self.finished = False
        self.wpm = DEFAULT_WPM
        self.speed = 60.0 / DEFAULT_WPM
        self.brightness = DEFAULT_BRIGHTNESS
        self.theme_index = 0
        self.jump_pct = 0
        self.menu_state = None  # Set after menu tree is built in main()
```

### Changes to `main.py`

```python
def main():
    hw_display, backlight, spi, encoder = init_hardware()
    font = bitmap_font.load_font("fonts/Toronto_14.pcf")
    smallfont = bitmap_font.load_font("fonts/Toronto_9.pcf")

    books = [x for x in os.listdir("/sd/books/") if x.endswith('.txt')]
    if not books:
        # ... existing error display ...
        return

    metadata = [parse_book_filename(b) for b in books]
    lens = [m[3] for m in metadata]

    state = AppState()
    book = BookReader(books, metadata, lens)
    book.load_place()

    # Build menu tree
    recent_filenames = recent.load_recent()
    root = menu.build_menu_tree(books, metadata, recent_filenames)
    state.menu_state = menu.MenuState(root)

    disp = Display(hw_display, backlight, font, smallfont)
    disp.show_menu_screen(state.menu_state, metadata)

    with keypad.Keys(PIN_BUTTONS, value_when_pressed=False, pull=True) as keys:
        main_loop(state, book, disp, keys, encoder)
```

---

## 8. Simulator Compatibility

### What needs to change in `worker.ts`

1. **Module loading:** If Phase 1 introduces module loading (fetching `pico_reader/*.py` into `/app/pico_reader/`), Phase 2 adds `menu.py` and `recent.py` to that list. No structural change -- just two more files.

2. **Monkey-patched `_patched_main`:** The main function setup in worker.ts creates `state`, `book`, `disp` objects. It needs to be updated to also build the menu tree and set `state.menu_state`. The key additions:

   ```python
   # In _patched_main:
   from pico_reader import menu, recent

   recent_filenames = recent.load_recent()
   root = menu.build_menu_tree(books, metadata, recent_filenames)
   state.menu_state = menu.MenuState(root)

   disp.show_menu_screen(state.menu_state, metadata)
   ```

3. **State tracker update:** `_state_tracker.py` should include menu breadcrumb in state messages so the UI inspector can show current menu position:

   ```python
   if _app_state.menu_state:
       msg["menuBreadcrumb"] = _app_state.menu_state.breadcrumb()
       msg["menuCursor"] = _app_state.menu_state.cursor
       msg["menuDepth"] = len(_app_state.menu_state.path) - 1
   ```

4. **Save file mirroring:** `recent_order.txt` is under `/saves/` so the existing save-mirroring mechanism handles it. No change needed.

### What does NOT need to change

- The displayio shims (Group, TileGrid, Label, Rect, Palette) are unaffected -- the menu uses the same primitives.
- The canvas renderer in the main thread handles labels and rects the same way regardless of content.
- Chapter markers are pure text parsing -- no CircuitPython-specific APIs.
- Jump mode reuses the reader group -- no new display groups.

---

## 9. Unit Tests

All tests go in `tests/unit/`. They run with `pytest` on desktop Python, not CircuitPython.

### `tests/unit/test_menu.py`

```python
# Menu tree building
def test_build_menu_tree_has_root_children():
    """Root has 6 children: All Books, Recently Read, Authors, Series, Genres, Settings."""

def test_all_books_sorted_by_title():
    """All Books children are sorted alphabetically by title."""

def test_authors_grouped_correctly():
    """Each author node contains only that author's books."""

def test_series_sorted_by_filename():
    """Series books sorted by filename (encodes series number)."""

def test_genres_from_metadata():
    """Genre grouping respects parsed genre field."""

def test_uncategorized_genre_for_missing():
    """Books without [Genre] tag end up under 'Uncategorized'."""

def test_recently_read_preserves_order():
    """Recently Read children match the order from recent_filenames."""

def test_recently_read_skips_missing_files():
    """Files in recent_order.txt not present in books list are skipped."""

# Menu navigation
def test_scroll_wraps_forward():
    """Scrolling past last item wraps to first."""

def test_scroll_wraps_backward():
    """Scrolling before first item wraps to last."""

def test_select_category_drills_in():
    """Selecting a category node pushes it onto path stack."""

def test_select_book_returns_id():
    """Selecting a book leaf returns its book_id."""

def test_back_pops_level():
    """Back removes last entry from path stack."""

def test_back_at_root_returns_false():
    """Back at root level returns False, no-op."""

def test_breadcrumb_at_root():
    """Breadcrumb at root shows 'picoReader'."""

def test_breadcrumb_two_levels_deep():
    """Breadcrumb shows 'Authors > Pratchett' style."""

def test_breadcrumb_truncation():
    """Long breadcrumbs are truncated to fit display."""

def test_refresh_recent_updates_children():
    """refresh_recent replaces Recently Read node's children."""

# Empty states
def test_empty_series_when_no_books_have_series():
    """Series node has no children if no books have series tags."""

def test_select_on_empty_category():
    """Selecting into an empty category (Settings stub) shows empty."""
```

### `tests/unit/test_recent.py`

```python
def test_load_recent_no_file():
    """Returns empty list when file doesn't exist."""

def test_update_recent_adds_to_front():
    """New filename goes to position 0."""

def test_update_recent_deduplicates():
    """Existing filename is moved to front, not duplicated."""

def test_update_recent_caps_at_10():
    """List is truncated to 10 entries after 11th addition."""

def test_round_trip():
    """update_recent followed by load_recent returns correct order."""

def test_update_recent_preserves_others():
    """Adding a new entry preserves order of remaining entries."""
```

### `tests/unit/test_utils.py` (additions)

```python
def test_parse_genre_with_series():
    """'(Series 1) [Fantasy] Author - Title (100).txt' -> genre='Fantasy'."""

def test_parse_genre_without_series():
    """'[SciFi] Author - Title (100).txt' -> genre='SciFi'."""

def test_parse_no_genre_defaults_uncategorized():
    """'Author - Title (100).txt' -> genre='Uncategorized'."""

def test_parse_genre_and_series_together():
    """Both (Series) and [Genre] present, both extracted correctly."""
```

### `tests/unit/test_book_reader.py` (additions)

```python
def test_build_chapter_index_multiple_chapters():
    """File with 3 chapter markers returns 3 (line, title) tuples."""

def test_build_chapter_index_no_chapters():
    """File with no markers returns empty list."""

def test_jump_to_chapter_forward():
    """jump_to_chapter(1) moves to next chapter start."""

def test_jump_to_chapter_backward():
    """jump_to_chapter(-1) moves to previous chapter start."""

def test_jump_to_chapter_at_boundary():
    """jump_to_chapter(1) at last chapter returns None."""

def test_update_chapter_index_between_chapters():
    """chapter_index reflects the chapter that contains current line."""

def test_chapter_markers_not_treated_as_words():
    """step_forward() on a chapter marker line skips or includes it appropriately."""
```

### `tests/unit/test_state.py` (additions)

```python
def test_mode_jump_constant():
    """MODE_JUMP == 3."""

def test_jump_pct_default():
    """jump_pct defaults to 0."""
```

### Test fixtures needed in `conftest.py`

```python
@pytest.fixture
def sample_books_with_genres():
    """Returns a list of filenames with genre tags."""
    return [
        "(Earthsea 1) [Fantasy] Ursula K Le Guin - A Wizard Of Earthsea (1835).txt",
        "[Science Fiction] Andy Weir - The Martian (3500).txt",
        "Terry Pratchett - Guards Guards (9200).txt",
        "(Red Rising 1) [Science Fiction] Pierce Brown - Red Rising (5000).txt",
    ]

@pytest.fixture
def sample_metadata_with_genres(sample_books_with_genres):
    """Returns parsed metadata for genre-tagged books."""
    return [parse_book_filename(b) for b in sample_books_with_genres]

@pytest.fixture
def tmp_book_with_chapters(tmp_path):
    """Creates a temp book file with chapter markers."""
    content = (
        "Some intro text here\n"
        "---CHAPTER: The Beginning---\n"
        "Once upon a time there were some words\n"
        "More words on this line\n"
        "---CHAPTER: The Middle---\n"
        "The plot thickens with more words\n"
        "---CHAPTER: The End---\n"
        "And they all lived happily ever after\n"
    )
    book_file = tmp_path / "books" / "Test Author - Test Book (50).txt"
    book_file.parent.mkdir(parents=True)
    book_file.write_text(content)
    return tmp_path, book_file.name
```

---

## 10. File Change Summary

### New files

| File | Purpose |
|------|---------|
| `firmware/pico_reader/menu.py` | `MenuNode`, `MenuState`, `build_menu_tree()` |
| `firmware/pico_reader/recent.py` | `load_recent()`, `update_recent()` |
| `tests/unit/test_menu.py` | Menu tree building + navigation tests |
| `tests/unit/test_recent.py` | Recently read tracking tests |

### Modified files

| File | Changes |
|------|---------|
| `firmware/pico_reader/utils.py` | `parse_book_filename()` returns 5-tuple with genre |
| `firmware/pico_reader/state.py` | Add `MODE_JUMP = 3`, `jump_pct`, `menu_state` attributes |
| `firmware/pico_reader/book_reader.py` | Add `chapters`, `chapter_index`, `build_chapter_index()`, `jump_to_chapter()`, `_update_chapter_index()`. Call `build_chapter_index()` from `select_book()`. |
| `firmware/pico_reader/display.py` | Replace `show_menu_screen()` signature (takes `MenuState` instead of raw indices). Add `show_jump_screen()`. |
| `firmware/pico_reader/input_handlers.py` | New handlers: `prev_chapter`, `next_chapter`, `enter_jump_mode`, `jump_confirm`, `jump_cancel`, `jump_adjust_up`, `jump_adjust_down`, `menu_select`, `menu_back`, `menu_scroll_down`, `menu_scroll_up`. Updated dispatch tables. Remove Display mode entries. |
| `firmware/pico_reader/main.py` | Build menu tree in `main()`, set `state.menu_state`, pass to `show_menu_screen()`. |
| `firmware/pico_reader/__init__.py` | Add re-exports for `menu` and `recent` modules. |
| `tests/unit/test_utils.py` | Add genre parsing tests |
| `tests/unit/test_book_reader.py` | Add chapter index and chapter navigation tests |
| `tests/unit/test_state.py` | Add MODE_JUMP and jump_pct tests |
| `tests/conftest.py` | Add genre-tagged sample books, chapter-marked temp file fixtures |
| `simulator/src/worker.ts` | Update `_patched_main` to build menu tree. Add `menu.py` and `recent.py` to module fetch list. |
| `simulator/public/shims/_state_tracker.py` | Add menu breadcrumb/cursor/depth to state messages. |

---

## 11. Task Order

1. **Genre parsing** -- Update `parse_book_filename()` in `utils.py`, add tests
2. **Chapter index** -- Add chapter scanning and navigation to `book_reader.py`, add tests
3. **Recently read** -- Create `recent.py`, add tests
4. **Menu data model** -- Create `menu.py` with `MenuNode`, `MenuState`, `build_menu_tree()`, add tests
5. **Menu display** -- Update `display.py` with new `show_menu_screen()` signature
6. **Jump mode** -- Add `MODE_JUMP` to state, add `show_jump_screen()` to display, add tests
7. **Input handlers** -- Rewrite dispatch tables, add all new handler functions
8. **Main integration** -- Update `main.py` to wire everything together
9. **Simulator updates** -- Update `worker.ts` and `_state_tracker.py`
10. **Verify** -- Run all unit tests, manual simulator check, syntax check all `.py` files

---

## 12. What Phase 2 Does NOT Include

- **Skins** (Phase 3) -- Settings menu is a stub with empty children
- **ORP highlighting** (Phase 3) -- No word splitting for highlight
- **Epub converter** (Phase 4) -- Chapter markers are consumed, not generated
- **Smart pacing** (Phase 5) -- Flat WPM timing continues
- **Analytics** (Phase 5) -- No stats tracking
- **Animations** (Phase 5) -- No walker/particles/page turn
- **Integration tests** (Phase 6) -- Playwright-driven tests are separate
- **Font switching** -- Remains hardcoded to Toronto_14/9, settings key exists but isn't acted on
- **Brightness control** -- Removed from reader buttons, not yet wired into Settings menu. Workaround: brightness value persists from Phase 1 settings load.

Phase 2 establishes the navigation infrastructure that all menu-driven features (skins, settings, analytics display) will plug into.
