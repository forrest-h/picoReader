# Retro Games Collection — Design Spec

**Date**: 2026-04-02
**Status**: Draft

## Context

picoReader already has two hidden Palm Pilot–inspired games (Sub Hunt, Hardball) accessed via Settings → System Info. The hardware — 160×128 ST7735R LCD, 5-button keypad, rotary encoder, SD card — is capable of running a broader retro arcade collection. The goal is to add 5 new arcade games plus a text adventure engine, recreating the feel of classic PDA gaming with high fidelity to the originals. Adventure episodes live on the SD card, mirroring how books are stored.

## Scope

**New arcade games (5):**
1. Snake
2. Missile Command
3. Asteroids
4. Space Invaders
5. Lunar Lander

**Text adventure engine (1 engine + SD card episodes):**
- Engine on Pico flash (~15–20K)
- Episodes as `.adv` files on SD card (`/sd/adventures/`)
- Choice-based UI adapted from classic interactive fiction

**Existing games unchanged:** Sub Hunt, Hardball

**Total game entries in game select:** 8 (Sub Hunt, Hardball, Snake, Missile Command, Asteroids, Space Invaders, Lunar Lander, Adventures)

## Hardware Constraints

| Resource | Limit | Notes |
|----------|-------|-------|
| Display | 160×128 BGR, manual refresh | `auto_refresh=False` |
| RAM | ~114KB free | One game loaded at a time (lazy import) |
| Flash (Pico) | ~592K available | Budget ~80–100K for new games, leave 490K+ for future |
| SD Card | Effectively unlimited | Adventure episodes + saves |
| Inputs | 5 buttons + rotary encoder | CENTER, UP, DOWN, LEFT, RIGHT + encoder CW/CCW |
| Tick rate | ~100Hz (10ms polling) | Sufficient for all arcade games |
| displayio objects | ~40 practical max per game | Hardball uses ~35 and works fine |

## Game Designs

### 1. Snake

**Rendering:** `Bitmap` + single `TileGrid`. Grid of 26×21 cells (6px each). Avoids displayio object explosion — a long snake would need 50+ Rects otherwise.

**Update strategy:** O(1) per frame. Paint new head cell, erase old tail cell on the bitmap. Only score label and border are separate displayio objects.

**Controls:**
| Input | Action |
|-------|--------|
| Encoder CW | Turn snake clockwise (relative to current heading) |
| Encoder CCW | Turn snake counter-clockwise |
| CENTER | Pause/resume |
| UP | Pause → quit confirmation |

**Gameplay:**
- Food appears at random empty cell
- Snake grows by 1 segment on eating food
- Speed increases as snake grows (tick interval shortens from ~200ms down to ~80ms)
- Game over: hit self or wall
- Score: 10 points per food eaten

**High score:** Saved to `/sd/saves/game_snake`

**Estimated size:** ~8–10K on flash

---

### 2. Missile Command

**Rendering:** displayio `Rect`, `Line`, `Circle` primitives. Moderate object count (~25–30): 3 cities + 3 batteries + crosshair + incoming missiles + explosions + HUD labels.

**Controls:**
| Input | Action |
|-------|--------|
| D-pad (UP/DOWN/LEFT/RIGHT) | Move crosshair |
| CENTER | Fire counter-missile from selected battery |
| Encoder | Cycle active battery (left/center/right) |

**Layout:**
```
┌────────────────────────────────┐
│          ╲    ╱                │ ← Incoming missiles (Lines
│           ╲  ╱   ╲             │    drawn incrementally)
│            ╳      ╲            │
│           ╱ ╲      ╲           │
│     +                          │ ← Crosshair (2 short Lines)
│                                │
│  ▓▓  ▲  ▓▓▓  ▲  ▓▓  ▲  ▓▓   │ ← Cities (▓) + Batteries (▲)
│ [Score: 1250]    [Missiles: 8] │
└────────────────────────────────┘
```

**Gameplay:**
- Missiles fall from random sky positions toward cities/batteries
- Counter-missile travels from battery to crosshair position, then explodes
- Explosion: Circle that expands over ~300ms then contracts — any incoming missile within radius is destroyed
- Battery ammo is limited per wave (refills between waves)
- Wave ends when all incoming missiles destroyed or landed
- Bonus points for surviving cities between waves
- Destroyed city = gone for the rest of the game

**Difficulty progression:**
| Wave | Missiles | Speed | Special |
|------|----------|-------|---------|
| 1–3 | 5–8 | Slow | — |
| 4–6 | 8–12 | Medium | — |
| 7–9 | 12–16 | Fast | Splitting warheads (1→2 at random altitude) |
| 10+ | 16+ | Very fast | More splitters, fewer battery reloads |

**Game over:** All 3 cities destroyed.

**Scoring:** 25 pts per intercepted missile, 100 pts per surviving city per wave.

**High score:** Saved to `/sd/saves/game_missile_cmd`

**Estimated size:** ~12–15K on flash

---

### 3. Asteroids

**Rendering:** `Bitmap` + single `TileGrid` for the full play area. Required because the ship rotates freely and `Line` endpoints can't be updated after creation. Ship triangle, asteroid circles, and bullet dots drawn as pixels using `math.sin`/`math.cos`.

**Controls:**
| Input | Action |
|-------|--------|
| Encoder | Rotate ship (smooth analog rotation) |
| UP | Thrust in facing direction |
| CENTER | Fire bullet |
| DOWN | Hyperspace (random teleport, small chance of death) |

**Ship rendering:** 3 vertices calculated from position + angle, connected by drawn lines on the bitmap. Thrust flame: additional vertex drawn behind ship when UP held.

**Asteroids:** 3 sizes.
| Size | Radius (px) | Points | Splits into |
|------|-------------|--------|-------------|
| Large | 12 | 20 | 2 medium |
| Medium | 7 | 50 | 2 small |
| Small | 3 | 100 | Destroyed |

**Gameplay:**
- All objects wrap at screen edges
- Start with 4 large asteroids, player in center
- Bullet limit: 4 active at a time
- Ship has inertia (velocity persists, thrust adds to velocity vector)
- Ship drag: slight deceleration so ship doesn't fly forever

**Difficulty:** Each level adds 1 more starting asteroid (level 2 = 5, level 3 = 6, etc.)

**Game over:** Ship hit by asteroid (3 lives).

**High score:** Saved to `/sd/saves/game_asteroids`

**Estimated size:** ~12–15K on flash (bitmap drawing helpers + trig)

---

### 4. Space Invaders

**Rendering:** `Rect` objects for aliens (5 rows × 8 columns = 40), ship, bullets, shields. Comparable to Hardball's 32 bricks. As aliens are destroyed, object count drops.

**Controls:**
| Input | Action |
|-------|--------|
| Encoder | Move ship horizontally (smooth analog) |
| LEFT/RIGHT | Move ship horizontally (discrete steps, alternative) |
| CENTER | Fire bullet |
| UP | Pause → quit |

**Layout:**
```
┌────────────────────────────────┐
│ Score: 0350        Lives: ♦♦♦  │
│                                │
│  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪   ← Row 1  │ ← 10 pts each
│  ▫ ▫ ▫ ▫ ▫ ▫ ▫ ▫   ← Row 2  │ ← 20 pts each
│  ▫ ▫ ▫ ▫ ▫ ▫ ▫ ▫   ← Row 3  │ ← 20 pts each
│  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪   ← Row 4  │ ← 30 pts each
│  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪   ← Row 5  │ ← 30 pts each
│                                │
│   ░░░░  ░░░░  ░░░░  ░░░░     │ ← Shields (4)
│          ▲▲▲                   │ ← Player ship
└────────────────────────────────┘
```

**Alien movement:**
- All aliens move together as a formation
- Move right until rightmost alien hits edge → drop 1 row, reverse to left
- Speed increases as aliens are destroyed (fewer aliens = faster march)

**Shields:**
- 4 shields made from small Bitmap sections (~8×6 pixels each)
- Erode pixel-by-pixel when hit by any bullet (player or alien)
- Aliens passing through shields also destroy them

**Alien firing:**
- Random alien in the lowest row of each column fires
- Fire rate increases with difficulty
- Max 2 alien bullets on screen

**Mystery ship:** Occasional ship across the top for bonus points (50–300 random).

**Game over:** Alien hits player (3 lives) or aliens reach the bottom row.

**High score:** Saved to `/sd/saves/game_invaders`

**Estimated size:** ~12–15K on flash

---

### 5. Lunar Lander

**Rendering:** `Line` segments for terrain, `Rect`/`Line` for lander, `Label` for HUD. Light object count (~15–20).

**Controls:**
| Input | Action |
|-------|--------|
| UP | Increase main thruster power |
| DOWN | Decrease main thruster power |
| Encoder | Side thrusters (CW = right thrust, CCW = left thrust) for fine lateral control |
| CENTER | Unused (or quick-boost) |

**Layout:**
```
┌────────────────────────────────┐
│ Fuel: ████░░  Alt: 89  Sc: 200│
│ Vx: -1.2   Vy: 3.4   Pwr: 40%│
│                                │
│         🔽                     │ ← Lander
│         ╎╎                     │ ← Thrust flame (size = power)
│                                │
│                                │
│╱╲    ╱╲___╱╲        ╱╲___╱╲  │ ← Terrain (Lines)
│   ╲╱╱         ╲____╱         │    Flat sections = landing pads
└────────────────────────────────┘
```

**Physics:**
- Gravity: constant downward acceleration (~0.5 px/tick²)
- Main thruster: upward force proportional to power level (UP/DOWN adjusts 0–100%)
- Side thrusters: lateral force from encoder input (returns to zero when encoder stops)
- Fuel: depletes proportional to total thrust used
- No fuel = no thrust (gravity wins)

**Landing:**
- Must land on a flat pad (horizontal terrain segment)
- Vertical velocity < threshold for safe landing (shown in HUD)
- Horizontal velocity < threshold
- Lander must be roughly level (not tilted — simplified: no tilt mechanic)

**Scoring:**
| Landing quality | Points |
|----------------|--------|
| Perfect (very slow, small pad) | 100 |
| Good (slow, any pad) | 50 |
| Rough (borderline velocity) | 25 |
| Crash | 0, lose a life |

**Difficulty:** Each level has rougher terrain, smaller pads, less fuel, and optional wind (random lateral force shown as arrow in HUD).

**Lives:** 3 landers. Game over when all crashed.

**High score:** Saved to `/sd/saves/game_lunar`

**Estimated size:** ~10–12K on flash

---

## Text Adventure Engine

### Architecture

```
Flash (Pico)                         SD Card
┌───────────────────────┐           ┌───────────────────────────┐
│ games/adventure.py    │           │ /sd/adventures/            │
│  ├─ AdventureEngine   │◄─────────│   colossal_cave.adv        │
│  │   ├─ parse/index   │  seek()  │   haunted_manor.adv        │
│  │   ├─ room renderer │           │   space_station.adv        │
│  │   ├─ choice UI     │           │                            │
│  │   ├─ inventory mgr │           │ /sd/saves/                 │
│  │   ├─ state tracker │           │   adv_colossal_cave        │
│  │   └─ save/load     │           │   adv_haunted_manor        │
│  └─ AdventureSelect   │           └───────────────────────────┘
│       (episode picker) │
└───────────────────────┘
```

**Engine on flash:** Single `adventure.py` module containing both the game engine class and the episode selection screen. Estimated ~15–20K.

**Episodes on SD card:** `.adv` text files in `/sd/adventures/`. Unlimited number and size since SD card has ample space.

**One room in RAM at a time:** On first load, the engine scans the file to build a room index (`room_id → byte_offset`). To enter a room, it `seek()`s to the offset and reads lines until the next `@ROOM` marker. Only the current room's parsed data (description, choices, items) is in memory.

### Story File Format (`.adv`)

Stream-parseable, line-based format. Each directive starts with `@`.

**Header directives:**

| Directive | Required | Example |
|-----------|----------|---------|
| `@TITLE text` | Yes | `@TITLE Colossal Cave Adventure` |
| `@AUTHOR text` | No | `@AUTHOR Adapted from Crowther & Woods` |
| `@START room_id` | Yes | `@START entrance` |
| `@DESC_TEXT text` | No | `@DESC_TEXT A brief description for the episode select screen` |

**Room directives:**

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@ROOM id` | Start a new room | `@ROOM dark_cave` |
| `@DESC` / `@ENDDESC` | Multi-line description block | See below |
| `@CHOICE "text" -> room_id` | Navigation choice | `@CHOICE "Go north" -> hallway` |
| `@CHOICE ... @NEED item` | Requires item in inventory | `@CHOICE "Unlock door" -> cellar @NEED brass_key` |
| `@CHOICE ... @NEED !flag` | Requires flag NOT set | `@CHOICE "Escape" -> exit @NEED !guards_alerted` |
| `@CHOICE ... @NEED flag` | Requires flag IS set | `@CHOICE "Enter" -> throne @NEED door_opened` |
| `@CHOICE ... @PICKUP item` | Stay in room, add item to inventory | `@CHOICE "Take the key" -> dark_cave @PICKUP brass_key` |
| `@CHOICE ... @USE item` | Consume item from inventory | `@CHOICE "Light the torch" -> dark_cave @USE match` |
| `@CHOICE ... @SET flag` | Set a flag when this choice is taken | `@CHOICE "Light a match" -> cave @USE match @SET has_torch` |
| `@ITEM id "name" "examine text"` | Item present in this room | `@ITEM brass_key "Brass Key" "Ornate, slightly tarnished."` |
| `@ON_ENTER @SET flag` | Set flag on room entry | `@ON_ENTER @SET visited_cave` |
| `@ON_ENTER @GIVE item` | Auto-give item on entry | `@ON_ENTER @GIVE map` |
| `@IF flag` / `@ENDIF` | Conditional block (no nesting) | Wraps choices or description lines |
| `@SCORE +N` | Add N points on entry | `@SCORE +10` |
| `@GAMEOVER "text"` | Game over screen | `@GAMEOVER "The cave collapses. You are crushed."` |
| `@WIN "text"` | Victory screen | `@WIN "You escape with the treasure! Final score: {score}"` |

**Example room:**

```
@ROOM dark_cave
@DESC
The cave is pitch black. You can hear water
dripping somewhere ahead. The air is cold
and damp.
@IF has_torch
The torch illuminates rough stone walls
covered in ancient markings.
@ENDIF
@ENDDESC
@ITEM old_coin "Old Coin" "A worn gold coin with an unfamiliar face."
@CHOICE "Take the coin" -> dark_cave @PICKUP old_coin
@CHOICE "Go deeper" -> deep_cave @NEED has_torch
@CHOICE "Go back" -> entrance
@CHOICE "Light a match" -> dark_cave @USE match @SET has_torch
@SCORE +5
```

### Display Layout

```
┌──────────────────────────┐
│ Colossal Cave      [INV] │  ← Title + inventory indicator
│──────────────────────────│
│ The cave is pitch black. │
│ You can hear water       │  ← Description area
│ dripping somewhere       │    (scrollable when focused)
│ ahead. The air is cold   │
│ and damp.                │
│──────────────────────────│
│ ▸ Take the coin          │  ← Choice list
│   Go deeper (locked)     │    (encoder scrolls,
│   Go back                │     CENTER selects)
└──────────────────────────┘
```

### Encoder Focus Toggle

The encoder can control either the description scroll or the choice list:

- **DOWN** switches focus between the two areas
- A `▸` marker on the left edge indicates which section the encoder controls
- Default focus: **choices** (the most common action)
- When focused on description: encoder scrolls text up/down
- When focused on choices: encoder scrolls through options
- **CENTER** always selects the highlighted choice regardless of which area has focus

### Controls Summary

| Input | Action |
|-------|--------|
| Encoder | Scroll focused area (description or choices) |
| CENTER | Select highlighted choice |
| UP | Toggle inventory overlay (shows items + flags as status) |
| DOWN | Switch encoder focus between description and choices |
| LEFT/RIGHT | Unused (reserved for future: examine item, hint) |

### Inventory Overlay

Pressing UP shows a modal overlay:

```
┌──────────────────────────┐
│ ═══ Inventory ═══        │
│                          │
│  • Brass Key             │
│  • Old Coin              │
│  • Torch (lit)           │
│                          │
│  Score: 45               │
│                          │
│  [UP to close]           │
└──────────────────────────┘
```

Encoder scrolls through items, DOWN examines selected item (shows its description text). UP again closes the overlay.

### State & Save System

**Runtime state:**
```python
{
    "room": "dark_cave",
    "inventory": ["brass_key", "old_coin"],
    "flags": {"visited_cave": True, "door_opened": True},
    "score": 45
}
```

**Save format:** Written to `/sd/saves/adv_<adventure_name>` as line-based key=value:
```
room=dark_cave
inventory=brass_key,old_coin
flags=visited_cave,door_opened
score=45
```

**Save triggers:** Auto-save on every room transition. One save slot per adventure.

### Episode Selection Screen

"Adventures" appears as an entry in the game select screen. Selecting it shows a secondary picker that scans `/sd/adventures/` for `.adv` files:

```
┌──────────────────────────┐
│   ═══ Adventures ═══     │
│                          │
│   Colossal Cave [SAVED]  │
│ ▸ Haunted Manor          │
│   Space Station Omega    │
│                          │
│                          │
│  [CENTER to play]        │
└──────────────────────────┘
```

- Reads `@TITLE` from each file's header for display names
- Shows `[SAVED]` if a save file exists for that adventure
- Encoder scrolls, CENTER launches
- UP returns to game select

### Starter Episodes

Ship 1–2 starter episodes with the engine to verify it works end-to-end:

1. **Tutorial Dungeon** (~20 rooms) — A short adventure that exercises all engine features: rooms, items, conditions, flags, scoring, game over, and win states. Doubles as a test fixture.
2. **Colossal Cave (Abridged)** (~40–60 rooms) — An adaptation of the original Colossal Cave Adventure, simplified to choice-based navigation. Covers the main path and major puzzles.

Additional episodes can be authored by anyone and dropped into `/sd/adventures/`.

---

## Game Select Screen Updates

The current game select screen shows "Sub Hunt" and "Hardball" in a flat list. With 8 entries (7 games + Adventures), the list still fits on one screen without categories:

```
┌──────────────────────────┐
│   ═══ Games ═══          │
│                          │
│   Sub Hunt               │
│   Hardball               │
│   Snake                  │
│ ▸ Missile Command        │
│   Asteroids              │
│   Space Invaders         │
│   Lunar Lander           │
│   Adventures             │
│                          │
└──────────────────────────┘
```

Encoder scrolls with wrapping, CENTER launches. The existing `show_game_select_screen()` in `display.py` just needs its list extended. The `games/__init__.py` registry gets new entries.

---

## Game Interface Contract

All games implement the existing contract (unchanged from Sub Hunt / Hardball):

```python
class GameName:
    def __init__(self, hw_display, smallfont):
        """Initialize game, build displayio group, show on display."""

    def handle_button(self, button):
        """Handle button press. Return 'quit' to exit, None otherwise."""

    def handle_encoder(self, direction):
        """Handle encoder turn (+1/-1). Return 'quit' to exit, None otherwise."""

    def tick(self, now):
        """Update game state. Return True if display needs refresh."""

    def get_group(self):
        """Return the displayio.Group for this game."""

    def destroy(self):
        """Clean up all displayio objects for GC."""
```

**Pause system (arcade games):** UP pauses, CENTER resumes, UP again quits. Same pattern as existing games.

**Adventure engine:** Same contract, but `tick()` is mostly idle (no physics loop). The engine is event-driven — display updates happen in response to button/encoder input.

---

## Flash Budget

| Component | Estimated Size |
|-----------|---------------|
| Snake | 8–10K |
| Missile Command | 12–15K |
| Asteroids | 12–15K |
| Space Invaders | 12–15K |
| Lunar Lander | 10–12K |
| Adventure engine | 15–20K |
| `__init__.py` updates | <1K |
| **Total new** | **~70–90K** |
| **Available before** | **592K** |
| **Remaining after** | **~500–520K** |

Leaves over 500K for future eReader features.

---

## Verification

### Per-game testing
1. Launch each game from game select screen
2. Verify all controls respond correctly per the control tables above
3. Play through at least 2 levels / difficulty increases
4. Trigger game over, verify high score save and display
5. Quit via pause menu, verify clean return to game select
6. Check `gc.mem_free()` after quit — should recover to pre-game levels

### Adventure engine testing
1. Launch Adventures from game select
2. Verify episode list loads from `/sd/adventures/`
3. Play through tutorial dungeon exercising all directives
4. Test encoder focus toggle (DOWN) between description and choices
5. Test inventory overlay (UP) with item examination
6. Verify conditional choices (`@NEED`, `@IF`) show/hide correctly
7. Verify save/load: quit mid-game, relaunch, confirm state restored
8. Test `@GAMEOVER` and `@WIN` endings
9. Test with a long description (>8 lines) to verify scrolling

### Integration testing
1. Play a game, quit, immediately start reading a book — no glitches
2. Play multiple games in sequence — no memory leaks
3. Verify game select screen scrolls correctly with 8 entries
4. Verify high scores persist across power cycles
