import time
import os
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT,
                         BTN_CENTER, BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT)

# BGR colors
_BG = 0x1a1a1a
_TEXT = 0xc8c8c8
_BRIGHT = 0xe7e7e7
_HIGHLIGHT = 0x005500
_TITLE_BG = 0x2a2a2a
_LOCKED = 0x606060
_INV_BG = 0x282828
_FOCUS_ARROW = 0x00cc66   # green in BGR

# Layout
_TITLE_H = 12
_DESC_Y = _TITLE_H + 2
_DESC_LINES = 5
_LINE_H = 11
_CHOICE_Y = _DESC_Y + _DESC_LINES * _LINE_H + 4
_MAX_CHOICES_VISIBLE = 4
_CHARS_PER_LINE = 25  # approximate for 9pt font at 160px


# =========================================================================
# Episode selection screen (launched from game select)
# =========================================================================
class AdventureSelect:
    """Picker for .adv files in /sd/adventures/. Acts as a 'game' in the
    game framework, forwarding to AdventureEngine on selection."""

    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._cursor = 0
        self._engine = None  # when set, we delegate everything

        # Background
        bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        pal = displayio.Palette(1)
        pal[0] = _BG
        self._group.append(displayio.TileGrid(bmp, pixel_shader=pal))

        # Title
        tl = label.Label(smallfont, text="Adventures", color=_BRIGHT,
                         base_alignment=True)
        tl.anchor_point = (0.5, 0.0)
        tl.anchored_position = (80, 2)
        self._group.append(tl)

        # Scan episodes
        self._episodes = []  # list of (title, filename)
        self._scan_episodes()

        # Build list labels (up to 8 visible)
        self._labels = []
        self._rects = []
        for i in range(min(8, max(1, len(self._episodes)))):
            y = 18 + i * 13
            r = Rect(2, y - 1, DISPLAY_WIDTH - 4, 13, fill=_BG)
            self._group.append(r)
            self._rects.append(r)
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (6, y)
            self._group.append(lb)
            self._labels.append(lb)

        self._hint = label.Label(smallfont, text="", color=_LOCKED,
                                 base_alignment=True)
        self._hint.anchor_point = (0.5, 1.0)
        self._hint.anchored_position = (80, DISPLAY_HEIGHT - 2)
        self._group.append(self._hint)

        if not self._episodes:
            self._hint.text = "No .adv in /sd/adventures/"
        else:
            self._hint.text = "C=play  U=back"
            self._refresh_list()

    def _scan_episodes(self):
        try:
            files = os.listdir("/sd/adventures")
        except OSError:
            return
        for fn in sorted(files):
            if not fn.endswith(".adv"):
                continue
            title = fn[:-4].replace("_", " ")
            # Try to read @TITLE from header
            try:
                with open("/sd/adventures/" + fn, "r") as f:
                    for _ in range(10):
                        line = f.readline()
                        if not line:
                            break
                        if line.startswith("@TITLE "):
                            title = line[7:].strip()
                            break
            except OSError:
                pass
            # Check for save
            has_save = False
            try:
                os.stat("saves/adv_" + fn[:-4])
                has_save = True
            except OSError:
                pass
            suffix = " [SAVED]" if has_save else ""
            self._episodes.append((title + suffix, fn))

    def _refresh_list(self):
        n = len(self._episodes)
        for i, lb in enumerate(self._labels):
            idx = i  # simple offset if we add scroll later
            if idx < n:
                lb.text = self._episodes[idx][0][:22]
                lb.color = _BRIGHT if idx == self._cursor else _TEXT
            else:
                lb.text = ""
            self._rects[i].fill = _HIGHLIGHT if idx == self._cursor else _BG

    def get_group(self):
        if self._engine:
            return self._engine.get_group()
        return self._group

    def handle_button(self, button):
        if self._engine:
            result = self._engine.handle_button(button)
            if result == 'quit':
                self._engine.destroy()
                self._engine = None
                self._display.show(self._group)
                return None
            return result
        if button == BTN_UP:
            return 'quit'
        if button == BTN_CENTER and self._episodes:
            _, fn = self._episodes[self._cursor]
            path = "/sd/adventures/" + fn
            self._engine = AdventureEngine(self._display, self._font, path,
                                           fn[:-4])
            self._display.show(self._engine.get_group())
        return None

    def handle_encoder(self, direction):
        if self._engine:
            return self._engine.handle_encoder(direction)
        if not self._episodes:
            return None
        self._cursor = (self._cursor + direction) % len(self._episodes)
        self._refresh_list()
        return None

    def tick(self, now):
        if self._engine:
            return self._engine.tick(now)
        return False

    def destroy(self):
        if self._engine:
            self._engine.destroy()
            self._engine = None
        while len(self._group) > 0:
            self._group.pop()
        self._group = None


# =========================================================================
# Adventure engine
# =========================================================================
def _word_wrap(text, max_chars):
    """Split text into lines of at most max_chars characters."""
    lines = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        words = raw.split()
        cur = ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > max_chars:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w) if cur else w
        if cur:
            lines.append(cur)
    return lines


class AdventureEngine:
    """Plays a single .adv episode."""

    def __init__(self, hw_display, smallfont, filepath, save_name):
        self._display = hw_display
        self._font = smallfont
        self._filepath = filepath
        self._save_name = save_name
        self._group = displayio.Group()

        # State
        self._inventory = []
        self._flags = set()
        self._score = 0
        self._room_id = None
        self._title = ""
        self._start_room = ""

        # Room data (current only)
        self._desc_lines = []       # word-wrapped description
        self._choices = []          # list of (text, target_room, conditions_dict)
        self._items_here = []       # list of (id, name, examine)
        self._on_enter_actions = [] # list of (action, value)
        self._gameover_text = None
        self._win_text = None

        # Index: room_id -> byte offset in file
        self._room_index = {}

        # UI state
        self._desc_scroll = 0
        self._choice_cursor = 0
        self._focus = 'choices'  # 'choices' or 'desc'
        self._showing_inventory = False
        self._inv_cursor = 0
        self._ended = False

        # Build index
        self._build_index()

        # Background
        bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        pal = displayio.Palette(1)
        pal[0] = _BG
        self._group.append(displayio.TileGrid(bmp, pixel_shader=pal))

        # Title bar background
        self._group.append(Rect(0, 0, DISPLAY_WIDTH, _TITLE_H, fill=_TITLE_BG))

        # Title label
        self._title_lbl = label.Label(smallfont, text=self._title[:20],
                                      color=_BRIGHT, base_alignment=True)
        self._title_lbl.anchor_point = (0.0, 0.0)
        self._title_lbl.anchored_position = (3, 2)
        self._group.append(self._title_lbl)

        # Inventory indicator
        self._inv_ind = label.Label(smallfont, text="", color=_LOCKED,
                                    base_alignment=True)
        self._inv_ind.anchor_point = (1.0, 0.0)
        self._inv_ind.anchored_position = (DISPLAY_WIDTH - 3, 2)
        self._group.append(self._inv_ind)

        # Description labels (fixed lines)
        self._desc_lbls = []
        for i in range(_DESC_LINES):
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (4, _DESC_Y + i * _LINE_H)
            self._group.append(lb)
            self._desc_lbls.append(lb)

        # Separator line
        sep_y = _CHOICE_Y - 3
        self._group.append(Rect(4, sep_y, DISPLAY_WIDTH - 8, 1, fill=_TITLE_BG))

        # Focus indicator
        self._focus_lbl = label.Label(smallfont, text="", color=_FOCUS_ARROW,
                                      base_alignment=True)
        self._focus_lbl.anchor_point = (1.0, 0.0)
        self._focus_lbl.anchored_position = (DISPLAY_WIDTH - 2, _DESC_Y)
        self._group.append(self._focus_lbl)

        # Choice labels + highlight rects
        self._choice_rects = []
        self._choice_lbls = []
        for i in range(_MAX_CHOICES_VISIBLE):
            y = _CHOICE_Y + i * _LINE_H
            r = Rect(2, y - 1, DISPLAY_WIDTH - 4, _LINE_H, fill=_BG)
            self._group.append(r)
            self._choice_rects.append(r)
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (6, y)
            self._group.append(lb)
            self._choice_lbls.append(lb)

        # Inventory overlay: background rect (starts off-screen)
        self._inv_bg = Rect(4, -DISPLAY_HEIGHT, DISPLAY_WIDTH - 8,
                            DISPLAY_HEIGHT - 24, fill=_INV_BG)
        self._group.append(self._inv_bg)

        # Inventory overlay labels (start with empty text)
        self._inv_lbls = []
        for i in range(7):
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (8, 16 + i * _LINE_H)
            self._group.append(lb)
            self._inv_lbls.append(lb)

        # Load save or start fresh
        self._load_save()
        if self._room_id and self._room_id in self._room_index:
            self._enter_room(self._room_id)
        else:
            self._enter_room(self._start_room)

    def get_group(self):
        return self._group

    # -- File parsing --------------------------------------------------

    def _build_index(self):
        """Scan file to build room_id -> byte offset index and read header."""
        with open(self._filepath, "r") as f:
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if line.startswith("@TITLE "):
                    self._title = line[7:]
                elif line.startswith("@START "):
                    self._start_room = line[7:]
                elif line.startswith("@ROOM "):
                    room_id = line[6:]
                    self._room_index[room_id] = pos

    def _load_room(self, room_id):
        """Parse a single room from the file. Returns (desc, choices, items,
        on_enter, gameover_text, win_text, score_delta)."""
        offset = self._room_index.get(room_id)
        if offset is None:
            return ["Room not found: " + room_id], [], [], [], None, None, 0

        desc_parts = []
        choices = []
        items = []
        on_enter = []
        gameover = None
        win = None
        score_delta = 0
        in_desc = False
        skip_block = False  # for @IF blocks

        with open(self._filepath, "r") as f:
            f.seek(offset)
            f.readline()  # skip @ROOM line
            while True:
                line = f.readline()
                if not line:
                    break
                raw = line.strip()
                if raw.startswith("@ROOM "):
                    break  # next room

                # @IF / @ENDIF handling
                if raw.startswith("@IF "):
                    flag = raw[4:]
                    negate = flag.startswith("!")
                    if negate:
                        flag = flag[1:]
                    has_flag = flag in self._flags
                    skip_block = (has_flag if negate else not has_flag)
                    continue
                if raw == "@ENDIF":
                    skip_block = False
                    continue
                if skip_block:
                    continue

                if raw == "@DESC":
                    in_desc = True
                    continue
                if raw == "@ENDDESC":
                    in_desc = False
                    continue
                if in_desc:
                    desc_parts.append(raw)
                    continue

                if raw.startswith("@CHOICE "):
                    choice = self._parse_choice(raw[8:])
                    if choice:
                        choices.append(choice)
                elif raw.startswith("@ITEM "):
                    item = self._parse_item(raw[6:])
                    if item:
                        items.append(item)
                elif raw.startswith("@ON_ENTER "):
                    rest = raw[10:]
                    if rest.startswith("@SET "):
                        on_enter.append(("set", rest[5:]))
                    elif rest.startswith("@GIVE "):
                        on_enter.append(("give", rest[6:]))
                elif raw.startswith("@GAMEOVER "):
                    gameover = raw[10:].strip('"')
                elif raw.startswith("@WIN "):
                    win = raw[5:].strip('"').replace("{score}",
                                                     str(self._score))
                elif raw.startswith("@SCORE "):
                    try:
                        score_delta = int(raw[7:])
                    except ValueError:
                        pass

        return desc_parts, choices, items, on_enter, gameover, win, score_delta

    def _parse_choice(self, raw):
        """Parse: "text" -> target [@NEED x] [@PICKUP x] [@USE x] [@SET x]"""
        # Extract quoted text
        if not raw.startswith('"'):
            return None
        end_q = raw.find('"', 1)
        if end_q < 0:
            return None
        text = raw[1:end_q]
        rest = raw[end_q + 1:].strip()

        # Extract target: -> room_id
        arrow_idx = rest.find("->")
        if arrow_idx < 0:
            return None
        after_arrow = rest[arrow_idx + 2:].strip()
        parts = after_arrow.split()
        target = parts[0] if parts else ""

        # Parse modifiers
        need = None
        pickup = None
        use = None
        set_flag = None
        i = 1
        while i < len(parts):
            if parts[i] == "@NEED" and i + 1 < len(parts):
                need = parts[i + 1]
                i += 2
            elif parts[i] == "@PICKUP" and i + 1 < len(parts):
                pickup = parts[i + 1]
                i += 2
            elif parts[i] == "@USE" and i + 1 < len(parts):
                use = parts[i + 1]
                i += 2
            elif parts[i] == "@SET" and i + 1 < len(parts):
                set_flag = parts[i + 1]
                i += 2
            else:
                i += 1

        return {
            "text": text,
            "target": target,
            "need": need,
            "pickup": pickup,
            "use": use,
            "set": set_flag,
        }

    def _parse_item(self, raw):
        """Parse: id "name" "examine text" """
        parts = raw.split('"')
        if len(parts) < 4:
            return None
        item_id = parts[0].strip()
        name = parts[1]
        examine = parts[3] if len(parts) > 3 else ""
        return (item_id, name, examine)

    # -- Room entry ----------------------------------------------------

    def _enter_room(self, room_id):
        self._room_id = room_id
        desc, choices, items, on_enter, gameover, win, score_delta = \
            self._load_room(room_id)

        # Apply on_enter actions
        for action, value in on_enter:
            if action == "set":
                self._flags.add(value)
            elif action == "give":
                if value not in self._inventory:
                    self._inventory.append(value)

        # Score
        if score_delta:
            self._score += score_delta

        # Check endings
        if gameover:
            self._gameover_text = gameover
        if win:
            self._win_text = win

        # Filter choices by conditions
        visible = []
        for c in choices:
            if not self._check_need(c["need"]):
                continue
            # Hide pickup choices for items already held
            if c["pickup"] and c["pickup"] in self._inventory:
                continue
            visible.append(c)

        # Also add item pickup choices from @ITEM directives
        for item_id, name, _ in items:
            if item_id not in self._inventory:
                visible.append({
                    "text": "Take " + name,
                    "target": room_id,
                    "need": None,
                    "pickup": item_id,
                    "use": None,
                    "set": None,
                })

        self._desc_lines = _word_wrap("\n".join(desc), _CHARS_PER_LINE)
        self._choices = visible
        self._desc_scroll = 0
        self._choice_cursor = 0
        self._focus = 'choices'

        self._render()
        self._save_state()

    def _check_need(self, need):
        if need is None:
            return True
        if need.startswith("!"):
            return need[1:] not in self._flags and need[1:] not in self._inventory
        return need in self._flags or need in self._inventory

    # -- Rendering -----------------------------------------------------

    def _render(self):
        # Title + inventory indicator
        self._inv_ind.text = "[{}]".format(len(self._inventory)) if self._inventory else ""

        # Handle endings
        if self._gameover_text:
            self._render_ending("GAME OVER", self._gameover_text)
            return
        if self._win_text:
            self._render_ending("YOU WIN!", self._win_text)
            return

        # Description
        for i, lb in enumerate(self._desc_lbls):
            idx = self._desc_scroll + i
            if idx < len(self._desc_lines):
                lb.text = self._desc_lines[idx]
            else:
                lb.text = ""

        # Focus indicator
        if self._focus == 'desc' and len(self._desc_lines) > _DESC_LINES:
            scroll_pct = self._desc_scroll / max(1, len(self._desc_lines) - _DESC_LINES)
            self._focus_lbl.text = "^" if scroll_pct < 1 else ""
        else:
            self._focus_lbl.text = ""

        # Choices
        for i in range(_MAX_CHOICES_VISIBLE):
            idx = i  # could add choice scrolling if >4 choices
            if idx < len(self._choices):
                c = self._choices[idx]
                prefix = "> " if idx == self._choice_cursor and self._focus == 'choices' else "  "
                self._choice_lbls[i].text = (prefix + c["text"])[:_CHARS_PER_LINE]
                self._choice_lbls[i].color = _BRIGHT if idx == self._choice_cursor else _TEXT
                self._choice_rects[i].fill = _HIGHLIGHT if idx == self._choice_cursor else _BG
            else:
                self._choice_lbls[i].text = ""
                self._choice_rects[i].fill = _BG

    def _render_ending(self, title, text):
        lines = _word_wrap(text, _CHARS_PER_LINE)
        for i, lb in enumerate(self._desc_lbls):
            if i == 0:
                lb.text = title
                lb.color = _BRIGHT
            elif i - 1 < len(lines):
                lb.text = lines[i - 1]
                lb.color = _TEXT
            else:
                lb.text = ""
        if self._score:
            self._choice_lbls[0].text = "  Score: {}".format(self._score)
        else:
            self._choice_lbls[0].text = ""
        self._choice_lbls[1].text = "  Press any button"
        for i in range(2, _MAX_CHOICES_VISIBLE):
            self._choice_lbls[i].text = ""
        for r in self._choice_rects:
            r.fill = _BG
        self._ended = True

    def _show_inventory(self):
        self._showing_inventory = True
        self._inv_cursor = 0
        self._inv_bg.y = 12  # move on-screen
        self._render_inventory()

    def _hide_inventory(self):
        self._showing_inventory = False
        self._inv_bg.y = -DISPLAY_HEIGHT  # move off-screen
        for lb in self._inv_lbls:
            lb.text = ""

    def _render_inventory(self):
        self._inv_lbls[0].text = "=== Inventory ==="
        self._inv_lbls[0].color = _BRIGHT
        if not self._inventory:
            self._inv_lbls[1].text = "(empty)"
            self._inv_lbls[1].color = _LOCKED
            for i in range(2, len(self._inv_lbls)):
                self._inv_lbls[i].text = ""
            return
        for i in range(1, len(self._inv_lbls) - 1):
            idx = i - 1
            lb = self._inv_lbls[i]
            if idx < len(self._inventory):
                prefix = "> " if idx == self._inv_cursor else "  "
                lb.text = prefix + self._inventory[idx].replace("_", " ")
                lb.color = _BRIGHT if idx == self._inv_cursor else _TEXT
            else:
                lb.text = ""
        # Score at bottom
        last = self._inv_lbls[-1]
        last.text = "Score: {}".format(self._score)
        last.color = _LOCKED

    # -- Input ---------------------------------------------------------

    def handle_button(self, button):
        if self._ended:
            return 'quit'

        if self._showing_inventory:
            if button == BTN_UP:
                self._hide_inventory()
                return None
            if button == BTN_DOWN and self._inventory:
                # Examine item
                item_id = self._inventory[self._inv_cursor]
                self._examine_item(item_id)
                return None
            return None

        if button == BTN_UP:
            self._show_inventory()
            return None

        if button == BTN_DOWN:
            # Toggle focus
            if len(self._desc_lines) > _DESC_LINES:
                self._focus = 'desc' if self._focus == 'choices' else 'choices'
                self._render()
            return None

        if button == BTN_CENTER:
            if self._choices:
                self._select_choice(self._choice_cursor)
            return None

        if button == BTN_LEFT:
            # Quit back to adventure select (save is already auto-saved)
            return 'quit'

        return None

    def handle_encoder(self, direction):
        if self._ended:
            return None

        if self._showing_inventory:
            if self._inventory:
                self._inv_cursor = (self._inv_cursor + direction) % len(self._inventory)
                self._render_inventory()
            return None

        if self._focus == 'desc':
            max_scroll = max(0, len(self._desc_lines) - _DESC_LINES)
            self._desc_scroll = max(0, min(max_scroll,
                                           self._desc_scroll + direction))
            self._render()
        else:
            if self._choices:
                self._choice_cursor = ((self._choice_cursor + direction) %
                                       len(self._choices))
                self._render()
        return None

    def tick(self, now):
        return False  # event-driven, no physics loop

    # -- Choice execution ----------------------------------------------

    def _select_choice(self, idx):
        if idx >= len(self._choices):
            return
        c = self._choices[idx]

        # Use item
        if c["use"] and c["use"] in self._inventory:
            self._inventory.remove(c["use"])

        # Pickup item
        if c["pickup"] and c["pickup"] not in self._inventory:
            self._inventory.append(c["pickup"])

        # Set flag
        if c["set"]:
            self._flags.add(c["set"])

        # Navigate
        self._enter_room(c["target"])

    def _examine_item(self, item_id):
        """Show item description in a temporary overlay."""
        # Find item description from current room or show generic
        _, _, items, _, _, _, _ = self._load_room(self._room_id)
        desc = "A " + item_id.replace("_", " ") + "."
        for iid, _, examine in items:
            if iid == item_id:
                desc = examine
                break
        # Show in inventory overlay
        self._inv_lbls[0].text = item_id.replace("_", " ")
        self._inv_lbls[0].color = _BRIGHT
        lines = _word_wrap(desc, _CHARS_PER_LINE - 2)
        for i in range(1, len(self._inv_lbls)):
            if i - 1 < len(lines):
                self._inv_lbls[i].text = lines[i - 1]
                self._inv_lbls[i].color = _TEXT
                self._inv_lbls[i].hidden = False
            else:
                self._inv_lbls[i].text = ""

    # -- Save / Load ---------------------------------------------------

    def _save_state(self):
        try:
            with open("saves/adv_" + self._save_name, "w") as f:
                f.write("room={}\n".format(self._room_id))
                f.write("inventory={}\n".format(",".join(self._inventory)))
                f.write("flags={}\n".format(",".join(sorted(self._flags))))
                f.write("score={}\n".format(self._score))
        except OSError:
            pass

    def _load_save(self):
        try:
            with open("saves/adv_" + self._save_name, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("room="):
                        self._room_id = line[5:]
                    elif line.startswith("inventory="):
                        val = line[10:]
                        self._inventory = [x for x in val.split(",") if x]
                    elif line.startswith("flags="):
                        val = line[6:]
                        self._flags = set(x for x in val.split(",") if x)
                    elif line.startswith("score="):
                        try:
                            self._score = int(line[6:])
                        except ValueError:
                            pass
        except OSError:
            pass  # no save file, fresh start

    # -- Cleanup -------------------------------------------------------

    def destroy(self):
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
