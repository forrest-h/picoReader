import time
import random
import displayio
from adafruit_display_text import label
from ..constants import DISPLAY_WIDTH, DISPLAY_HEIGHT, BTN_CENTER, BTN_UP

# BGR colors
_BG_COLOR = 0x000000
_SNAKE_BODY = 0x00b000    # green (BGR)
_SNAKE_HEAD = 0x00ff40    # bright green (BGR)
_FOOD_COLOR = 0x4040ff    # red (BGR: 0xff4040 -> 0x4040ff)
_TEXT_COLOR = 0xe7e7e7

# Grid
_CELL = 6
_TOP_MARGIN = 10          # score area
_GRID_COLS = DISPLAY_WIDTH // _CELL          # 26
_GRID_ROWS = (DISPLAY_HEIGHT - _TOP_MARGIN) // _CELL  # 19

# Direction indices: UP=0, RIGHT=1, DOWN=2, LEFT=3
_DX = [0, 1, 0, -1]
_DY = [-1, 0, 1, 0]

# Speed
_START_INTERVAL = 0.200   # seconds per step
_SPEED_DEC = 0.003        # decrease per food eaten
_MIN_INTERVAL = 0.080


class SnakeGame:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._score = 0
        self._paused = False
        self._game_over = False

        from . import load_high_score
        self._high_score = load_high_score('snake')

        # Play-area bitmap with 4-color palette
        self._bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 4)
        self._pal = displayio.Palette(4)
        self._pal[0] = _BG_COLOR
        self._pal[1] = _SNAKE_BODY
        self._pal[2] = _SNAKE_HEAD
        self._pal[3] = _FOOD_COLOR
        self._group.append(displayio.TileGrid(self._bmp, pixel_shader=self._pal))

        # Score label
        self._score_lbl = label.Label(self._font, text="Score: 0",
                                      color=_TEXT_COLOR, base_alignment=True)
        self._score_lbl.anchor_point = (0.0, 0.0)
        self._score_lbl.anchored_position = (2, 1)
        self._group.append(self._score_lbl)

        # High score label
        self._hi_lbl = label.Label(self._font, text="Hi: {}".format(self._high_score),
                                   color=_TEXT_COLOR, base_alignment=True)
        self._hi_lbl.anchor_point = (1.0, 0.0)
        self._hi_lbl.anchored_position = (DISPLAY_WIDTH - 2, 1)
        self._group.append(self._hi_lbl)

        # Pause / game-over labels (hidden initially)
        self._pause_lbl = label.Label(self._font, text="", color=_TEXT_COLOR,
                                      base_alignment=False)
        self._pause_lbl.anchor_point = (0.5, 0.5)
        self._pause_lbl.anchored_position = (80, 60)
        self._group.append(self._pause_lbl)

        self._pause_hint = label.Label(self._font, text="", color=_TEXT_COLOR,
                                       base_alignment=False)
        self._pause_hint.anchor_point = (0.5, 0.5)
        self._pause_hint.anchored_position = (80, 75)
        self._group.append(self._pause_hint)

        # Snake state
        mid_c = _GRID_COLS // 2
        mid_r = _GRID_ROWS // 2
        # Body stored as list from tail to head
        self._body = [(mid_c - 2, mid_r), (mid_c - 1, mid_r), (mid_c, mid_r)]
        self._body_set = set(self._body)
        self._dir = 1           # facing RIGHT
        self._next_dir = 1

        # Draw initial snake
        for cx, cy in self._body[:-1]:
            self._fill_cell(cx, cy, 1)
        hx, hy = self._body[-1]
        self._fill_cell(hx, hy, 2)

        # Food
        self._food = None
        self._place_food()

        # Timing
        self._interval = _START_INTERVAL
        self._last_step = time.monotonic()

    def get_group(self):
        return self._group

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_button(self, button):
        if self._game_over:
            return 'quit'

        if button == BTN_UP:
            if self._paused:
                self._end_game()
                return None
            else:
                self._paused = True
                self._pause_lbl.text = "PAUSED"
                self._pause_hint.text = "C=resume U=quit"
                return None

        if button == BTN_CENTER:
            if self._paused:
                self._paused = False
                self._pause_lbl.text = ""
                self._pause_hint.text = ""
                self._last_step = time.monotonic()
                return None

        return None

    def handle_encoder(self, direction):
        if self._paused or self._game_over:
            return None
        # direction: +1 = CW (turn right), -1 = CCW (turn left)
        candidate = (self._dir + direction) % 4
        # Prevent 180-degree reversal
        if (candidate + 2) % 4 != self._dir:
            self._next_dir = candidate
        return None

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def tick(self, now):
        if self._paused or self._game_over:
            return False

        if now - self._last_step < self._interval:
            return False
        self._last_step = now

        # Commit direction
        self._dir = self._next_dir

        # Compute new head
        hx, hy = self._body[-1]
        nx = hx + _DX[self._dir]
        ny = hy + _DY[self._dir]

        # Wall collision
        if nx < 0 or nx >= _GRID_COLS or ny < 0 or ny >= _GRID_ROWS:
            self._end_game()
            return True

        # Self collision
        if (nx, ny) in self._body_set:
            self._end_game()
            return True

        ate_food = (nx, ny) == self._food

        # Old head becomes body color
        self._fill_cell(hx, hy, 1)

        # Add new head
        self._body.append((nx, ny))
        self._body_set.add((nx, ny))
        self._fill_cell(nx, ny, 2)

        if ate_food:
            # Score
            self._score += 10
            self._score_lbl.text = "Score: {}".format(self._score)
            if self._score > self._high_score:
                self._high_score = self._score
                self._hi_lbl.text = "Hi: {}".format(self._high_score)
            # Speed up
            self._interval = max(_MIN_INTERVAL,
                                 self._interval - _SPEED_DEC)
            # New food
            self._place_food()
        else:
            # Remove tail
            tx, ty = self._body.pop(0)
            self._body_set.discard((tx, ty))
            self._fill_cell(tx, ty, 0)

        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fill_cell(self, cx, cy, color_idx):
        """Paint a single grid cell on the bitmap."""
        px = cx * _CELL
        py = cy * _CELL + _TOP_MARGIN
        bmp = self._bmp
        for y in range(py, min(py + _CELL, DISPLAY_HEIGHT)):
            for x in range(px, min(px + _CELL, DISPLAY_WIDTH)):
                bmp[x, y] = color_idx

    def _place_food(self):
        """Place food on a random empty cell using retry loop."""
        total = _GRID_COLS * _GRID_ROWS
        if len(self._body_set) >= total:
            self._end_game()
            return
        for _ in range(200):
            fx = random.randint(0, _GRID_COLS - 1)
            fy = random.randint(0, _GRID_ROWS - 1)
            if (fx, fy) not in self._body_set:
                self._food = (fx, fy)
                self._fill_cell(fx, fy, 3)
                return

    def _end_game(self):
        self._game_over = True
        self._pause_lbl.text = "GAME OVER"
        self._pause_hint.text = "Score: {} Hi: {}".format(self._score, self._high_score)

    def destroy(self):
        from . import save_high_score
        if self._score > 0:
            save_high_score('snake', self._high_score)
        while len(self._group) > 0:
            self._group.pop()
        self._bmp = None
        self._pal = None
        self._group = None
