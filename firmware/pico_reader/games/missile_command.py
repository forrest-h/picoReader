import time
import random
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT,
                         BTN_CENTER, BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT)

# BGR colors
_BG = 0x000000
_TEXT_C = 0xe7e7e7
_CITY_C = 0xFF9900
_CITY_C2 = 0xCC6600
_BATTERY_C = 0x00CC00
_MISSILE_C = 0x0000FF
_COUNTER_C = 0x00FFFF
_EXPLOSION_C = 0x00AAFF
_CROSSHAIR_C = 0xFFFFFF
_GROUND_C = 0x004400

# Layout
_GROUND_Y = 118
_CH_ARM = 4         # crosshair arm length
_CH_STEP = 4        # crosshair move step
_CITY_X = [25, 75, 125]
_BATT_X = [5, 55, 105]

# Gameplay
_AMMO = 10
_CTR_SPEED = 2.5
_EXP_MAX_R = 12
_EXP_GROW = 0.4
_EXP_SHRINK = 0.6
_MAX_IN = 15
_MAX_CTR = 5
_MAX_EXP = 5
_INTERCEPT_PTS = 25
_CITY_BONUS = 100

# Difficulty: wave -> (missile_count, speed)
_WAVE_P = {1: (5, 0.3), 2: (6, 0.35), 3: (8, 0.4),
           4: (9, 0.5), 5: (10, 0.55), 6: (12, 0.6)}
_W7_BASE = (12, 0.7)
_SPLIT_WAVE = 7


def _rm(group, obj):
    try:
        group.remove(obj)
    except ValueError:
        pass


class MissileCommandGame:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        g = displayio.Group()
        self._group = g
        self._score = 0
        self._wave = 1
        self._paused = False
        self._game_over = False
        self._wave_active = True
        self._wave_trans = False
        self._trans_end = 0.0

        from . import load_high_score
        self._high_score = load_high_score('missile_cmd')

        # Background + ground
        bg_bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        bg_pal = displayio.Palette(1)
        bg_pal[0] = _BG
        g.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))
        g.append(Rect(0, _GROUND_Y, DISPLAY_WIDTH,
                       DISPLAY_HEIGHT - _GROUND_Y, fill=_GROUND_C))

        # HUD
        def _lbl(txt, anchor, pos):
            l = label.Label(self._font, text=txt, color=_TEXT_C, base_alignment=True)
            l.anchor_point = anchor
            l.anchored_position = pos
            g.append(l)
            return l
        self._score_lbl = _lbl("S:0", (0.0, 0.0), (2, 2))
        self._wave_lbl = _lbl("W:1", (0.5, 0.0), (80, 2))
        self._hi_lbl = _lbl("H:{}".format(self._high_score), (1.0, 0.0),
                            (DISPLAY_WIDTH - 2, 2))

        # Message labels (pause/game-over/wave transition)
        def _msg(y):
            l = label.Label(self._font, text="", color=_TEXT_C, base_alignment=False)
            l.anchor_point = (0.5, 0.5)
            l.anchored_position = (80, y)
            g.append(l)
            return l
        self._msg_lbl = _msg(55)
        self._msg_hint = _msg(70)

        # Cities (3 buildings each)
        self._cities = []
        for cx in _CITY_X:
            rects = []
            for ox, ow, oh, c in [(-6, 5, 8, _CITY_C), (0, 6, 10, _CITY_C2),
                                   (7, 4, 6, _CITY_C)]:
                r = Rect(cx + ox, _GROUND_Y - oh, ow, oh, fill=c)
                g.append(r)
                rects.append(r)
            self._cities.append([True, cx, rects])  # [alive, x, rects]

        # Batteries
        self._batts = []
        self._batt_rects = []
        for bx in _BATT_X:
            r = Rect(bx, _GROUND_Y - 5, 8, 5, fill=_BATTERY_C)
            g.append(r)
            self._batt_rects.append(r)
            self._batts.append([True, bx + 4, _AMMO])  # [alive, center_x, ammo]
        self._sel_batt = 1

        # Crosshair
        self._cx = 80
        self._cy = 60
        self._ch_h = Rect(self._cx - _CH_ARM, self._cy, _CH_ARM * 2 + 1, 1,
                          fill=_CROSSHAIR_C)
        self._ch_v = Rect(self._cx, self._cy - _CH_ARM, 1, _CH_ARM * 2 + 1,
                          fill=_CROSSHAIR_C)
        g.append(self._ch_h)
        g.append(self._ch_v)

        # Dynamic entities: missiles [rect,sx,sy,tx,ty,progress,speed]
        # counters [rect,x,y,tx,ty,speed], explosions [circle,x,y,rad,max_r,expanding]
        self._missiles = []
        self._counters = []
        self._explosions = []
        self._missiles_left = 0
        self._last_tick = time.monotonic()
        self._last_spawn = 0.0
        self._start_wave(1)

    def get_group(self):
        return self._group

    # --- Input ---

    def handle_button(self, button):
        if self._game_over:
            return 'quit'
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
            if not self._wave_trans:
                self._fire()
            return None
        if self._paused or self._wave_trans:
            return None
        if button == BTN_LEFT:
            self._cx = max(_CH_ARM, self._cx - _CH_STEP)
        elif button == BTN_RIGHT:
            self._cx = min(DISPLAY_WIDTH - _CH_ARM - 1, self._cx + _CH_STEP)
        elif button == BTN_DOWN:
            self._cy = min(_GROUND_Y - _CH_ARM - 1, self._cy + _CH_STEP)
        self._ch_h.x = self._cx - _CH_ARM
        self._ch_h.y = self._cy
        self._ch_v.x = self._cx
        self._ch_v.y = self._cy - _CH_ARM
        return None

    def handle_encoder(self, direction):
        if self._paused or self._game_over or self._wave_trans:
            return None
        self._sel_batt = (self._sel_batt + direction) % 3
        return None

    # --- Wave management ---

    def _start_wave(self, n):
        self._wave = n
        self._wave_lbl.text = "W:{}".format(n)
        if n in _WAVE_P:
            cnt, spd = _WAVE_P[n]
        else:
            cnt = _W7_BASE[0] + (n - 7) * 2
            spd = min(1.2, _W7_BASE[1] + (n - 7) * 0.05)
        self._w_count = cnt
        self._w_speed = spd
        self._missiles_left = cnt
        self._last_spawn = time.monotonic()
        self._wave_active = True
        for b in self._batts:
            if b[0]:
                b[2] = _AMMO

    def _wave_done(self):
        return (self._missiles_left <= 0 and not self._missiles
                and not self._counters and not self._explosions)

    def _end_wave(self):
        alive = sum(1 for c in self._cities if c[0])
        bonus = alive * _CITY_BONUS
        self._score += bonus
        self._update_score()
        self._wave_trans = True
        self._trans_end = time.monotonic() + 1.5
        self._msg_lbl.text = "Wave {} done!".format(self._wave)
        self._msg_hint.text = "+{} bonus".format(bonus) if bonus else ""

    # --- Firing ---

    def _fire(self):
        if len(self._counters) >= _MAX_CTR:
            return
        for off in range(3):
            b = self._batts[(self._sel_batt + off) % 3]
            if b[0] and b[2] > 0:
                b[2] -= 1
                bx, by = b[1], _GROUND_Y - 5
                r = Rect(bx - 1, by, 2, 2, fill=_COUNTER_C)
                self._group.append(r)
                self._counters.append([r, float(bx), float(by),
                                       float(self._cx), float(self._cy), _CTR_SPEED])
                return

    # --- Spawning ---

    def _spawn_missile(self):
        if self._missiles_left <= 0 or len(self._missiles) >= _MAX_IN:
            return
        self._missiles_left -= 1
        sx = random.randint(5, DISPLAY_WIDTH - 5)
        targets = ([(c[1], _GROUND_Y) for c in self._cities if c[0]] +
                   [(b[1], _GROUND_Y) for b in self._batts if b[0]])
        if not targets:
            return
        tx, ty = targets[random.randint(0, len(targets) - 1)]
        r = Rect(sx, 12, 2, 2, fill=_MISSILE_C)
        self._group.append(r)
        self._missiles.append([r, sx, 12, tx, ty, 0.0, self._w_speed])

    # --- Tick ---

    def tick(self, now):
        if self._paused or self._game_over:
            return False
        if self._wave_trans:
            if now >= self._trans_end:
                self._wave_trans = False
                self._msg_lbl.text = ""
                self._msg_hint.text = ""
                self._start_wave(self._wave + 1)
                self._last_tick = now
            return False
        if now - self._last_tick < 0.03:
            return False
        self._last_tick = now
        changed = False

        # Spawn
        if self._missiles_left > 0:
            interval = max(0.3, 1.5 - self._wave * 0.1)
            if now - self._last_spawn >= interval:
                self._spawn_missile()
                self._last_spawn = now
                if self._wave >= _SPLIT_WAVE and random.randint(0, 3) == 0:
                    self._spawn_missile()

        # Move incoming missiles
        for i in range(len(self._missiles) - 1, -1, -1):
            m = self._missiles[i]
            r, sx, sy, tx, ty, prog, spd = m
            dx, dy = tx - sx, ty - sy
            dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
            prog += spd / dist
            if prog >= 1.0:
                self._hit_target(tx, ty)
                _rm(self._group, r)
                self._missiles.pop(i)
                changed = True
                if self._game_over:
                    return True
                continue
            r.x = int(sx + dx * prog)
            r.y = int(sy + dy * prog)
            m[5] = prog
            changed = True

        # Move counter-missiles
        for i in range(len(self._counters) - 1, -1, -1):
            c = self._counters[i]
            r, x, y, tx, ty, spd = c
            dx, dy = tx - x, ty - y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < spd:
                _rm(self._group, r)
                self._counters.pop(i)
                self._create_explosion(tx, ty)
                changed = True
                continue
            ratio = spd / dist
            c[1] = x + dx * ratio
            c[2] = y + dy * ratio
            r.x = int(c[1])
            r.y = int(c[2])
            changed = True

        # Update explosions (fixed Rect, track radius mathematically)
        for i in range(len(self._explosions) - 1, -1, -1):
            e = self._explosions[i]
            rect, ex, ey, rad, max_r, expanding = e
            if expanding:
                rad += _EXP_GROW
                if rad >= max_r:
                    rad = max_r
                    e[5] = False
            else:
                rad -= _EXP_SHRINK
                if rad <= 0:
                    _rm(self._group, rect)
                    self._explosions.pop(i)
                    changed = True
                    continue
            e[3] = rad
            # Check blast hits on incoming missiles
            rad_sq = max_r * max_r  # use full visual rect size for hit check
            for j in range(len(self._missiles) - 1, -1, -1):
                mr = self._missiles[j][0]
                ddx, ddy = mr.x - ex, mr.y - ey
                if ddx * ddx + ddy * ddy <= rad_sq:
                    _rm(self._group, mr)
                    self._missiles.pop(j)
                    self._score += _INTERCEPT_PTS
                    self._update_score()
            changed = True

        if self._wave_active and self._wave_done():
            self._wave_active = False
            self._end_wave()
            changed = True
        return changed

    # --- Helpers ---

    def _hit_target(self, tx, ty):
        for c in self._cities:
            if c[0] and abs(c[1] - tx) < 12:
                c[0] = False
                for r in c[2]:
                    _rm(self._group, r)
                break
        for i, b in enumerate(self._batts):
            if b[0] and abs(b[1] - tx) < 10:
                b[0] = False
                _rm(self._group, self._batt_rects[i])
                break
        if not any(c[0] for c in self._cities):
            self._end_game()

    def _create_explosion(self, x, y):
        if len(self._explosions) >= _MAX_EXP:
            return
        sz = _EXP_MAX_R * 2
        r = Rect(int(x) - _EXP_MAX_R, int(y) - _EXP_MAX_R, sz, sz,
                 fill=_EXPLOSION_C)
        self._group.append(r)
        self._explosions.append([r, x, y, 2.0, _EXP_MAX_R, True])

    def _update_score(self):
        self._score_lbl.text = "S:{}".format(self._score)
        if self._score > self._high_score:
            self._high_score = self._score
            self._hi_lbl.text = "H:{}".format(self._high_score)

    def _end_game(self):
        self._game_over = True
        self._msg_lbl.text = "GAME OVER"
        self._msg_hint.text = "S:{} H:{}".format(self._score, self._high_score)

    def destroy(self):
        from . import save_high_score
        if self._score > 0:
            save_high_score('missile_cmd', self._high_score)
        for lst in (self._missiles, self._counters, self._explosions):
            for ent in lst:
                _rm(self._group, ent[0])
            lst.clear()
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
