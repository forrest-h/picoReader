# picoReader Browser Simulator — Design Spec

## Context

picoReader is an RSVP speed-reading eReader running CircuitPython on a Raspberry Pi Pico with a 160x128 ST7735R LCD, rotary encoder clickwheel, and 5-button keypad. Currently, every UI or logic change requires deploying to the physical device to test. This simulator enables rapid iteration by running the real `code_v2.py` in a browser with emulated hardware.

## Goal

A browser-based simulator that:
- Runs `code_v2.py` (the canonical codebase) unmodified
- Renders a pixel-accurate 160x128 LCD display
- Provides interactive hardware controls (clickwheel, 5 buttons)
- Matches real-world timing behavior (WPM pacing, sleep durations)
- Includes a state inspector for development visibility
- Persists save state across browser sessions

## Architecture: Pyodide in Web Worker

The simulator uses **Pyodide** (CPython compiled to WebAssembly) running inside a **Web Worker**. The main thread owns the canvas, hardware UI, and state inspector. Communication flows via `postMessage`.

```
Main Thread                          Web Worker
============                         ===========
Canvas renderer  <-- refresh msg --  Pyodide + code_v2.py
Hardware UI      --- input msg  -->  Python shim modules
State inspector  <-- state msg  --   (board, displayio, keypad, etc.)
localStorage     <-- save msg   --
```

### Why Web Worker

- `time.sleep(0.01)` in the `while True` main loop must yield without blocking the UI. In a Worker, this is a reliable async yield via Pyodide's Asyncify/JSPI support.
- The main thread stays responsive for canvas painting, clickwheel animation, and state inspector updates regardless of Python execution load.
- Clean separation: rendering logic in TypeScript, application logic in Python.

## Project Structure

```
simulator/
  index.html                -- Shell: loads JS, creates layout
  style.css                 -- Hardware replica + inspector styling
  src/
    main.ts                 -- Entry: Worker lifecycle, canvas setup, UI wiring
    renderer.ts             -- Paints scene graph messages to 160x128 canvas
    pcf-parser.ts           -- Parses PCF binary -> glyph bitmaps + metrics
    hardware-ui.ts          -- Clickwheel SVG, buttons, mouse/keyboard -> events
    state-inspector.ts      -- Side panel: mode, WPM, book info, group tree, console
    worker.ts               -- Loads Pyodide, mounts FS, runs code_v2.py
    shims/                  -- Python shim package (loaded into Pyodide)
      board.py              -- Pin constants (GP2, GP3... as simple objects)
      digitalio.py          -- DigitalInOut stub (no-op)
      busio.py              -- SPI stub (no-op)
      sdcardio.py           -- SDCard stub (no-op)
      storage.py            -- VfsFat/mount stubs (FS pre-loaded)
      displayio.py          -- Group, Bitmap, Palette, TileGrid, FourWire
      adafruit_st7735r.py   -- ST7735R class (wraps display shim)
      adafruit_display_text/
        __init__.py
        label.py            -- Label class
      adafruit_bitmap_font/
        __init__.py
        bitmap_font.py      -- load_font -> JS bridge
      adafruit_display_shapes/
        __init__.py
        rect.py             -- Rect class
      keypad.py             -- Keys with event queue fed by messages
      rotaryio.py           -- IncrementalEncoder (position from messages)
      pwmio.py              -- PWMOut stub (posts brightness)
      time_patch.py         -- Patches time.sleep -> async yield
  assets/
    fonts/
      Toronto_14.pcf
      Toronto_9.pcf
    books/                  -- 3 bundled sample books
  package.json
  vite.config.ts
  tsconfig.json
```

**Build**: Vite + TypeScript. Vite natively handles Worker bundling via `new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })`.

**Pyodide version**: Target Pyodide 0.26+ (latest stable). Load from CDN (`cdn.jsdelivr.net/pyodide/`). Pyodide's Emscripten FS supports `os.listdir()`, `open()`, `readline()`, and other standard file operations on pre-populated paths — no special handling needed for `code_v2.py`'s file I/O.

## Communication Protocol

### Worker -> Main Thread

| Message type | Trigger | Payload |
|-------------|---------|---------|
| `ready` | Pyodide loaded, `main()` about to start | `{}` |
| `refresh` | `display.refresh()` called | `{ sceneGraph: SceneNode[] }` |
| `state` | Any state change | `{ mode, wpm, playing, finished, bookId, lineNum, wordIdx, themeIndex, brightness }` |
| `save` | `save_place()` or `save_backup()` | `{ filename: string, data: string }` |
| `console` | Python `print()` or shim debug | `{ message: string }` |

#### Scene graph node types

```typescript
type SceneNode =
  | { type: 'tilegrid'; x: number; y: number; w: number; h: number;
      paletteColors: number[]; bitmapData?: number[] }
  | { type: 'label'; text: string; x: number; y: number;
      anchorX: number; anchorY: number; color: number;
      fontId: string; baseAlignment: boolean }
  | { type: 'rect'; x: number; y: number; w: number; h: number;
      fill: number; outline: number; stroke: number }
```

All colors are BGR integers (matching CircuitPython). The renderer converts to RGB at paint time.

### Main Thread -> Worker

| Message type | Trigger | Payload |
|-------------|---------|---------|
| `init` | Before main() starts | `{ saves: Record<string, string> }` |
| `button` | Button clicked/pressed | `{ keyNumber: number, pressed: boolean }` |
| `encoder` | Clickwheel rotated | `{ position: number }` |

## Display Rendering

### Canvas renderer (`renderer.ts`)

- Operates on a `160x128` pixel `<canvas>` using `ImageData` for pixel-perfect output (no anti-aliasing, no subpixel rendering)
- On each `refresh` message: clear framebuffer, walk scene graph array in order (painters algorithm), write `ImageData` via `putImageData()`
- Canvas is scaled 3x in CSS via `image-rendering: pixelated` / `crisp-edges` (480x384 CSS pixels)

#### Rendering each node type

**Solid TileGrid** (backgrounds): Fill the rect area with `palette[0]` converted BGR->RGB.

**Bitmap TileGrid** (progress bar): Iterate pixels, look up `bitmapData[i]` as palette index, paint that color. The progress bar is 160x2 with per-pixel data.

**Label**: Look up PCF font by ID, iterate characters, for each glyph paint the 1-bit bitmap pixels in the label's color. Position computed from anchor math (see below).

**Rect**: Fill rectangle with `fill` color, then draw outline inset by `stroke` width.

#### BGR-to-RGB conversion

```typescript
function bgrToRgb(bgr: number): [r: number, g: number, b: number] {
  return [bgr & 0xFF, (bgr >> 8) & 0xFF, (bgr >> 16) & 0xFF];
}
```

#### Label anchor positioning (matching CircuitPython)

```
finalX = anchoredPosition.x - anchorPoint.x * boundingBoxWidth
finalY = anchoredPosition.y - anchorPoint.y * boundingBoxHeight
```

Where:
- `boundingBoxWidth` = sum of glyph advances for the text string
- `boundingBoxHeight` = font ascent + descent
- `base_alignment=False` means anchor point Y references the full bounding box (ascent + descent)
- `base_alignment=True` means anchor point Y=1.0 aligns to the baseline

#### Backlight simulation

A semi-transparent dark overlay `<div>` on top of the canvas. Opacity = `1 - (brightness / 100)`. At 100% brightness the overlay is invisible; at 1% it's nearly opaque.

### PCF font parser (`pcf-parser.ts`)

Parses the binary X11 PCF format:
1. Read table of contents (type, format, size, offset for each table)
2. Extract **METRICS** table: glyph bounding boxes (left/right bearing, width, ascent, descent)
3. Extract **BDF_ENCODINGS** table: character code -> glyph index mapping
4. Extract **BITMAPS** table: 1-bit glyph images (row-padded, MSB first)

Output: `Map<charCode, Glyph>` where:
```typescript
interface Glyph {
  width: number;       // bitmap pixel width
  height: number;      // bitmap pixel height
  xOffset: number;     // left side bearing
  yOffset: number;     // ascent - glyph ascent
  advance: number;     // horizontal advance width
  bitmap: Uint8Array;  // 1-bit packed glyph image
}
```

Toronto fonts contain ~170 glyphs each (~10-12KB per font file).

## Python Shim Layer

15 CircuitPython modules replaced with browser-backed shims. `code_v2.py` runs unmodified.

### No-op shims (hardware stubs)

| Module | What it provides | Implementation |
|--------|-----------------|----------------|
| `board` | Pin constants (GP2, GP3, ...) | Simple `Pin` class with `.id` attribute |
| `digitalio` | `DigitalInOut`, `switch_to_output()` | No-op methods |
| `busio` | `SPI(clock, MOSI, MISO)` | Returns dummy object |
| `sdcardio` | `SDCard(spi, cs)` | No-op (Emscripten FS pre-loaded) |
| `storage` | `VfsFat()`, `mount()`, `remount()` | No-ops |

### Display shims

**`displayio.py`**:
- `Group`: Python list of children with `append()`, `__setitem__` (index replacement), `__getitem__`
- `Bitmap(w, h, colors)`: 2D array (`list[list[int]]`), supports `__setitem__((x,y), value)`
- `Palette(n)`: List of color ints, supports `__setitem__(index, color)`
- `TileGrid(bitmap, pixel_shader=palette)`: Holds references, stores `x`, `y` position
- `FourWire(spi, command, chip_select, reset)`: Stub
- `release_displays()`: No-op

**`adafruit_st7735r.py`**:
- `ST7735R(bus, width, height, rotation, colstart, rowstart, auto_refresh)`: Stores dimensions
- `.show(group)`: Sets current root group reference
- `.refresh()`: Serializes root group tree -> posts `refresh` message to main thread via `js.postMessage`

**`adafruit_display_text/label.py`**:
- `Label(font, text, color, base_alignment)`: Stores all properties
- `.text`, `.color`: Settable properties
- `.anchor_point`, `.anchored_position`: Settable tuples
- During serialization: emits `{ type: 'label', text, color, fontId, anchorX, anchorY, x, y, baseAlignment }`

**`adafruit_display_shapes/rect.py`**:
- `Rect(x, y, w, h, fill, outline, stroke)`: Stores all properties
- `.fill`, `.outline`: Settable properties
- During serialization: emits `{ type: 'rect', ... }`

**`adafruit_bitmap_font/bitmap_font.py`**:
- `load_font(path)`: Returns a font object with a string ID (the path). Actual PCF parsing happens on the main thread; the shim only stores the identifier.

### Input shims

**`keypad.py`**:
- `Keys(pins, value_when_pressed, pull)`: Context manager. On `__enter__`, registers a JS `onmessage` handler (via Pyodide's `js` module) that pushes `Event` objects into a Python `collections.deque` when `button` messages arrive.
- `keys.events.get()`: Pops from deque, returns `Event` or `None`
- `Event` class: has `.pressed` (bool) and `.key_number` (int) attributes

**`rotaryio.py`**:
- `IncrementalEncoder(pinA, pinB, divisor)`: Module-level position variable
- `.position` property: reads from variable updated by incoming `encoder` messages

### Timing shim

**`time_patch.py`** (loaded first in Worker):
- Monkey-patches `time.sleep(seconds)` to yield via Pyodide's async bridge: calls into a JS function that returns a `Promise` wrapping `setTimeout`, which Pyodide awaits via Asyncify/JSPI
- Patches `time.monotonic()` to use `performance.now() / 1000`

### PWM shim

**`pwmio.py`**:
- `PWMOut(pin, frequency, duty_cycle)`: Stores values
- `.duty_cycle` setter: Posts brightness message to main thread (main thread adjusts backlight overlay)

## Hardware UI

### Layout

A dark "device bezel" `<div>` containing:
- **LCD screen**: The canvas (scaled 3x), centered in the bezel with backlight overlay
- **D-pad buttons**: Below the screen. CENTER is a large circle; UP/DOWN/LEFT/RIGHT arranged as directional pads around it
- **Clickwheel**: To the right of the buttons. Circular SVG element with a knob indicator showing rotation position

### Button interaction

- Click/tap on a button -> posts `{ type: 'button', keyNumber: N, pressed: true }` to Worker
- Visual feedback: button briefly highlights on press (CSS transition)
- Keyboard shortcuts: `Space`=CENTER, `ArrowUp`=UP, `ArrowDown`=DOWN, `ArrowLeft`=LEFT, `ArrowRight`=RIGHT

### Clickwheel interaction

- Mouse/touch drag on the wheel tracks angular movement. Each 15-degree increment posts an encoder position change (+1 or -1)
- Scroll wheel over the clickwheel area: scroll up = +1, scroll down = -1
- The knob indicator rotates visually to show current position
- Keyboard: `[` and `]` keys for encoder left/right

## State Inspector Panel

Right-side panel (~300px wide) with sections:

1. **Status bar**: Mode badge (MENU / READER / DISPLAY), Playing/Paused/Finished indicator
2. **Book info**: Title, author, series, line number / total lines, word index
3. **Settings**: WPM value, brightness %, theme index with color swatches
4. **Display group tree**: Collapsible tree showing current root group's children (type, position, key properties like label text, rect fill, bitmap dimensions). Updates on each refresh message.
5. **Console**: Scrollable log of Python `print()` output and shim debug messages

## File System & Persistence

- **Books**: 3 sample books bundled as static assets in `assets/books/`. Fetched via HTTP at startup, written to Pyodide's Emscripten FS at `/sd/books/`
- **Fonts**: `Toronto_14.pcf` and `Toronto_9.pcf` bundled in `assets/fonts/`. Fetched and written to Emscripten FS at `fonts/`. Also loaded by the main thread PCF parser for rendering.
- **Saves**: Python writes to Emscripten FS at `saves/` (so subsequent Python reads work). The shim also posts save data to the main thread, which persists to `localStorage` with key prefix `picoReader_save_`. On startup, main thread reads all `picoReader_save_*` keys and sends them to Worker via `init` message for Emscripten FS pre-population.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `time.sleep` doesn't yield in Worker | Main loop blocks, no word display | Validate first with minimal `while True: time.sleep(0.01)` test in Pyodide Worker. Pyodide 0.24+ supports this. Fallback: wrap `main_loop()` in explicit async. |
| PCF font rendering doesn't match CircuitPython | Words positioned wrong on screen | Compare screenshots pixel-by-pixel against real device. Toronto fonts are small (~170 glyphs). |
| Pyodide download is 10-15MB | Slow first load | Show loading progress bar. Use CDN-hosted Pyodide for caching. Show hardware UI shell immediately while Pyodide loads in background. |
| Label bounding box differs from CircuitPython | Text misaligned | Study `adafruit_display_text` source for exact anchor math, especially `base_alignment` parameter. Test with known strings. |
| Message latency for input | Button/encoder response feels laggy | At 10ms polling interval, one `postMessage` round-trip is imperceptible. No mitigation needed. |

## Verification Plan

1. **Pyodide sleep test**: Before building the full shim, run a minimal `while True: time.sleep(0.01); print("tick")` loop in a Pyodide Web Worker to confirm yielding works
2. **Font fidelity**: Render "picoReader", "200", and a sample word in both Toronto fonts. Compare pixel-by-pixel against a photo/screenshot of the real device
3. **Scene graph correctness**: Hard-code a known theme + word + progress state, render it, compare against expected pixel output
4. **Full integration**: Load a sample book, verify menu displays correctly, select a book, confirm word display starts at correct WPM, pause/resume, step forward/backward, change theme, adjust brightness
5. **Save persistence**: Read a book partway, refresh the browser, verify it resumes at the saved position
6. **Input responsiveness**: Verify button presses and encoder rotation feel immediate with no perceptible lag
