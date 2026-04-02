# Secret Games Submenu — Design Spec

## Context

picoReader is an RSVP eReader on a Raspberry Pi Pico (CircuitPython 8.0.5, 160x128 ST7735R LCD, 5-button keypad + rotary encoder). The user wants to add retro Palm Pilot-style games (Sub Hunt and Hardball/brick breaker) as a hidden easter egg accessible through a disguised menu entry in Settings.

**Constraints:**
- ~114KB estimated free RAM during normal operation
- 160x128 BGR display, `auto_refresh=False`, manual `display.refresh()` calls
- Synchronous main loop polling at ~100Hz (10ms sleep)
- `adafruit_display_shapes` available (Rect, Circle, Line, etc.)
- Games must not degrade reader performance or boot time (lazy import)

## Secret Access

A menu entry labeled **"System Info"** is added to the Settings submenu in `menu.py:163-176`. It uses `setting_key="games"` so the existing `menu_select` dispatch routes it to a game selection handler instead of cycling a setting value.

When selected, the app enters `MODE_GAME_SELECT`.

## Game Selection Screen

`MODE_GAME_SELECT` shows a simple centered list on a dark background:
- Sub Hunt
- Hardball

Rendered as a custom `show_game_select_screen(cursor)` method on `Display`, using the 9pt font and the same color scheme as the menu (highlight color for selected item, dim for others). Encoder scrolls, CENTER selects, UP returns to Settings.

## Game Module Architecture

### File structure

```
pico_reader/games/
    __init__.py       # GAME_LIST, launch_game() factory
    sub_hunt.py       # Sub Hunt game class
    hardball.py       # Hardball brick breaker game class
```

### Game interface

Each game module exports a single class:

```python
class GameName:
    def __init__(self, hw_display, smallfont):
        """Build displayio.Group, set initial state, show on display."""
    
    def handle_button(self, button):
        """Handle button press. Return 'quit' to exit game."""
    
    def handle_encoder(self, direction):
        """Handle encoder tick (+1 or -1)."""
    
    def tick(self, now):
        """Called every main loop iteration (~10ms).
        Update game state, move entities, check collisions.
        Return True if display.refresh() is needed."""
    
    def get_group(self):
        """Return the displayio.Group for this game."""
    
    def destroy(self):
        """Clean up displayio objects and release references."""
```

### Lazy import pattern

Games are only imported when selected. The launch flow:

```python
import gc
gc.collect()
if game_name == 'sub_hunt':
    from .games.sub_hunt import SubHuntGame
    state.active_game = SubHuntGame(disp.display, disp._smallfont)
elif game_name == 'hardball':
    from .games.hardball import HardballGame
    state.active_game = HardballGame(disp.display, disp._smallfont)
```

On exit: `state.active_game.destroy()`, `state.active_game = None`, `gc.collect()`.

## State Machine Changes

### `state.py`

```python
MODE_GAME_SELECT = 8
MODE_GAME = 9
```

In `AppState.__init__`:
```python
self.active_game = None
self.game_select_cursor = 0
```

### `input_handlers.py` — New dispatch entries

```python
# Game select mode
(AppState.MODE_GAME_SELECT, BTN_CENTER): game_select_confirm,
(AppState.MODE_GAME_SELECT, BTN_UP):     game_select_back,

# Game mode
(AppState.MODE_GAME, BTN_CENTER): game_button_center,
(AppState.MODE_GAME, BTN_UP):     game_button_up,
(AppState.MODE_GAME, BTN_LEFT):   game_button_left,
(AppState.MODE_GAME, BTN_RIGHT):  game_button_right,
(AppState.MODE_GAME, BTN_DOWN):   game_button_down,
```

Encoder handlers for both modes as well.

Game button handlers delegate to `state.active_game.handle_button(btn)` and check for `'quit'` return value.

### `main.py` — Game tick in main loop

After the word display timer block (line 121), before `time.sleep(0.01)`:

```python
if state.mode == AppState.MODE_GAME and state.active_game:
    if state.active_game.tick(now):
        disp.refresh()
```

### `menu.py` — Settings node addition

Add to Settings children (after "Stats"):
```python
MenuNode("System Info", setting_key="games"),
```

### `input_handlers.py` — Route "games" setting key

In `_cycle_setting()`, add handling for `key == 'games'`:
```python
elif key == 'games':
    state.mode = AppState.MODE_GAME_SELECT
    state.game_select_cursor = 0
    # Show game selection screen
```

## Sub Hunt — Game Design

### Concept
Top-down depth charge game. Player controls a ship on the ocean surface, dropping depth charges on submarines passing below at varying depths and speeds.

### Display layout (160x128)

```
[Score: 000    Hi: 000]     <- y=0-12, score + high score labels
~~~~~~~~~~SHIP~~~~~~~~~~    <- y=16, ocean surface line + ship rect
                            <- y=20-40, depth 1 (shallow, fast subs)
   <=SUB=>                  <- y=45-70, depth 2 (medium)
          *bomb*            <- falling depth charge
     <=SUB======>           <- y=75-110, depth 3 (deep, slow subs)
[________________________]  <- y=120-128, sea floor decoration
```

### Entities (all `Rect` objects)
- **Ship**: 12x4 rect on surface, moves with encoder
- **Submarines**: 16x6 to 24x6 rects at 3 depth bands, scroll horizontally
- **Depth charges**: 3x3 rects, fall vertically from ship position
- **Surface line**: Full-width 1px line at y=16
- **Score/lives labels**: `label.Label` with 9pt font

### Controls
- **Encoder**: Move ship left/right
- **CENTER**: Drop depth charge (max 2 active at once)
- **UP**: Pause overlay (CENTER to resume, UP again to quit)

### Mechanics
- Subs spawn from left or right edge at random intervals
- 3 depth bands with different speeds (shallow=fast, deep=slow)
- Depth charges fall at constant rate, explode on collision or reaching bottom
- Hit = score based on depth (deeper = more points, 10/20/30)
- Max 4-5 subs on screen at once to limit displayio objects
- Difficulty increases every 100 points: faster spawn rate, faster subs
- Pure score attack — no lives, play until you press UP to quit
- Game over screen shows final score vs. high score

### Pause behavior
- UP once = pause overlay (text label "PAUSED" centered, "CENTER=resume UP=quit" below)
- CENTER while paused = resume
- UP while paused = quit, show final score, then return to game select

### displayio budget: ~20 elements
1 background, 1 surface line, 1 ship, 5 subs max, 2 depth charges, 2 labels, ~5 decoration = ~17

## Hardball (Brick Breaker) — Game Design

### Concept
Classic breakout/brick breaker. Paddle at bottom, ball bounces to destroy brick grid above.

### Display layout (160x128)

```
[Score: 000    Ball: 3]     <- y=0-10, labels
[B][B][B][B][B][B][B][B]    <- y=14-22, brick row 1
[B][B][B][B][B][B][B][B]    <- y=24-32, brick row 2
[B][B][B][B][B][B][B][B]    <- y=34-42, brick row 3
[B][B][B][B][B][B][B][B]    <- y=44-52, brick row 4
                             <- open play area
                             <- ball bouncing
[=========PADDLE=========]  <- y=120-126, paddle
```

### Entities
- **Paddle**: 24x4 rect at y=122, moves with encoder
- **Ball**: 3x3 rect, moves with dx/dy velocity
- **Bricks**: 8 columns x 4 rows = 32 bricks, each 18x7 with 1px gap
  - Bricks use a single color per row (4 colors from current theme palette)
  - Destroyed bricks are removed from the displayio.Group
- **Labels**: Score and balls remaining

### Controls
- **Encoder**: Move paddle left/right
- **CENTER**: Launch ball from paddle (when ball is resting on paddle)
- **UP**: Pause overlay (CENTER to resume, UP again to quit)

### Mechanics
- Ball starts resting on paddle, CENTER launches at 45-degree angle
- Ball bounces off walls (left, right, top) and paddle
- Paddle hit position affects bounce angle (center = straight up, edges = wider angle)
- Ball speed increases slightly each level
- Brick contact: brick removed, ball reverses y-direction (simplified collision)
- Ball drops below paddle: lose a ball (3 total)
- All bricks cleared: next level (regenerate bricks, slightly faster ball)
- Game over when all balls lost — show score vs. high score

### Pause behavior
Same as Sub Hunt: UP = pause, CENTER = resume, UP again = quit to game select.

### displayio budget: ~38 elements
1 background, 1 paddle, 1 ball, 32 bricks, 2 labels = 37

### Color strategy
- Use BGR colors from the currently active theme palette where possible
- Brick rows use 4 distinct colors derived from the palette
- Ball and paddle use the text/highlight color

## High Scores

Each game persists its top score to `/sd/saves/game_<name>`:

```python
# Save
with open("saves/game_subhunt", 'w') as f:
    f.write(str(high_score))

# Load
try:
    with open("saves/game_subhunt", 'r') as f:
        high_score = int(f.read().strip())
except (OSError, ValueError):
    high_score = 0
```

Shown on game-over screen. New high score gets a brief flash/highlight.

## Files to Create

| File | Purpose |
|------|---------|
| `pico_reader/games/__init__.py` | Game registry and launch helper |
| `pico_reader/games/sub_hunt.py` | Sub Hunt game (~150-200 lines) |
| `pico_reader/games/hardball.py` | Hardball game (~200-250 lines) |

## Files to Modify

| File | Change |
|------|--------|
| `pico_reader/state.py` | Add `MODE_GAME_SELECT`, `MODE_GAME`, `active_game`, `game_select_cursor` |
| `pico_reader/menu.py` | Add "System Info" node to Settings children |
| `pico_reader/input_handlers.py` | Add game select/play handlers + dispatch table entries |
| `pico_reader/main.py` | Add game tick block in main loop |
| `pico_reader/display.py` | Add `show_game_select_screen()` method |

## Verification

1. **Syntax check**: `python3 -c "import py_compile; py_compile.compile('code.py', doraise=True)"` for all modified files
2. **Menu navigation**: Navigate to Settings > System Info, verify game list appears
3. **Sub Hunt**: Select Sub Hunt, verify ship moves with encoder, CENTER drops charges, subs scroll, scoring works, UP quits back to game select
4. **Hardball**: Select Hardball, verify paddle moves, ball launches and bounces, bricks break, score increments, ball loss works, UP quits
5. **High scores**: Play game, score > 0, quit, re-enter game, verify high score persisted
6. **Return to reading**: Exit games, select a book, verify reader mode works normally (no leaked displayio objects or RAM issues)
7. **Memory**: Check that `gc.mem_free()` after exiting a game is roughly the same as before entering (no major leaks)
