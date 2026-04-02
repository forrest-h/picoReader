"""Walker animation -- a 5x5 sprite that walks across the bottom of the screen.

Position tracks reading progress; animation speed varies with WPM.
Frames: 0-1 walk (<=150), 2-3 jog (150-300), 4-5 run (300+).
"""
import displayio

SPRITE_W = 5
SPRITE_H = 5
FRAME_COUNT = 6
SHEET_W = SPRITE_W * FRAME_COUNT  # 30

# Display geometry
DISPLAY_W = 160
Y_POS = 128 - 6  # 1px above bottom


def _build_sheet():
    """Create a 30x5 bitmap with 6 frames of a stick-figure walker.

    Each 5x5 frame uses palette index 1 for the sprite pixels.
    Frame 0-1: walk cycle
    Frame 2-3: jog cycle
    Frame 4-5: run cycle
    """
    bmp = displayio.Bitmap(SHEET_W, SPRITE_H, 2)

    # Frame 0 -- walk A (standing, left foot forward)
    _draw_pixels(bmp, 0, [
        (2, 0),              # head
        (1, 1), (2, 1), (3, 1),  # shoulders
        (2, 2),              # torso
        (1, 3), (3, 3),      # thighs
        (0, 4), (4, 4),      # feet apart
    ])

    # Frame 1 -- walk B (standing, right foot forward)
    _draw_pixels(bmp, 1, [
        (2, 0),
        (1, 1), (2, 1), (3, 1),
        (2, 2),
        (1, 3), (3, 3),
        (1, 4), (3, 4),      # feet closer
    ])

    # Frame 2 -- jog A (leaning, stride wide)
    _draw_pixels(bmp, 2, [
        (3, 0),              # head shifted forward
        (2, 1), (3, 1),      # shoulders
        (2, 2), (3, 2),      # torso lean
        (1, 3), (4, 3),      # wide stride
        (0, 4), (4, 4),      # feet
    ])

    # Frame 3 -- jog B (leaning, feet passing)
    _draw_pixels(bmp, 3, [
        (3, 0),
        (2, 1), (3, 1),
        (2, 2), (3, 2),
        (2, 3), (3, 3),      # legs together
        (1, 4), (4, 4),
    ])

    # Frame 4 -- run A (full lean, airborne feel)
    _draw_pixels(bmp, 4, [
        (3, 0), (4, 0),      # head + motion
        (2, 1), (3, 1),
        (2, 2),
        (1, 3), (4, 3),
        (0, 4), (4, 4),
    ])

    # Frame 5 -- run B (full lean, opposite)
    _draw_pixels(bmp, 5, [
        (3, 0), (4, 0),
        (2, 1), (3, 1),
        (3, 2),
        (1, 3), (4, 3),
        (1, 4), (4, 4),
    ])

    return bmp


def _draw_pixels(bmp, frame, pixels):
    """Set pixels for a single 5x5 frame in the sprite sheet."""
    x_off = frame * SPRITE_W
    for px, py in pixels:
        bmp[x_off + px, py] = 1


def _frame_for_wpm(wpm, tick_count):
    """Return frame index based on WPM and alternating tick."""
    alt = tick_count % 2
    if wpm <= 150:
        return 0 + alt       # walk: 0-1
    elif wpm <= 300:
        return 2 + alt       # jog: 2-3
    else:
        return 4 + alt       # run: 4-5


def _x_for_progress(progress):
    """Return x-position from progress (0.0 to 1.0)."""
    return int(progress * (DISPLAY_W - SPRITE_W))


class Animation:
    def __init__(self):
        self._tg = None
        self._palette = None
        self._tick_count = 0

    def build(self, display):
        """Create sprite sheet and return list with one TileGrid element."""
        sheet = _build_sheet()
        self._palette = displayio.Palette(2)
        self._palette[0] = 0x000000  # transparent (matches bg)
        self._palette[1] = 0x7c7c7c  # default highlight

        self._tg = displayio.TileGrid(
            sheet,
            pixel_shader=self._palette,
            x=0,
            y=Y_POS,
            tile_width=SPRITE_W,
            tile_height=SPRITE_H,
        )
        self._tg[0] = 0
        self._tick_count = 0
        return [self._tg]

    def tick(self, state, book, display):
        """Update walker position and frame each word tick."""
        if self._tg is None:
            return

        # Position from book progress
        progress = 0.0
        if book.total_lines > 0:
            progress = min(1.0, book.line_num / book.total_lines)
        base_x = _x_for_progress(progress)

        # Add wobble so walker visibly walks even with sub-pixel progress
        self._tick_count += 1
        wobble = 1 if self._tick_count % 2 == 0 else -1
        self._tg.x = max(0, min(DISPLAY_W - SPRITE_W, base_x + wobble))

        # Frame from WPM
        self._tg[0] = _frame_for_wpm(state.wpm, self._tick_count)

        # Match skin highlight color if available
        if hasattr(display, 'skin') and hasattr(display.skin, 'get_highlight_color'):
            self._palette[1] = display.skin.get_highlight_color()

    def destroy(self):
        """Release references."""
        self._tg = None
        self._palette = None
        self._tick_count = 0
