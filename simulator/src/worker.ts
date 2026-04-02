// Web Worker: loads Pyodide, mounts virtual FS, runs code.py with shim modules

const _self = self as unknown as DedicatedWorkerGlobalScope & {
  __buttonQueue: Array<{ keyNumber: number; pressed: boolean }>;
  __encoderPosition: number;
  __saves: Record<string, string>;
};

// Message queues for Python shims to read from
_self.__buttonQueue = [];
_self.__encoderPosition = 0;
_self.__saves = {};

_self.onmessage = async (e: MessageEvent) => {
  const msg = e.data;
  switch (msg.type) {
    case 'init':
      _self.__saves = msg.saves ?? {};
      await startPyodide();
      break;
    case 'button':
      _self.__buttonQueue.push({
        keyNumber: msg.keyNumber,
        pressed: msg.pressed,
      });
      break;
    case 'encoder':
      _self.__encoderPosition = msg.position;
      break;
  }
};

async function startPyodide() {
  _self.postMessage({ type: 'console', message: 'Loading Pyodide...' });

  // Load Pyodide from CDN
  // Module workers can't use importScripts, so we use dynamic import
  const { loadPyodide } = await import(
    /* @vite-ignore */
    'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.mjs'
  );
  const pyodide = await loadPyodide();

  _self.postMessage({ type: 'console', message: 'Pyodide loaded. Setting up filesystem...' });

  // Fetch and mount font files
  const fontFiles = ['Toronto_14.pcf', 'Toronto_9.pcf'];
  pyodide.FS.mkdirTree('/fonts');
  for (const name of fontFiles) {
    const resp = await fetch(`/assets/fonts/${name}`);
    const data = new Uint8Array(await resp.arrayBuffer());
    pyodide.FS.writeFile(`/fonts/${name}`, data);
  }

  // Fetch and mount book files
  pyodide.FS.mkdirTree('/sd/books');
  const bookListResp = await fetch('/assets/books/');
  // Vite dev server serves directory listings; fallback to known book list
  let bookFiles: string[];
  try {
    const text = await bookListResp.text();
    // Parse directory listing for .txt files
    const matches = text.match(/href="([^"]+\.txt)"/g);
    bookFiles = matches
      ? matches.map((m) => decodeURIComponent(m.slice(6, -1)))
      : [];
  } catch {
    bookFiles = [];
  }

  // Fallback: hardcoded book list
  if (bookFiles.length === 0) {
    bookFiles = [
      '(Earthsea 1)  Ursula K Le Guin - A Wizard Of Earthsea (1835).txt',
      '(Red Rising 2) Pierce Brown - Golden Son (3249).txt',
      '(Red Rising 3) Pierce Brown - Morning Star (12557).txt',
      'Test Author - Short Story (20).txt',
      'Test Author - Five Lines (25).txt',
      '(TestSeries 1) Test Author - Chapter Book (50).txt',
    ];
  }

  for (const name of bookFiles) {
    try {
      const resp = await fetch(`/assets/books/${encodeURIComponent(name)}`);
      if (resp.ok) {
        const data = new Uint8Array(await resp.arrayBuffer());
        pyodide.FS.writeFile(`/sd/books/${name}`, data);
        _self.postMessage({ type: 'console', message: `Loaded book: ${name} (${data.length} bytes)` });
      }
    } catch (err) {
      _self.postMessage({ type: 'console', message: `Failed to load book: ${name}` });
    }
  }

  // Create saves directory and load persisted saves
  pyodide.FS.mkdirTree('/saves');
  const saves = _self.__saves;
  for (const [filename, data] of Object.entries(saves)) {
    pyodide.FS.writeFile(`/saves/${filename}`, data);
  }

  // Load shim modules
  const shimModules = [
    '_bridge', '_state_tracker',
    'board', 'digitalio', 'busio', 'sdcardio', 'storage',
    'displayio', 'adafruit_st7735r', 'keypad', 'rotaryio',
    'pwmio', 'time_patch',
    'adafruit_display_text/__init__', 'adafruit_display_text/label',
    'adafruit_bitmap_font/__init__', 'adafruit_bitmap_font/bitmap_font',
    'adafruit_display_shapes/__init__', 'adafruit_display_shapes/rect',
  ];

  pyodide.FS.mkdirTree('/shims/adafruit_display_text');
  pyodide.FS.mkdirTree('/shims/adafruit_bitmap_font');
  pyodide.FS.mkdirTree('/shims/adafruit_display_shapes');

  for (const mod of shimModules) {
    const filename = mod.includes('/') ? mod : mod;
    try {
      const resp = await fetch(`/shims/${filename}.py`);
      if (resp.ok) {
        const code = await resp.text();
        pyodide.FS.writeFile(`/shims/${filename}.py`, code);
      }
    } catch {
      _self.postMessage({ type: 'console', message: `Failed to load shim: ${mod}` });
    }
  }

  // Create app directory for code.py
  pyodide.FS.mkdirTree('/app');

  // Set working directory to / so relative paths (saves/, fonts/) resolve correctly
  pyodide.FS.chdir('/');

  // Add shims to Python path (before standard lib so they shadow CircuitPython modules)
  pyodide.runPython(`
import sys
sys.path.insert(0, '/shims')
  `);

  // Apply time patches and redirect print output
  pyodide.runPython(`
import time_patch

# Redirect print to post console messages to main thread
import sys
import io
from _bridge import post_message

class _ConsoleWriter(io.TextIOBase):
    def write(self, text):
        if text and text.strip():
            post_message({"type": "console", "message": text.rstrip()})
        return len(text)

sys.stdout = _ConsoleWriter()
sys.stderr = _ConsoleWriter()
  `);

  _self.postMessage({ type: 'ready' });
  _self.postMessage({ type: 'console', message: 'Starting code.py...' });

  // Fetch the application code from the firmware directory
  let code: string;
  try {
    const resp = await fetch('/firmware/code.py');
    code = await resp.text();
  } catch (err: any) {
    _self.postMessage({
      type: 'console',
      message: `Failed to fetch code.py: ${err.message ?? err}`,
    });
    return;
  }

  // Write code.py to the virtual FS, stripping the module-level main() call
  // so we can import it without it auto-executing
  const strippedCode = code.replace(/^main\(\)\s*$/m, '# main() — called by simulator wrapper');
  pyodide.FS.writeFile('/app/code.py', strippedCode);

  // Fetch pico_reader module files
  const picoModules = [
    '__init__',
    'constants',
    'hardware',
    'state',
    'book_reader',
    'display',
    'input_handlers',
    'utils',
    'main',
    'settings',
    'menu',
    'recent',
    'analytics',
    'orp',
    'skins/__init__',
    'skins/default',
    'skins/terminal',
    'skins/rpg',
    'skins/typewriter',
    'animations/__init__',
    'animations/page_turn',
    'animations/particles',
    'animations/walker',
  ];

  pyodide.FS.mkdirTree('/app/pico_reader');
  pyodide.FS.mkdirTree('/app/pico_reader/skins');
  pyodide.FS.mkdirTree('/app/pico_reader/animations');

  for (const mod of picoModules) {
    try {
      const resp = await fetch(`/firmware/pico_reader/${mod}.py`);
      if (resp.ok) {
        const code = await resp.text();
        pyodide.FS.writeFile(`/app/pico_reader/${mod}.py`, code);
      }
    } catch {
      _self.postMessage({
        type: 'console',
        message: `Failed to load module: pico_reader/${mod}.py`,
      });
    }
  }

  // Run with a wrapper that hooks into the application objects for state tracking
  // and save file mirroring
  try {
    await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, '/app')

# Import the application module
import code

# Monkey-patch save methods to mirror writes to main thread
import _state_tracker
from _bridge import post_message

_original_save_place = code.BookReader.save_place
_original_save_backup = code.BookReader.save_backup

def _patched_save_place(self):
    _original_save_place(self)
    try:
        with open("saves/save_{}".format(self.book), 'r') as f:
            data = f.read()
        post_message({"type": "save", "filename": "save_{}".format(self.book), "data": data})
    except:
        pass

def _patched_save_backup(self):
    _original_save_backup(self)
    try:
        with open("saves/save_prev_{}".format(self.book), 'r') as f:
            data = f.read()
        post_message({"type": "save", "filename": "save_prev_{}".format(self.book), "data": data})
    except:
        pass

code.BookReader.save_place = _patched_save_place
code.BookReader.save_backup = _patched_save_backup

# Monkey-patch main() to register state tracker
_original_main = code.main

async def _patched_main():
    hw_display, backlight, spi, encoder = code.init_hardware()

    settings = code.load_settings()
    font = code.load_reading_font(settings.get('font', 'Toronto_14.pcf'))
    smallfont = code.bitmap_font.load_font("fonts/Toronto_9.pcf")

    books = [x for x in code.os.listdir("/sd/books/") if x.endswith('.txt')]
    if not books:
        return

    metadata = [code.parse_book_filename(b) for b in books]
    lens = [m[3] for m in metadata]

    state = code.AppState(settings=settings)
    book = code.BookReader(books, metadata, lens)
    book.load_place()

    # Build menu tree
    recent_filenames = code.recent.load_recent()
    root = code.menu.build_menu_tree(books, metadata, recent_filenames)
    state.menu_state = code.menu.MenuState(root)

    disp = code.Display(hw_display, backlight, font, smallfont,
                        skin_name=state.skin_name)
    disp.set_brightness(state.brightness)

    # Register with state tracker
    _state_tracker.register(state, book, metadata)

    disp.show_menu_screen(state.menu_state, metadata)

    with code.keypad.Keys(code.PIN_BUTTONS, value_when_pressed=False, pull=True) as keys:
        # Instead of calling main_loop (which has a blocking while True),
        # run an async version that yields to the browser event loop
        await _async_main_loop(state, book, disp, keys, encoder)

async def _async_main_loop(state, book, disp, keys, encoder):
    """Async replacement for code.main_loop that yields via JS setTimeout."""
    import asyncio
    from js import Promise, self as _w

    last_enc_pos = encoder.position
    last_word_time = 0.0
    lines_since_save = 0
    last_line = book.line_num
    prev_line_empty = False

    while True:
        now = code.time.monotonic()

        # --- Buttons ---
        event = keys.events.get()
        if event and event.pressed:
            handler = code.BUTTON_HANDLERS.get((state.mode, event.key_number))
            if handler:
                handler(state, book, disp)
                _state_tracker.send_state()
            # Update cursor visibility after button handling
            disp.set_cursor_visible(not state.playing)

        # --- Encoder ---
        enc_pos = encoder.position
        if enc_pos != last_enc_pos:
            direction = 1 if enc_pos > last_enc_pos else -1
            handler = code.ENCODER_HANDLERS.get((state.mode, direction))
            if handler:
                handler(state, book, disp)
                _state_tracker.send_state()
            last_enc_pos = enc_pos

        # --- Word display timer ---
        if state.mode == code.AppState.MODE_READER and state.playing:
            # Calculate delay: smart pacing or flat rate
            if state.smart_pacing:
                word_delay = state._next_word_delay
            else:
                word_delay = state.speed

            if now - last_word_time >= word_delay:
                word = book.step_forward()
                if word:
                    cleaned = code.clean_word(word)

                    # Detect paragraph start: first word on a line that
                    # follows an empty line
                    is_para_start = (book.word_idx == 1
                                     and book.line_num > 0
                                     and prev_line_empty)

                    # Pre-compute delay for the NEXT iteration so the
                    # current word's complexity determines how long it
                    # stays on screen.
                    if state.smart_pacing:
                        ramp = state.get_ramp_factor()
                        state._next_word_delay = code.calculate_word_delay(
                            cleaned, state.wpm, is_para_start, ramp)
                    else:
                        state._next_word_delay = state.speed

                    # Track whether this line is empty (for next
                    # paragraph-start detection)
                    prev_line_empty = (book._get_words(book.line_num) == [])

                    if len(cleaned) > 17:
                        for part in cleaned.split('-'):
                            disp.show_word(part + '-', state.orp_mode)
                            disp.show_wpm(state.wpm)
                            disp.tick_animation(state, book)
                            disp.refresh()
                    else:
                        disp.show_word(cleaned, state.orp_mode)
                        disp.show_wpm(state.wpm)
                        disp.tick_animation(state, book)
                        disp.refresh()

                    # Track analytics
                    if state.book_stats:
                        state.book_stats.increment_word()
                    if state.session_stats:
                        state.session_stats.record_word(state.wpm)

                    # Auto-save and progress update
                    if book.line_num != last_line:
                        lines_since_save += book.line_num - last_line
                        last_line = book.line_num
                        if lines_since_save >= code.SAVE_INTERVAL:
                            book.save_place()
                            if state.book_stats:
                                state.book_stats.save()
                            disp.update_progress(book.line_num, book.book_len)
                            disp.refresh()
                            lines_since_save = 0
                else:
                    # End of book
                    state.playing = False
                    state.finished = True
                    book.save_place()
                    disp.show_word("End of Book")
                    disp.show_wpm(state.wpm)
                    disp.refresh()

                last_word_time = now

        # --- Periodic state update (every ~100ms = 10 iterations) ---
        _loop_counter = getattr(_async_main_loop, '_counter', 0) + 1
        _async_main_loop._counter = _loop_counter
        if _loop_counter % 10 == 0:
            _state_tracker.send_state()

        # --- Yield to browser event loop via JS Promise ---
        await Promise.new(lambda resolve, *_: _w.setTimeout(resolve, 10))

await _patched_main()
    `);
  } catch (err: any) {
    _self.postMessage({
      type: 'console',
      message: `Error running code.py: ${err.message ?? err}`,
    });
  }
}
