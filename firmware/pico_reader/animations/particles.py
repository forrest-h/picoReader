"""Particles animation -- 4 drifting pixels in the display margins.

Uses pseudo-random positioning via time.monotonic() mod arithmetic
to avoid importing the random module. Particles drift down 1px per
tick and wrap to the top with a new pseudo-random X within margins.
"""
import time
import displayio

# Display geometry
DISPLAY_W = 160
DISPLAY_H = 128
MARGIN = 12  # particles stay within 12px of left/right edges

NUM_PARTICLES = 4

# Prime multipliers for pseudo-random spread
_PRIMES = [7, 13, 23, 37]


def _pseudo_x(seed, particle_id):
    """Return a pseudo-random x within the left or right margin.

    Even particle_ids use left margin (0..MARGIN-1),
    odd particle_ids use right margin (DISPLAY_W-MARGIN..DISPLAY_W-1).
    """
    val = int((seed * _PRIMES[particle_id % len(_PRIMES)]) * 1000) % MARGIN
    if particle_id % 2 == 0:
        return val  # left margin: 0..11
    else:
        return DISPLAY_W - MARGIN + val  # right margin: 148..159


class Animation:
    def __init__(self):
        self._grids = []
        self._palettes = []

    def build(self, display):
        """Create 4 single-pixel TileGrids and return them."""
        elements = []
        now = time.monotonic()
        for i in range(NUM_PARTICLES):
            bmp = displayio.Bitmap(2, 2, 2)
            bmp[0, 0] = 1
            bmp[1, 0] = 1
            bmp[0, 1] = 1
            bmp[1, 1] = 1
            pal = displayio.Palette(2)
            pal[0] = 0x000000  # transparent
            pal[1] = 0x7c7c7c  # default highlight
            self._palettes.append(pal)

            # Spread initial Y positions evenly
            start_y = (i * (DISPLAY_H // NUM_PARTICLES)) % DISPLAY_H
            start_x = _pseudo_x(now + i, i)

            tg = displayio.TileGrid(bmp, pixel_shader=pal, x=start_x, y=start_y)
            self._grids.append(tg)
            elements.append(tg)

        return elements

    def tick(self, state, book, display):
        """Drift all particles down 1px; wrap to top with new X."""
        now = time.monotonic()

        for i, tg in enumerate(self._grids):
            tg.y += 1
            if tg.y >= DISPLAY_H:
                tg.y = 0
                tg.x = _pseudo_x(now, i)

        # Match skin highlight color if available
        if hasattr(display, 'skin') and hasattr(display.skin, 'get_highlight_color'):
            color = display.skin.get_highlight_color()
            for pal in self._palettes:
                pal[1] = color

    def destroy(self):
        """Release references."""
        self._grids = []
        self._palettes = []
