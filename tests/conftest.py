import sys
import os
from types import ModuleType
from unittest.mock import MagicMock

# =============================================================================
# CircuitPython stubs — must run at module level (before test collection)
# =============================================================================

_shims_dir = os.path.join(os.path.dirname(__file__), '..', 'simulator', 'public', 'shims')
_shims_dir = os.path.abspath(_shims_dir)
_firmware_dir = os.path.join(os.path.dirname(__file__), '..', 'firmware')
_firmware_dir = os.path.abspath(_firmware_dir)

# Add firmware dir to END of path so `from pico_reader.X import Y` works
# but stdlib `code` module isn't shadowed by firmware/code.py
sys.path.append(_firmware_dir)

# board — needs GP* pin attributes (constants.py imports it)
_board = ModuleType('board')
for _i in range(28):
    setattr(_board, 'GP{}'.format(_i), 'GP{}'.format(_i))
sys.modules['board'] = _board

# Simple MagicMock stubs for hardware modules
for _mod_name in ['digitalio', 'busio', 'sdcardio', 'storage',
                  'rotaryio', 'keypad', 'pwmio']:
    sys.modules[_mod_name] = MagicMock()

# displayio + adafruit libs — reuse simulator shims if available
if os.path.isdir(_shims_dir):
    sys.path.insert(0, _shims_dir)

    # _bridge is needed by displayio shim but uses js module — stub it
    _bridge = ModuleType('_bridge')
    _bridge.post_message = lambda msg: None
    sys.modules['_bridge'] = _bridge

    import displayio as _displayio
    sys.modules['displayio'] = _displayio

    import adafruit_display_text
    import adafruit_display_text.label
    sys.modules['adafruit_display_text'] = adafruit_display_text
    sys.modules['adafruit_display_text.label'] = adafruit_display_text.label

    import adafruit_bitmap_font
    import adafruit_bitmap_font.bitmap_font
    sys.modules['adafruit_bitmap_font'] = adafruit_bitmap_font
    sys.modules['adafruit_bitmap_font.bitmap_font'] = adafruit_bitmap_font.bitmap_font

    import adafruit_display_shapes
    import adafruit_display_shapes.rect
    sys.modules['adafruit_display_shapes'] = adafruit_display_shapes
    sys.modules['adafruit_display_shapes.rect'] = adafruit_display_shapes.rect

    sys.modules['adafruit_st7735r'] = MagicMock()
else:
    for _mod_name in ['displayio', 'adafruit_st7735r',
                      'adafruit_display_text', 'adafruit_display_text.label',
                      'adafruit_bitmap_font', 'adafruit_bitmap_font.bitmap_font',
                      'adafruit_display_shapes', 'adafruit_display_shapes.rect']:
        sys.modules[_mod_name] = MagicMock()

# =============================================================================
# Fixtures
# =============================================================================

import pytest
from pico_reader.utils import parse_book_filename


@pytest.fixture
def book_reader_env(tmp_path, monkeypatch):
    """Set up environment for BookReader tests with redirected file paths."""
    books_dir = tmp_path / "sd" / "books"
    books_dir.mkdir(parents=True)
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    # Monkeypatch open to redirect /sd/books/ to tmp_path/sd/books/
    real_open = open

    def patched_open(path, *args, **kwargs):
        if isinstance(path, str) and path.startswith('/sd/books/'):
            path = str(books_dir / path[len('/sd/books/'):])
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr('builtins.open', patched_open)

    return tmp_path, books_dir, saves_dir


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
