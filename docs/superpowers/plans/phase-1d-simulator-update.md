# Phase 1D: Simulator Update for Module Split

> **Dependency:** Phase 1A (module split) must be complete. Can run in parallel with 1B and 1C.

**Goal:** Update `simulator/src/worker.ts` to fetch and mount the `pico_reader/` module files into Pyodide's virtual filesystem so the simulator works with the new multi-file structure.

---

## What needs to change in worker.ts

### 1. Fetch and mount pico_reader modules

Currently worker.ts fetches only `code.py` (line 164-173) and writes it to `/app/code.py`. After the module split, it also needs to fetch all `pico_reader/*.py` files and mount them under `/app/pico_reader/`.

Add after the code.py fetch:

```typescript
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
  'settings',  // Added in Phase 1B
];

pyodide.FS.mkdirTree('/app/pico_reader');

for (const mod of picoModules) {
  try {
    const resp = await fetch(`../firmware/pico_reader/${mod}.py`);
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
```

### 2. No changes to monkey-patching

The monkey-patching in worker.ts (lines 196-238) accesses everything via `code.X` (e.g., `code.BookReader`, `code.AppState`). Since `code.py` does `from pico_reader import *` and `__init__.py` re-exports everything, all `code.X` references still resolve. No patching changes needed.

### 3. No changes to code.py stripping

Line 177 strips `main()` from code.py:
```typescript
const strippedCode = code.replace(/^main\(\)\s*$/m, '# main() — called by simulator wrapper');
```

The new `code.py` is `from pico_reader import *\nmain()`. The regex still matches `main()` on its own line. This works unchanged.

---

## Verification

1. Start simulator: `cd simulator && npm run dev`
2. Open browser — simulator should load without errors
3. Console should show "Starting code.py..." and books loading
4. Menu should display, book selection and reading should work
5. Save/load should work (check browser localStorage)

---

## What this does NOT include

- Settings mirroring to localStorage (settings.txt in `/saves/` is already caught by the existing save-file mirroring in `_patched_save_place` — but only if save_settings writes to `saves/settings.txt`, which it does)
- State tracker updates for new features (Phase 6)
- New skin or animation support (Phases 3, 5)

---

## Task order

1. Update `worker.ts` to add `picoModules` list and fetch/mount loop
2. Start simulator, verify no console errors
3. Test menu navigation, book reading, save/load
4. Commit
