import time
import random
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..constants import DISPLAY_WIDTH, DISPLAY_HEIGHT, BTN_CENTER, BTN_UP, BTN_LEFT, BTN_RIGHT

# BGR colors
_BG = 0x000000
_TEXT = 0xe7e7e7
_PLAYER_COLOR = 0xffcc00       # cyan-ish (BGR)
_BULLET_COLOR = 0x00ffff       # yellow (BGR)
_ALIEN_BULLET = 0x4040ff       # red (BGR)
_SHIELD_COLOR = 0x00b000       # green (BGR)
_MYSTERY_COLOR = 0xff00ff      # magenta (BGR)
_ROW_COLORS = [0x5050ff, 0x5050ff, 0x00b0b0, 0x00b0b0, 0x00b000]  # BGR per row
_ROW_POINTS = [30, 20, 20, 10, 10]

# Layout
_HUD_H = 10
_ALIEN_W = 6
_ALIEN_H = 5
_ALIEN_COLS = 8
_ALIEN_ROWS = 5
_ALIEN_TOTAL = _ALIEN_COLS * _ALIEN_ROWS
_ALIEN_SPC_X = 16
_ALIEN_SPC_Y = 12
_GRID_X0 = (DISPLAY_WIDTH - _ALIEN_COLS * _ALIEN_SPC_X) // 2
_GRID_Y0 = 20

_PLAYER_W = 8
_PLAYER_H = 4
_PLAYER_Y = 118
_PLAYER_SPEED_BTN = 4
_PLAYER_SPEED_ENC = 2

_BULLET_W = 1
_BULLET_H = 3
_BULLET_SPEED = 3
_ALIEN_BULLET_SPEED = 1.5
_MAX_ALIEN_BULLETS = 2

_SHIELD_W = 12
_SHIELD_H = 6
_SHIELD_Y = 106
_SHIELD_HP = 3
_NUM_SHIELDS = 4

_MYSTERY_W = 8
_MYSTERY_H = 3
_MYSTERY_Y = 12
_MYSTERY_INTERVAL = 20.0
_MYSTERY_SPEED = 1.0

_BASE_STEP_INTERVAL = 0.5
_MIN_STEP_INTERVAL = 0.05
_FORM_STEP_X = 2
_FORM_DROP_Y = 8
_ALIEN_FIRE_MIN = 1.0
_ALIEN_FIRE_MAX = 2.0


class SpaceInvadersGame:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._score = 0
        self._lives = 3
        self._level = 0
        self._paused = False
        self._game_over = False

        from . import load_high_score
        self._high_score = load_high_score('invaders')

        # Background
        bg_bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        bg_pal = displayio.Palette(1)
        bg_pal[0] = _BG
        self._group.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))

        # HUD labels
        self._score_lbl = label.Label(self._font, text="Score: 0",
                                      color=_TEXT, base_alignment=True)
        self._score_lbl.anchor_point = (0.0, 0.0)
        self._score_lbl.anchored_position = (2, 1)
        self._group.append(self._score_lbl)

        self._lives_lbl = label.Label(self._font, text="Lives: 3",
                                      color=_TEXT, base_alignment=True)
        self._lives_lbl.anchor_point = (1.0, 0.0)
        self._lives_lbl.anchored_position = (DISPLAY_WIDTH - 2, 1)
        self._group.append(self._lives_lbl)

        # Pause / game-over overlay
        self._msg_lbl = label.Label(self._font, text="", color=_TEXT,
                                    base_alignment=False)
        self._msg_lbl.anchor_point = (0.5, 0.5)
        self._msg_lbl.anchored_position = (80, 58)
        self._group.append(self._msg_lbl)

        self._hint_lbl = label.Label(self._font, text="", color=_TEXT,
                                     base_alignment=False)
        self._hint_lbl.anchor_point = (0.5, 0.5)
        self._hint_lbl.anchored_position = (80, 73)
        self._group.append(self._hint_lbl)

        # Player ship
        self._player_x = DISPLAY_WIDTH // 2 - _PLAYER_W // 2
        self._player = Rect(self._player_x, _PLAYER_Y, _PLAYER_W, _PLAYER_H,
                            fill=_PLAYER_COLOR)
        self._group.append(self._player)

        # Alien grid: list of [rect_or_None, row, col, alive]
        self._aliens = []
        self._alive_count = 0
        self._form_x = 0
        self._form_y = 0
        self._form_dir = 1  # +1 = right, -1 = left
        self._last_step = time.monotonic()
        self._spawn_aliens()

        # Shields: list of [rect, hp] or None
        self._shields = []
        self._spawn_shields()

        # Bullets
        self._player_bullet = None   # (rect, y_float) or None
        self._alien_bullets = []     # list of (rect, y_float)
        self._last_alien_fire = time.monotonic()
        self._next_fire_delay = random.uniform(_ALIEN_FIRE_MIN, _ALIEN_FIRE_MAX)

        # Mystery ship
        self._mystery = None         # (rect, x_float, direction) or None
        self._last_mystery = time.monotonic()

        self._last_tick = time.monotonic()

    def get_group(self):
        return self._group

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_button(self, button):
        if self._game_over:
            if button == BTN_CENTER or button == BTN_UP:
                return 'quit'
            return None

        if button == BTN_UP:
            if self._paused:
                self._end_game()
                return None
            self._paused = True
            self._msg_lbl.text = "PAUSED"
            self._hint_lbl.text = "C=resume U=quit"
            return None

        if button == BTN_CENTER:
            if self._paused:
                self._paused = False
                self._msg_lbl.text = ""
                self._hint_lbl.text = ""
                self._last_tick = time.monotonic()
                self._last_step = time.monotonic()
                return None
            self._fire_player()
            return None

        if button == BTN_LEFT:
            self._move_player(-_PLAYER_SPEED_BTN)
            return None

        if button == BTN_RIGHT:
            self._move_player(_PLAYER_SPEED_BTN)
            return None

        return None

    def handle_encoder(self, direction):
        if self._paused or self._game_over:
            return None
        self._move_player(direction * _PLAYER_SPEED_ENC)
        return None

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def tick(self, now):
        if self._paused or self._game_over:
            return False

        if now - self._last_tick < 0.033:  # ~30fps cap
            return False
        self._last_tick = now

        changed = False

        # Move alien formation
        step_interval = max(_MIN_STEP_INTERVAL,
                            _BASE_STEP_INTERVAL * (self._alive_count / _ALIEN_TOTAL))
        step_interval /= (1 + self._level * 0.15)
        if now - self._last_step >= step_interval:
            self._last_step = now
            self._step_aliens()
            changed = True

        # Player bullet
        if self._player_bullet is not None:
            rect, y_f = self._player_bullet
            y_f -= _BULLET_SPEED
            if y_f < 0:
                self._remove_rect(rect)
                self._player_bullet = None
            else:
                rect.y = int(y_f)
                self._player_bullet = (rect, y_f)
                # Check alien hits
                if self._check_bullet_alien(rect, int(y_f)):
                    self._remove_rect(rect)
                    self._player_bullet = None
                # Check mystery hit
                elif self._mystery and self._check_hit(
                        rect.x, int(y_f), _BULLET_W, _BULLET_H,
                        int(self._mystery[1]), _MYSTERY_Y, _MYSTERY_W, _MYSTERY_H):
                    pts = random.choice([50, 100, 150, 200, 300])
                    self._add_score(pts)
                    self._remove_rect(self._mystery[0])
                    self._remove_rect(rect)
                    self._mystery = None
                    self._player_bullet = None
            changed = True

        # Alien bullets - fire
        if now - self._last_alien_fire >= self._next_fire_delay:
            self._fire_alien()
            self._last_alien_fire = now
            self._next_fire_delay = random.uniform(_ALIEN_FIRE_MIN, _ALIEN_FIRE_MAX)

        # Alien bullets - move
        for i in range(len(self._alien_bullets) - 1, -1, -1):
            rect, y_f = self._alien_bullets[i]
            y_f += _ALIEN_BULLET_SPEED
            if y_f > DISPLAY_HEIGHT:
                self._remove_rect(rect)
                self._alien_bullets.pop(i)
                changed = True
                continue
            rect.y = int(y_f)
            self._alien_bullets[i] = (rect, y_f)
            # Hit player?
            if self._check_hit(rect.x, int(y_f), _BULLET_W, _BULLET_H,
                               self._player_x, _PLAYER_Y, _PLAYER_W, _PLAYER_H):
                self._remove_rect(rect)
                self._alien_bullets.pop(i)
                self._player_hit()
                changed = True
                continue
            # Hit shield?
            for si in range(len(self._shields)):
                s = self._shields[si]
                if s is None:
                    continue
                s_rect, hp = s
                sx = s_rect.x
                if self._check_hit(rect.x, int(y_f), _BULLET_W, _BULLET_H,
                                   sx, _SHIELD_Y, _SHIELD_W, _SHIELD_H):
                    self._remove_rect(rect)
                    self._alien_bullets.pop(i)
                    hp -= 1
                    if hp <= 0:
                        self._remove_rect(s_rect)
                        self._shields[si] = None
                    else:
                        self._shields[si] = (s_rect, hp)
                    changed = True
                    break
            changed = True

        # Player bullet vs shields
        if self._player_bullet is not None:
            rect, y_f = self._player_bullet
            for si in range(len(self._shields)):
                s = self._shields[si]
                if s is None:
                    continue
                s_rect, hp = s
                if self._check_hit(rect.x, int(y_f), _BULLET_W, _BULLET_H,
                                   s_rect.x, _SHIELD_Y, _SHIELD_W, _SHIELD_H):
                    self._remove_rect(rect)
                    self._player_bullet = None
                    hp -= 1
                    if hp <= 0:
                        self._remove_rect(s_rect)
                        self._shields[si] = None
                    else:
                        self._shields[si] = (s_rect, hp)
                    changed = True
                    break

        # Mystery ship
        if self._mystery is None:
            if now - self._last_mystery >= _MYSTERY_INTERVAL:
                self._spawn_mystery()
                self._last_mystery = now
                changed = True
        else:
            m_rect, x_f, m_dir = self._mystery
            x_f += _MYSTERY_SPEED * m_dir
            if x_f < -_MYSTERY_W - 5 or x_f > DISPLAY_WIDTH + 5:
                self._remove_rect(m_rect)
                self._mystery = None
            else:
                m_rect.x = int(x_f)
                self._mystery = (m_rect, x_f, m_dir)
            changed = True

        # Level clear
        if self._alive_count == 0:
            self._level += 1
            self._form_x = 0
            self._form_y = 0
            self._form_dir = 1
            self._spawn_aliens()
            self._spawn_shields()
            changed = True

        return changed

    # ------------------------------------------------------------------
    # Alien formation
    # ------------------------------------------------------------------
    def _spawn_aliens(self):
        # Remove old rects
        for entry in self._aliens:
            if entry[0] is not None:
                self._remove_rect(entry[0])
        self._aliens = []
        self._alive_count = 0
        for row in range(_ALIEN_ROWS):
            for col in range(_ALIEN_COLS):
                x = _GRID_X0 + col * _ALIEN_SPC_X
                y = _GRID_Y0 + row * _ALIEN_SPC_Y
                r = Rect(x, y, _ALIEN_W, _ALIEN_H, fill=_ROW_COLORS[row])
                self._group.append(r)
                self._aliens.append([r, row, col, True])
                self._alive_count += 1

    def _step_aliens(self):
        # Determine rightmost and leftmost alive alien column positions
        min_x = DISPLAY_WIDTH
        max_x = 0
        max_alien_y = 0
        for entry in self._aliens:
            if not entry[3]:
                continue
            _, row, col, _ = entry
            ax = _GRID_X0 + col * _ALIEN_SPC_X + self._form_x
            min_x = min(min_x, ax)
            max_x = max(max_x, ax + _ALIEN_W)
            ay = _GRID_Y0 + row * _ALIEN_SPC_Y + self._form_y
            max_alien_y = max(max_alien_y, ay + _ALIEN_H)

        # Check if formation reached player row
        if max_alien_y >= _PLAYER_Y:
            self._end_game()
            return

        drop = False
        if self._form_dir > 0 and max_x + _FORM_STEP_X > DISPLAY_WIDTH:
            drop = True
        elif self._form_dir < 0 and min_x - _FORM_STEP_X < 0:
            drop = True

        if drop:
            self._form_y += _FORM_DROP_Y
            self._form_dir = -self._form_dir
        else:
            self._form_x += _FORM_STEP_X * self._form_dir

        # Update rect positions
        for entry in self._aliens:
            if not entry[3]:
                continue
            rect, row, col, _ = entry
            rect.x = _GRID_X0 + col * _ALIEN_SPC_X + self._form_x
            rect.y = _GRID_Y0 + row * _ALIEN_SPC_Y + self._form_y

    def _check_bullet_alien(self, b_rect, b_y):
        bx = b_rect.x
        for i, entry in enumerate(self._aliens):
            if not entry[3]:
                continue
            a_rect, row, col, _ = entry
            if self._check_hit(bx, b_y, _BULLET_W, _BULLET_H,
                               a_rect.x, a_rect.y, _ALIEN_W, _ALIEN_H):
                self._add_score(_ROW_POINTS[row])
                self._remove_rect(a_rect)
                entry[0] = None
                entry[3] = False
                self._alive_count -= 1
                return True
        return False

    def _fire_alien(self):
        if len(self._alien_bullets) >= _MAX_ALIEN_BULLETS:
            return
        # Collect bottom-row alive aliens per column
        bottom = {}
        for entry in self._aliens:
            if not entry[3]:
                continue
            _, row, col, _ = entry
            if col not in bottom or row > bottom[col][1]:
                bottom[col] = (entry, row)
        if not bottom:
            return
        keys = list(bottom.keys())
        shooter_entry = bottom[keys[random.randint(0, len(keys) - 1)]][0]
        sx = shooter_entry[0].x + _ALIEN_W // 2
        sy = shooter_entry[0].y + _ALIEN_H
        br = Rect(sx, sy, _BULLET_W, _BULLET_H, fill=_ALIEN_BULLET)
        self._group.append(br)
        self._alien_bullets.append((br, float(sy)))

    # ------------------------------------------------------------------
    # Player
    # ------------------------------------------------------------------
    def _move_player(self, dx):
        self._player_x = max(0, min(DISPLAY_WIDTH - _PLAYER_W,
                                    self._player_x + dx))
        self._player.x = self._player_x

    def _fire_player(self):
        if self._player_bullet is not None:
            return
        bx = self._player_x + _PLAYER_W // 2
        by = _PLAYER_Y - _BULLET_H
        br = Rect(bx, by, _BULLET_W, _BULLET_H, fill=_BULLET_COLOR)
        self._group.append(br)
        self._player_bullet = (br, float(by))

    def _player_hit(self):
        self._lives -= 1
        self._lives_lbl.text = "Lives: {}".format(self._lives)
        if self._lives <= 0:
            self._end_game()

    # ------------------------------------------------------------------
    # Shields
    # ------------------------------------------------------------------
    def _spawn_shields(self):
        for s in self._shields:
            if s is not None:
                self._remove_rect(s[0])
        self._shields = []
        spacing = DISPLAY_WIDTH // (_NUM_SHIELDS + 1)
        for i in range(_NUM_SHIELDS):
            sx = spacing * (i + 1) - _SHIELD_W // 2
            r = Rect(sx, _SHIELD_Y, _SHIELD_W, _SHIELD_H, fill=_SHIELD_COLOR)
            self._group.append(r)
            self._shields.append((r, _SHIELD_HP))

    # ------------------------------------------------------------------
    # Mystery ship
    # ------------------------------------------------------------------
    def _spawn_mystery(self):
        d = 1 if random.randint(0, 1) else -1
        x = -_MYSTERY_W if d > 0 else DISPLAY_WIDTH
        r = Rect(int(x), _MYSTERY_Y, _MYSTERY_W, _MYSTERY_H, fill=_MYSTERY_COLOR)
        self._group.append(r)
        self._mystery = (r, float(x), d)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _check_hit(ax, ay, aw, ah, bx, by, bw, bh):
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    def _add_score(self, pts):
        self._score += pts
        self._score_lbl.text = "Score: {}".format(self._score)
        if self._score > self._high_score:
            self._high_score = self._score

    def _remove_rect(self, rect):
        try:
            self._group.remove(rect)
        except ValueError:
            pass

    def _end_game(self):
        self._game_over = True
        self._msg_lbl.text = "GAME OVER"
        hi_txt = " NEW HI!" if self._score >= self._high_score and self._score > 0 else ""
        self._hint_lbl.text = "{} Hi:{}{}".format(self._score, self._high_score, hi_txt)

    def destroy(self):
        from . import save_high_score
        if self._score > 0:
            save_high_score('invaders', self._high_score)
        if self._player_bullet is not None:
            self._remove_rect(self._player_bullet[0])
            self._player_bullet = None
        for rect, _ in self._alien_bullets:
            self._remove_rect(rect)
        self._alien_bullets.clear()
        if self._mystery is not None:
            self._remove_rect(self._mystery[0])
            self._mystery = None
        for entry in self._aliens:
            if entry[0] is not None:
                self._remove_rect(entry[0])
        self._aliens.clear()
        for s in self._shields:
            if s is not None:
                self._remove_rect(s[0])
        self._shields.clear()
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
