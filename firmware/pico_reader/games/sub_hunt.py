import time
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.line import Line
from ..constants import DISPLAY_WIDTH, DISPLAY_HEIGHT, BTN_CENTER, BTN_UP

# Display is BGR format
_BG_COLOR = 0x4b2500       # dark ocean blue (BGR: 0x00254b)
_SURFACE_COLOR = 0x7a5a32  # lighter blue-green
_SHIP_COLOR = 0x8c8c8c     # gray
_SUB_COLORS = [0x3244a0, 0x2838b0, 0x1e2cc0]  # reddish tones per depth (BGR)
_CHARGE_COLOR = 0x00ffff    # yellow (BGR)
_TEXT_COLOR = 0xe7e7e7
_FLOOR_COLOR = 0x284060     # brownish seabed (BGR)

# Layout
_SURFACE_Y = 16
_SHIP_Y = 10
_SHIP_W = 12
_SHIP_H = 4
_DEPTH_BANDS = [30, 58, 86]  # y positions for 3 depth bands
_DEPTH_SCORES = [10, 20, 30]
_SUB_H = 6
_CHARGE_SIZE = 3
_CHARGE_SPEED = 2       # pixels per tick
_MAX_CHARGES = 2
_MAX_SUBS = 5
_FLOOR_Y = 120

# Difficulty
_BASE_SPAWN_INTERVAL = 1.5  # seconds
_MIN_SPAWN_INTERVAL = 0.4
_BASE_SUB_SPEED = 0.8       # pixels per tick (float for fractional movement)
_SPEED_RAMP = 0.1           # speed increase per 100 points


class SubHuntGame:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._score = 0
        self._paused = False
        self._game_over = False

        from . import load_high_score
        self._high_score = load_high_score('sub_hunt')

        # Background
        bg_bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        bg_pal = displayio.Palette(1)
        bg_pal[0] = _BG_COLOR
        self._group.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))

        # Sea floor
        self._group.append(Rect(0, _FLOOR_Y, DISPLAY_WIDTH, DISPLAY_HEIGHT - _FLOOR_Y,
                                fill=_FLOOR_COLOR))

        # Surface line
        self._group.append(Line(0, _SURFACE_Y, DISPLAY_WIDTH - 1, _SURFACE_Y,
                                color=_SURFACE_COLOR))

        # Ship
        ship_x = DISPLAY_WIDTH // 2 - _SHIP_W // 2
        self._ship = Rect(ship_x, _SHIP_Y, _SHIP_W, _SHIP_H, fill=_SHIP_COLOR)
        self._ship_x = ship_x
        self._group.append(self._ship)

        # Score label
        self._score_lbl = label.Label(self._font, text="Score: 0",
                                      color=_TEXT_COLOR, base_alignment=True)
        self._score_lbl.anchor_point = (0.0, 0.0)
        self._score_lbl.anchored_position = (2, 2)
        self._group.append(self._score_lbl)

        # High score label
        self._hi_lbl = label.Label(self._font, text="Hi: {}".format(self._high_score),
                                   color=_TEXT_COLOR, base_alignment=True)
        self._hi_lbl.anchor_point = (1.0, 0.0)
        self._hi_lbl.anchored_position = (DISPLAY_WIDTH - 2, 2)
        self._group.append(self._hi_lbl)

        # Pause label (hidden initially)
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

        # Dynamic entity lists
        self._subs = []       # list of (rect, x_float, speed, depth_idx, direction, width)
        self._charges = []    # list of (rect, y_float)

        self._last_spawn = time.monotonic()
        self._last_tick = time.monotonic()
        self._spawn_interval = _BASE_SPAWN_INTERVAL

    def get_group(self):
        return self._group

    def handle_button(self, button):
        if self._game_over:
            if button == BTN_CENTER or button == BTN_UP:
                return 'quit'
            return None

        if button == BTN_UP:
            if self._paused:
                # Second UP = quit
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
                self._last_tick = time.monotonic()
                return None
            # Drop depth charge
            if len(self._charges) < _MAX_CHARGES:
                cx = self._ship_x + _SHIP_W // 2 - _CHARGE_SIZE // 2
                cy = _SURFACE_Y + 2
                charge_rect = Rect(cx, cy, _CHARGE_SIZE, _CHARGE_SIZE,
                                   fill=_CHARGE_COLOR)
                self._group.append(charge_rect)
                self._charges.append((charge_rect, float(cy)))
            return None

        return None

    def handle_encoder(self, direction):
        if self._paused or self._game_over:
            return None
        step = 4
        self._ship_x = max(0, min(DISPLAY_WIDTH - _SHIP_W,
                                  self._ship_x + direction * step))
        self._ship.x = self._ship_x
        return None

    def tick(self, now):
        if self._paused or self._game_over:
            return False

        dt = now - self._last_tick
        if dt < 0.03:  # ~30fps cap
            return False
        self._last_tick = now

        needs_refresh = False

        # Difficulty scaling
        level = self._score // 100
        self._spawn_interval = max(_MIN_SPAWN_INTERVAL,
                                   _BASE_SPAWN_INTERVAL - level * 0.15)
        speed_bonus = level * _SPEED_RAMP

        # Spawn subs
        if len(self._subs) < _MAX_SUBS and now - self._last_spawn >= self._spawn_interval:
            self._spawn_sub(speed_bonus)
            self._last_spawn = now

        # Move subs
        for i in range(len(self._subs) - 1, -1, -1):
            rect, x_f, speed, depth_idx, direction, sub_w = self._subs[i]
            x_f += speed * direction
            rect.x = int(x_f)

            # Off screen?
            if direction > 0 and x_f > DISPLAY_WIDTH + 10:
                self._remove_sub(i)
                needs_refresh = True
                continue
            if direction < 0 and x_f < -sub_w - 10:
                self._remove_sub(i)
                needs_refresh = True
                continue

            self._subs[i] = (rect, x_f, speed, depth_idx, direction, sub_w)
            needs_refresh = True

        # Move charges
        for i in range(len(self._charges) - 1, -1, -1):
            rect, y_f = self._charges[i]
            y_f += _CHARGE_SPEED
            rect.y = int(y_f)

            # Hit floor?
            if y_f >= _FLOOR_Y:
                self._remove_charge(i)
                needs_refresh = True
                continue

            # Check collision with subs
            hit = False
            for j in range(len(self._subs) - 1, -1, -1):
                s_rect, s_x, s_speed, s_depth, s_dir, sub_w = self._subs[j]
                if (int(y_f) + _CHARGE_SIZE >= s_rect.y and
                    int(y_f) <= s_rect.y + _SUB_H and
                    rect.x + _CHARGE_SIZE >= int(s_x) and
                    rect.x <= int(s_x) + sub_w):
                    # Hit!
                    self._score += _DEPTH_SCORES[s_depth]
                    self._score_lbl.text = "Score: {}".format(self._score)
                    if self._score > self._high_score:
                        self._high_score = self._score
                        self._hi_lbl.text = "Hi: {}".format(self._high_score)
                    self._remove_sub(j)
                    self._remove_charge(i)
                    hit = True
                    needs_refresh = True
                    break

            if not hit:
                self._charges[i] = (rect, y_f)
                needs_refresh = True

        return needs_refresh

    def _spawn_sub(self, speed_bonus):
        import random
        depth_idx = random.randint(0, 2)
        y = _DEPTH_BANDS[depth_idx]
        # Deeper subs are wider and slower
        widths = [14, 18, 24]
        base_speeds = [1.2, 0.9, 0.6]
        w = widths[depth_idx]
        speed = base_speeds[depth_idx] + speed_bonus

        direction = 1 if random.randint(0, 1) else -1
        if direction > 0:
            x = -w
        else:
            x = DISPLAY_WIDTH

        sub_rect = Rect(int(x), y, w, _SUB_H, fill=_SUB_COLORS[depth_idx])
        self._group.append(sub_rect)
        self._subs.append((sub_rect, float(x), speed, depth_idx, direction, w))

    def _remove_sub(self, index):
        rect = self._subs[index][0]
        try:
            self._group.remove(rect)
        except ValueError:
            pass
        self._subs.pop(index)

    def _remove_charge(self, index):
        rect = self._charges[index][0]
        try:
            self._group.remove(rect)
        except ValueError:
            pass
        self._charges.pop(index)

    def _end_game(self):
        self._game_over = True
        self._pause_lbl.text = "GAME OVER"
        self._pause_hint.text = "Score: {} Hi: {}".format(self._score, self._high_score)

    def destroy(self):
        from . import save_high_score
        if self._score > 0:
            save_high_score('sub_hunt', self._high_score)
        for rect, *_ in self._subs:
            try:
                self._group.remove(rect)
            except ValueError:
                pass
        for rect, _ in self._charges:
            try:
                self._group.remove(rect)
            except ValueError:
                pass
        self._subs.clear()
        self._charges.clear()
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
