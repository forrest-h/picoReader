import time
import math
import random
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT,
                         BTN_CENTER, BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT)

# BGR colors
_BG = 0x000000
_TEXT = 0xe7e7e7
_SHIP_COLOR = 0xffcc00     # cyan-ish (BGR)
_NOSE_COLOR = 0x00ffff     # yellow (BGR)
_BULLET_COLOR = 0xe7e7e7   # white
_ASTEROID_COLOR = 0x8080ff  # light red (BGR)

# Ship
_SHIP_SIZE = 4
_NOSE_SIZE = 2
_NOSE_DIST = 6
_DRAG = 0.985
_THRUST_IMPULSE = 0.4
_MAX_SPEED = 2.5
_ROTATE_STEP = 0.25

# Bullets
_BULLET_SIZE = 2
_BULLET_SPEED = 2.5
_BULLET_LIFE = 55
_MAX_BULLETS = 4

# Asteroids
_SIZES = {
    'large':  {'dim': 12, 'pts': 20,  'speed': (0.3, 0.7)},
    'medium': {'dim': 7,  'pts': 50,  'speed': (0.5, 1.0)},
    'small':  {'dim': 4,  'pts': 100, 'speed': (0.8, 1.4)},
}
_MAX_ASTEROIDS = 12
_START_COUNT = 4
_SAFE_DIST = 40

# Gameplay
_INVULN_TICKS = 60
_LIVES = 3
_HYPERSPACE_DEATH_CHANCE = 10  # 1 in N


class AsteroidsGame:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._score = 0
        self._lives = _LIVES
        self._level = 1
        self._paused = False
        self._game_over = False
        self._thrust_pending = False
        self._invuln = 0

        from . import load_high_score
        self._high_score = load_high_score('asteroids')

        # Background
        bg_bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        bg_pal = displayio.Palette(1)
        bg_pal[0] = _BG
        self._group.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))

        # HUD labels
        self._score_lbl = label.Label(self._font, text="S:0",
                                      color=_TEXT, base_alignment=True)
        self._score_lbl.anchor_point = (0.0, 0.0)
        self._score_lbl.anchored_position = (2, 1)
        self._group.append(self._score_lbl)

        self._lives_lbl = label.Label(self._font, text="x{}".format(self._lives),
                                      color=_TEXT, base_alignment=True)
        self._lives_lbl.anchor_point = (0.5, 0.0)
        self._lives_lbl.anchored_position = (80, 1)
        self._group.append(self._lives_lbl)

        self._hi_lbl = label.Label(self._font, text="H:{}".format(self._high_score),
                                   color=_TEXT, base_alignment=True)
        self._hi_lbl.anchor_point = (1.0, 0.0)
        self._hi_lbl.anchored_position = (DISPLAY_WIDTH - 2, 1)
        self._group.append(self._hi_lbl)

        # Center message labels
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

        # Ship state
        self._ship_x = float(DISPLAY_WIDTH // 2)
        self._ship_y = float(DISPLAY_HEIGHT // 2)
        self._ship_vx = 0.0
        self._ship_vy = 0.0
        self._angle = -math.pi / 2  # facing up

        # Ship rects
        sx = int(self._ship_x) - _SHIP_SIZE // 2
        sy = int(self._ship_y) - _SHIP_SIZE // 2
        self._ship_rect = Rect(sx, sy, _SHIP_SIZE, _SHIP_SIZE,
                               fill=_SHIP_COLOR)
        self._group.append(self._ship_rect)

        nx = int(self._ship_x + math.cos(self._angle) * _NOSE_DIST) - _NOSE_SIZE // 2
        ny = int(self._ship_y + math.sin(self._angle) * _NOSE_DIST) - _NOSE_SIZE // 2
        self._nose_rect = Rect(nx, ny, _NOSE_SIZE, _NOSE_SIZE,
                               fill=_NOSE_COLOR)
        self._group.append(self._nose_rect)

        # Dynamic entities
        self._bullets = []     # list of [rect, x_f, y_f, vx, vy, life]
        self._asteroids = []   # list of [rect, x_f, y_f, vx, vy, size_key]

        self._spawn_asteroids(self._level)
        self._last_tick = time.monotonic()

    def get_group(self):
        return self._group

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_button(self, button):
        if self._game_over:
            return 'quit'

        if button == BTN_LEFT:
            if self._paused:
                self._end_game()
                return None
            self._paused = True
            self._msg_lbl.text = "PAUSED"
            self._hint_lbl.text = "C=resume L=quit"
            return None

        if button == BTN_CENTER:
            if self._paused:
                self._paused = False
                self._msg_lbl.text = ""
                self._hint_lbl.text = ""
                self._last_tick = time.monotonic()
                return None
            self._fire()
            return None

        if button == BTN_UP:
            if self._paused:
                self._end_game()
                return None
            self._thrust_pending = True
            return None

        if button == BTN_DOWN:
            if not self._paused:
                self._hyperspace()
            return None

        return None

    def handle_encoder(self, direction):
        if self._paused or self._game_over:
            return None
        self._angle += direction * _ROTATE_STEP
        self._update_nose()
        return None

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def tick(self, now):
        if self._paused or self._game_over:
            return False

        if now - self._last_tick < 0.033:
            return False
        self._last_tick = now

        # Invulnerability countdown
        if self._invuln > 0:
            self._invuln -= 1
            # Blink ship during invulnerability
            visible = (self._invuln % 6) < 3
            show_color = _SHIP_COLOR if visible else _BG
            self._ship_rect.fill = show_color

        # Apply thrust if pending
        if self._thrust_pending:
            self._thrust_pending = False
            self._ship_vx += math.cos(self._angle) * _THRUST_IMPULSE
            self._ship_vy += math.sin(self._angle) * _THRUST_IMPULSE
            # Clamp speed
            spd = math.sqrt(self._ship_vx ** 2 + self._ship_vy ** 2)
            if spd > _MAX_SPEED:
                scale = _MAX_SPEED / spd
                self._ship_vx *= scale
                self._ship_vy *= scale

        # Apply drag
        self._ship_vx *= _DRAG
        self._ship_vy *= _DRAG

        # Move ship
        self._ship_x += self._ship_vx
        self._ship_y += self._ship_vy
        self._ship_x = self._ship_x % DISPLAY_WIDTH
        self._ship_y = self._ship_y % DISPLAY_HEIGHT
        self._ship_rect.x = int(self._ship_x) - _SHIP_SIZE // 2
        self._ship_rect.y = int(self._ship_y) - _SHIP_SIZE // 2
        self._update_nose()

        # Move bullets
        for i in range(len(self._bullets) - 1, -1, -1):
            b = self._bullets[i]
            b[1] += b[3]  # x += vx
            b[2] += b[4]  # y += vy
            b[5] -= 1     # life -= 1
            b[1] = b[1] % DISPLAY_WIDTH
            b[2] = b[2] % DISPLAY_HEIGHT
            if b[5] <= 0:
                self._remove_bullet(i)
                continue
            b[0].x = int(b[1])
            b[0].y = int(b[2])

        # Move asteroids
        for a in self._asteroids:
            a[1] += a[3]  # x += vx
            a[2] += a[4]  # y += vy
            a[1] = a[1] % DISPLAY_WIDTH
            a[2] = a[2] % DISPLAY_HEIGHT
            a[0].x = int(a[1])
            a[0].y = int(a[2])

        # Bullet-asteroid collisions
        for i in range(len(self._bullets) - 1, -1, -1):
            b = self._bullets[i]
            bx, by = int(b[1]), int(b[2])
            hit = False
            for j in range(len(self._asteroids) - 1, -1, -1):
                a = self._asteroids[j]
                dim = _SIZES[a[5]]['dim']
                ax, ay = int(a[1]), int(a[2])
                if self._aabb(bx, by, _BULLET_SIZE, _BULLET_SIZE,
                              ax, ay, dim, dim):
                    self._add_score(_SIZES[a[5]]['pts'])
                    self._split_asteroid(j)
                    self._remove_bullet(i)
                    hit = True
                    break
            if hit:
                continue

        # Ship-asteroid collisions (skip if invulnerable)
        if self._invuln <= 0:
            sx = int(self._ship_x) - _SHIP_SIZE // 2
            sy = int(self._ship_y) - _SHIP_SIZE // 2
            for a in self._asteroids:
                dim = _SIZES[a[5]]['dim']
                ax, ay = int(a[1]), int(a[2])
                if self._aabb(sx, sy, _SHIP_SIZE, _SHIP_SIZE,
                              ax, ay, dim, dim):
                    self._ship_hit()
                    break

        # Level clear check
        if not self._asteroids and not self._game_over:
            self._level += 1
            self._spawn_asteroids(self._level)

        return True

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _fire(self):
        if len(self._bullets) >= _MAX_BULLETS:
            return
        bx = self._ship_x + math.cos(self._angle) * (_SHIP_SIZE + 2)
        by = self._ship_y + math.sin(self._angle) * (_SHIP_SIZE + 2)
        vx = math.cos(self._angle) * _BULLET_SPEED
        vy = math.sin(self._angle) * _BULLET_SPEED
        r = Rect(int(bx), int(by), _BULLET_SIZE, _BULLET_SIZE,
                 fill=_BULLET_COLOR)
        self._group.append(r)
        self._bullets.append([r, bx, by, vx, vy, _BULLET_LIFE])

    def _hyperspace(self):
        if random.randint(1, _HYPERSPACE_DEATH_CHANCE) == 1:
            self._ship_hit()
            return
        self._ship_x = float(random.randint(10, DISPLAY_WIDTH - 10))
        self._ship_y = float(random.randint(20, DISPLAY_HEIGHT - 10))
        self._ship_vx = 0.0
        self._ship_vy = 0.0
        self._ship_rect.x = int(self._ship_x) - _SHIP_SIZE // 2
        self._ship_rect.y = int(self._ship_y) - _SHIP_SIZE // 2
        self._update_nose()

    def _ship_hit(self):
        self._lives -= 1
        self._lives_lbl.text = "x{}".format(self._lives)
        if self._lives <= 0:
            self._end_game()
            return
        # Respawn at center with invulnerability
        self._ship_x = float(DISPLAY_WIDTH // 2)
        self._ship_y = float(DISPLAY_HEIGHT // 2)
        self._ship_vx = 0.0
        self._ship_vy = 0.0
        self._angle = -math.pi / 2
        self._invuln = _INVULN_TICKS
        self._ship_rect.x = int(self._ship_x) - _SHIP_SIZE // 2
        self._ship_rect.y = int(self._ship_y) - _SHIP_SIZE // 2
        self._update_nose()

    # ------------------------------------------------------------------
    # Asteroids
    # ------------------------------------------------------------------
    def _spawn_asteroids(self, level):
        count = min(_START_COUNT + level - 1, _MAX_ASTEROIDS)
        cx = DISPLAY_WIDTH // 2
        cy = DISPLAY_HEIGHT // 2
        for _ in range(count):
            # Pick a position away from center
            for _attempt in range(20):
                x = float(random.randint(0, DISPLAY_WIDTH - 1))
                y = float(random.randint(12, DISPLAY_HEIGHT - 1))
                dx = x - cx
                dy = y - cy
                if dx * dx + dy * dy > _SAFE_DIST * _SAFE_DIST:
                    break
            vx = random.uniform(0.3, 0.7)
            vy = random.uniform(0.3, 0.7)
            if random.randint(0, 1):
                vx = -vx
            if random.randint(0, 1):
                vy = -vy
            self._create_asteroid(x, y, vx, vy, 'large')

    def _create_asteroid(self, x, y, vx, vy, size_key):
        if len(self._asteroids) >= _MAX_ASTEROIDS:
            return
        dim = _SIZES[size_key]['dim']
        r = Rect(int(x), int(y), dim, dim, fill=_ASTEROID_COLOR)
        self._group.append(r)
        self._asteroids.append([r, x, y, vx, vy, size_key])

    def _split_asteroid(self, index):
        a = self._asteroids[index]
        x, y, size_key = a[1], a[2], a[5]
        self._remove_asteroid(index)
        if size_key == 'large':
            child = 'medium'
        elif size_key == 'medium':
            child = 'small'
        else:
            return  # small destroyed, no children
        lo, hi = _SIZES[child]['speed']
        for _ in range(2):
            vx = random.uniform(lo, hi)
            vy = random.uniform(lo, hi)
            if random.randint(0, 1):
                vx = -vx
            if random.randint(0, 1):
                vy = -vy
            self._create_asteroid(x, y, vx, vy, child)

    def _remove_asteroid(self, index):
        r = self._asteroids[index][0]
        try:
            self._group.remove(r)
        except ValueError:
            pass
        self._asteroids.pop(index)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_nose(self):
        nx = int(self._ship_x + math.cos(self._angle) * _NOSE_DIST) - _NOSE_SIZE // 2
        ny = int(self._ship_y + math.sin(self._angle) * _NOSE_DIST) - _NOSE_SIZE // 2
        # Clamp to screen for display; wrapping handled on next tick
        self._nose_rect.x = nx % DISPLAY_WIDTH
        self._nose_rect.y = ny % DISPLAY_HEIGHT

    @staticmethod
    def _aabb(ax, ay, aw, ah, bx, by, bw, bh):
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    def _add_score(self, pts):
        self._score += pts
        self._score_lbl.text = "S:{}".format(self._score)
        if self._score > self._high_score:
            self._high_score = self._score
            self._hi_lbl.text = "H:{}".format(self._high_score)

    def _remove_bullet(self, index):
        r = self._bullets[index][0]
        try:
            self._group.remove(r)
        except ValueError:
            pass
        self._bullets.pop(index)

    def _end_game(self):
        self._game_over = True
        self._ship_rect.fill = _BG
        self._nose_rect.fill = _BG
        self._msg_lbl.text = "GAME OVER"
        hi_txt = " NEW HI!" if self._score >= self._high_score and self._score > 0 else ""
        self._hint_lbl.text = "{} Hi:{}{}".format(self._score, self._high_score, hi_txt)

    def destroy(self):
        from . import save_high_score
        if self._score > 0:
            save_high_score('asteroids', self._high_score)
        for b in self._bullets:
            try:
                self._group.remove(b[0])
            except ValueError:
                pass
        self._bullets.clear()
        for a in self._asteroids:
            try:
                self._group.remove(a[0])
            except ValueError:
                pass
        self._asteroids.clear()
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
