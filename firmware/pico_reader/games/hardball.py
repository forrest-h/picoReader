import time
import random
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..constants import DISPLAY_WIDTH, DISPLAY_HEIGHT, BTN_CENTER, BTN_UP

# BGR colors
_BG = 0x000000
_PADDLE_C = 0xe7e7e7
_BALL_C = 0xe7e7e7
_TEXT_C = 0xe7e7e7

# Layout
_PADDLE_W = 24
_PADDLE_H = 4
_PADDLE_Y = 122
_BALL_SZ = 3
_COLS = 8
_BK_W = 18
_BK_H = 7
_BK_GAP = 1
_BK_STRIDE = _BK_H + _BK_GAP
_BK_X0 = (DISPLAY_WIDTH - _COLS * (_BK_W + _BK_GAP) + _BK_GAP) // 2
_BK_Y0 = 14
_CEILING = 12

# Ball physics
_SPEED = 1.5
_RAMP_MULT = 0.5    # ball gets 50% faster over course of a level
_RAMP_TIME = 45.0   # seconds to reach max ramp

# Endless mode
_DESC_START = 5.0
_DESC_MIN = 2.0
_DESC_ACCEL = 0.15

# Transition
_TRANS_TIME = 1.5

# 10 level layouts: tuple of row bitmasks (bit N = column N)
_LEVELS = (
    (0xFF, 0xFF, 0xFF),                                     # 1: Classic
    (0xAA, 0x55, 0xAA, 0x55, 0xAA),                        # 2: Checkerboard
    (0x18, 0x3C, 0x7E, 0xFF, 0x7E, 0x3C, 0x18),           # 3: Diamond
    (0xF0, 0x78, 0x3C, 0x1E, 0x0F, 0x1E, 0x3C, 0x78),    # 4: Zigzag
    (0x18, 0x18, 0xFF, 0xFF, 0x18, 0x18),                  # 5: Cross
    (0xE7, 0xE7, 0xE7, 0xE7, 0xE7, 0xE7),                 # 6: Walls
    (0x66, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C, 0x18),           # 7: Heart
    (0xAA, 0xFF, 0xFF, 0xC3, 0xC3, 0xFF, 0xFF),           # 8: Fortress
    (0xFF, 0x7E, 0x3C, 0x18, 0x18, 0x3C, 0x7E, 0xFF),    # 9: Hourglass
    (0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF),     # 10: Gauntlet
)

# BGR color palettes per level (4 colors cycled across rows)
_PALETTES = (
    (0x0000FF, 0x0080FF, 0x00FFFF, 0x00FF00),  # 1: red-orange-yellow-green
    (0xFF0000, 0xFFFF00, 0xFF0000, 0xFFFF00),  # 2: blue, cyan
    (0x0000FF, 0x0040C0, 0x0080FF, 0x00C0FF),  # 3: red gradient
    (0xFF00FF, 0xFF0080, 0xFF0000, 0xFF0080),  # 4: magenta-purple-blue
    (0x00FFFF, 0x00FF00, 0x00FFFF, 0x00FF00),  # 5: yellow, green
    (0x0040A0, 0x0060C0, 0x0040A0, 0x0060C0),  # 6: dark warm
    (0x8080FF, 0x4040FF, 0x0000FF, 0x4040FF),  # 7: pink-red heart
    (0x808080, 0xA0A0A0, 0xC0C0C0, 0xA0A0A0),  # 8: stone gray
    (0xFF6000, 0xFFC000, 0xFF6000, 0xFFC000),  # 9: blue-teal
    (0x0000FF, 0x00FF00, 0xFF0000, 0x00FFFF),  # 10: rainbow
)

_ENDLESS_C = (0x0000FF, 0x00FF00, 0xFF0000, 0x00FFFF, 0xFF00FF, 0x0080FF)


class HardballGame:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._score = 0
        self._balls_left = 3
        self._level = 1
        self._paused = False
        self._game_over = False
        self._ball_launched = False
        self._transitioning = False
        self._transition_end = 0.0
        self._endless = False
        self._descend_count = 0
        self._descend_interval = _DESC_START
        self._last_descend = 0.0
        self._level_start_time = time.monotonic()

        from . import load_high_score
        self._high_score = load_high_score('hardball')

        # [0] Background
        bg_bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        bg_pal = displayio.Palette(1)
        bg_pal[0] = _BG
        self._group.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))

        # [1] Score label
        self._score_lbl = label.Label(self._font, text="Score: 0",
                                      color=_TEXT_C, base_alignment=True)
        self._score_lbl.anchor_point = (0.0, 0.0)
        self._score_lbl.anchored_position = (2, 2)
        self._group.append(self._score_lbl)

        # [2] Level label
        self._level_lbl = label.Label(self._font, text="Lv 1",
                                      color=_TEXT_C, base_alignment=True)
        self._level_lbl.anchor_point = (0.5, 0.0)
        self._level_lbl.anchored_position = (80, 2)
        self._group.append(self._level_lbl)

        # [3] Balls label
        self._balls_lbl = label.Label(self._font, text="Ball: 3",
                                      color=_TEXT_C, base_alignment=True)
        self._balls_lbl.anchor_point = (1.0, 0.0)
        self._balls_lbl.anchored_position = (DISPLAY_WIDTH - 2, 2)
        self._group.append(self._balls_lbl)

        # [4] Center message (pause/game over/level transition)
        self._msg_lbl = label.Label(self._font, text="", color=_TEXT_C,
                                    base_alignment=False)
        self._msg_lbl.anchor_point = (0.5, 0.5)
        self._msg_lbl.anchored_position = (80, 80)
        self._group.append(self._msg_lbl)

        # [5] Hint message
        self._msg_hint = label.Label(self._font, text="", color=_TEXT_C,
                                     base_alignment=False)
        self._msg_hint.anchor_point = (0.5, 0.5)
        self._msg_hint.anchored_position = (80, 95)
        self._group.append(self._msg_hint)

        # [6] Paddle
        self._paddle_x = DISPLAY_WIDTH // 2 - _PADDLE_W // 2
        self._paddle = Rect(self._paddle_x, _PADDLE_Y, _PADDLE_W, _PADDLE_H,
                            fill=_PADDLE_C)
        self._group.append(self._paddle)

        # [7] Ball
        self._ball_x = float(self._paddle_x + _PADDLE_W // 2 - _BALL_SZ // 2)
        self._ball_y = float(_PADDLE_Y - _BALL_SZ - 1)
        self._ball_dx = _SPEED
        self._ball_dy = -_SPEED
        self._ball = Rect(int(self._ball_x), int(self._ball_y),
                          _BALL_SZ, _BALL_SZ, fill=_BALL_C)
        self._group.append(self._ball)

        # Bricks (dynamic, appended after fixed elements)
        self._bricks = []
        self._build_level(1)

        self._last_tick = time.monotonic()

    def get_group(self):
        return self._group

    # --- Input ---

    def handle_button(self, button):
        if self._game_over:
            if button == BTN_CENTER or button == BTN_UP:
                return 'quit'
            return None

        if self._transitioning:
            return None

        if button == BTN_UP:
            if self._paused:
                self._end_game()
                return None
            self._paused = True
            self._msg_lbl.text = "PAUSED"
            self._msg_hint.text = "C=resume U=quit"
            return None

        if button == BTN_CENTER:
            if self._paused:
                self._paused = False
                self._msg_lbl.text = ""
                self._msg_hint.text = ""
                self._last_tick = time.monotonic()
                return None
            if not self._ball_launched:
                self._ball_launched = True
                self._ball_dx = _SPEED
                self._ball_dy = -_SPEED
                self._level_start_time = time.monotonic()
                return None

        return None

    def handle_encoder(self, direction):
        if self._paused or self._game_over or self._transitioning:
            return None
        step = 4
        self._paddle_x = max(0, min(DISPLAY_WIDTH - _PADDLE_W,
                                    self._paddle_x + direction * step))
        self._paddle.x = self._paddle_x
        if not self._ball_launched:
            self._ball_x = float(self._paddle_x + _PADDLE_W // 2 - _BALL_SZ // 2)
            self._ball.x = int(self._ball_x)
        return None

    # --- Game loop ---

    def tick(self, now):
        # Handle level transition timer
        if self._transitioning:
            if now >= self._transition_end:
                self._transitioning = False
                self._msg_lbl.text = ""
                self._msg_hint.text = ""
            return False

        if self._paused or self._game_over or not self._ball_launched:
            return False

        dt = now - self._last_tick
        if dt < 0.02:
            return False
        self._last_tick = now

        # Speed ramp within level
        elapsed = now - self._level_start_time
        ramp = 1.0 + min(elapsed / _RAMP_TIME, 1.0) * _RAMP_MULT

        # Move ball with ramp
        self._ball_x += self._ball_dx * ramp
        self._ball_y += self._ball_dy * ramp

        bx = int(self._ball_x)
        by = int(self._ball_y)

        # Wall collisions
        if bx <= 0:
            self._ball_x = 0.0
            self._ball_dx = abs(self._ball_dx)
        elif bx >= DISPLAY_WIDTH - _BALL_SZ:
            self._ball_x = float(DISPLAY_WIDTH - _BALL_SZ)
            self._ball_dx = -abs(self._ball_dx)

        ceiling_bounced = False
        if by <= _CEILING:
            self._ball_y = float(_CEILING)
            self._ball_dy = abs(self._ball_dy)
            ceiling_bounced = True

        # Ball below paddle = lost
        if by >= DISPLAY_HEIGHT:
            self._balls_left -= 1
            self._balls_lbl.text = "Ball: {}".format(self._balls_left)
            if self._balls_left <= 0:
                self._end_game()
                return True
            self._reset_ball()
            return True

        # Paddle collision
        if (self._ball_dy > 0 and
            by + _BALL_SZ >= _PADDLE_Y and
            by + _BALL_SZ <= _PADDLE_Y + _PADDLE_H + 2 and
            bx + _BALL_SZ >= self._paddle_x and
            bx <= self._paddle_x + _PADDLE_W):

            self._ball_dy = -abs(self._ball_dy)
            self._ball_y = float(_PADDLE_Y - _BALL_SZ)
            hit_pos = (self._ball_x + _BALL_SZ / 2 - self._paddle_x) / _PADDLE_W
            angle = max(-0.8, min(0.8, (hit_pos - 0.5) * 2.0))
            self._ball_dx = _SPEED * angle
            dy_sq = _SPEED * _SPEED - self._ball_dx * self._ball_dx
            self._ball_dy = -(dy_sq ** 0.5) if dy_sq > 0 else -_SPEED * 0.6

        # Brick collisions (skip on ceiling bounce to prevent overlap trap)
        if not ceiling_bounced:
            for i in range(len(self._bricks) - 1, -1, -1):
                br = self._bricks[i][0]
                br_x = br.x
                br_y = br.y
                if (bx + _BALL_SZ >= br_x and bx <= br_x + _BK_W and
                    by + _BALL_SZ >= br_y and by <= br_y + _BK_H):
                    try:
                        self._group.remove(br)
                    except ValueError:
                        pass
                    self._bricks.pop(i)
                    self._score += 10
                    self._score_lbl.text = "Score: {}".format(self._score)
                    if self._score > self._high_score:
                        self._high_score = self._score
                    self._ball_dy = -self._ball_dy
                    if self._ball_dy < 0:
                        self._ball_y = float(br_y - _BALL_SZ)
                    else:
                        self._ball_y = float(br_y + _BK_H)
                    break

        # Minimum vertical speed
        if abs(self._ball_dy) < 0.3:
            self._ball_dy = 0.3 if self._ball_dy >= 0 else -0.3

        # Endless mode: descend bricks
        if self._endless and now - self._last_descend >= self._descend_interval:
            if self._descend_bricks():
                self._end_game()
                return True
            self._spawn_random_row(_BK_Y0)
            self._last_descend = now
            self._descend_count += 1
            self._descend_interval = max(_DESC_MIN,
                                         _DESC_START - self._descend_count * _DESC_ACCEL)

        # Check level clear
        if not self._bricks:
            if self._endless:
                self._spawn_random_row(_BK_Y0)
            elif self._level < 10:
                self._level += 1
                self._begin_transition("Level {}!".format(self._level))
                return True
            elif self._level == 10:
                self._level = 11
                self._begin_transition("Endless!")
                return True

        self._ball.x = int(self._ball_x)
        self._ball.y = int(self._ball_y)
        return True

    # --- Level management ---

    def _begin_transition(self, text):
        """Start a level transition with a text flash."""
        now = time.monotonic()
        self._transitioning = True
        self._transition_end = now + _TRANS_TIME
        self._msg_lbl.text = text
        self._msg_hint.text = ""
        self._reset_ball()
        if self._level <= 10:
            self._build_level(self._level)
            self._level_lbl.text = "Lv {}".format(self._level)
        else:
            self._start_endless()
            self._level_lbl.text = "Endless"

    def _build_level(self, level_num):
        """Build bricks from a level pattern (1-10)."""
        self._clear_bricks()
        pattern = _LEVELS[level_num - 1]
        colors = _PALETTES[level_num - 1]
        for row_idx, mask in enumerate(pattern):
            color = colors[row_idx % len(colors)]
            y = _BK_Y0 + row_idx * _BK_STRIDE
            for col in range(_COLS):
                if mask & (1 << col):
                    x = _BK_X0 + col * (_BK_W + _BK_GAP)
                    brick = Rect(x, y, _BK_W, _BK_H, fill=color)
                    self._group.append(brick)
                    self._bricks.append((brick, col, row_idx))

    def _start_endless(self):
        """Initialize endless mode."""
        self._endless = True
        self._descend_count = 0
        self._descend_interval = _DESC_START
        self._clear_bricks()
        for row_offset in range(3):
            y = _BK_Y0 + row_offset * _BK_STRIDE
            self._spawn_random_row(y)
        self._last_descend = time.monotonic() + _TRANS_TIME + 3.0

    def _spawn_random_row(self, y):
        """Spawn a row of random bricks at the given y position."""
        mask = random.randint(0, 255)
        if mask == 0:
            mask = 0xFF
        color = _ENDLESS_C[self._descend_count % len(_ENDLESS_C)]
        for col in range(_COLS):
            if mask & (1 << col):
                x = _BK_X0 + col * (_BK_W + _BK_GAP)
                brick = Rect(x, y, _BK_W, _BK_H, fill=color)
                self._group.append(brick)
                self._bricks.append((brick, col, 0))

    def _descend_bricks(self):
        """Move all bricks down one row. Returns True if any reached paddle."""
        for i in range(len(self._bricks)):
            rect = self._bricks[i][0]
            rect.y += _BK_STRIDE
            if rect.y + _BK_H >= _PADDLE_Y:
                return True
        return False

    def _clear_bricks(self):
        for rect, _c, _r in self._bricks:
            try:
                self._group.remove(rect)
            except ValueError:
                pass
        self._bricks = []

    def _reset_ball(self):
        self._ball_launched = False
        self._ball_x = float(self._paddle_x + _PADDLE_W // 2 - _BALL_SZ // 2)
        self._ball_y = float(_PADDLE_Y - _BALL_SZ - 1)
        self._ball.x = int(self._ball_x)
        self._ball.y = int(self._ball_y)
        self._ball_dx = _SPEED
        self._ball_dy = -_SPEED

    def _end_game(self):
        self._game_over = True
        self._msg_lbl.text = "GAME OVER"
        self._msg_hint.text = "Score: {} Hi: {}".format(self._score, self._high_score)

    def destroy(self):
        from . import save_high_score
        if self._score > 0:
            save_high_score('hardball', self._high_score)
        self._clear_bricks()
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
