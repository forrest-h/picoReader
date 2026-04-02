import time
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.line import Line
from ..constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT,
                         BTN_CENTER, BTN_UP, BTN_DOWN)

# BGR colors
_BG = 0x000000
_TERRAIN = 0x608060
_PAD = 0x00c0c0
_LANDER = 0xe7e7e7
_FLAME = 0x0060ff       # orange in BGR
_TXT = 0xb0b0b0
_BRIGHT = 0xe7e7e7
_CRASH = 0x4040ff        # red in BGR
_OK = 0x40ff40           # green in BGR

# Physics
_GRAVITY = 0.015
_THRUST = 0.0003         # multiplied by power 0-100
_SIDE_IMPULSE = 0.02
_DRAG = 0.98
_FUEL_MAIN = 0.0008      # per tick * power
_FUEL_SIDE = 0.02
_TICK = 0.033             # ~30fps

_LW, _LH = 4, 3          # lander size
_TERR_TOP, _TERR_BOT = 85, 120
_HUD_H = 20


class LunarLanderGame:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._score = 0
        self._paused = False
        self._game_over = False
        from . import load_high_score
        self._high_score = load_high_score('lunar')

        # Background
        bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        pal = displayio.Palette(1)
        pal[0] = _BG
        self._group.append(displayio.TileGrid(bmp, pixel_shader=pal))

        # HUD labels: (anchor_point, anchored_position, color)
        defs = [
            ((0.0, 0.0), (1, 1), _BRIGHT),
            ((1.0, 0.0), (DISPLAY_WIDTH - 1, 1), _TXT),
            ((0.0, 0.0), (1, 11), _TXT),
            ((1.0, 0.0), (DISPLAY_WIDTH - 1, 11), _TXT),
            ((0.5, 0.5), (80, 50), _BRIGHT),   # status overlay
            ((0.5, 0.5), (80, 63), _TXT),       # hint overlay
        ]
        lbls = []
        for ap, pos, col in defs:
            lb = label.Label(smallfont, text="", color=col,
                             base_alignment=(ap[1] == 0.0))
            lb.anchor_point = ap
            lb.anchored_position = pos
            self._group.append(lb)
            lbls.append(lb)
        self._fuel_lbl, self._vel_lbl = lbls[0], lbls[1]
        self._info_lbl, self._pwr_lbl = lbls[2], lbls[3]
        self._status_lbl, self._hint_lbl = lbls[4], lbls[5]

        # Lander rect and flame rect (flame hidden off-screen)
        self._lander = Rect(DISPLAY_WIDTH // 2, _HUD_H + 5, _LW, _LH, fill=_LANDER)
        self._flame = Rect(0, -10, 2, 3, fill=_FLAME)
        self._group.append(self._lander)
        self._group.append(self._flame)

        # Terrain storage
        self._terrain_lines = []
        self._terrain_pts = []
        self._pads = []

        # Game state
        self._level = 1
        self._lives = 3
        self._power = 0
        self._fuel = 100.0
        self._lx = float(DISPLAY_WIDTH // 2)
        self._ly = float(_HUD_H + 5)
        self._vx = self._vy = 0.0
        self._side_thrust = 0.0
        self._side_ticks = 0
        self._flying = True
        self._crashed_last = False
        self._result_timer = 0.0
        self._last_tick = time.monotonic()
        self._generate_terrain()
        self._update_hud()

    def get_group(self):
        return self._group

    # -- Input -------------------------------------------------------------
    def handle_button(self, button):
        if self._game_over:
            return 'quit'
        if not self._flying and not self._paused:
            return None
        if button == BTN_CENTER:
            if self._paused:
                self._paused = False
                self._status_lbl.text = ""
                self._hint_lbl.text = ""
                self._last_tick = time.monotonic()
            else:
                self._paused = True
                self._status_lbl.text = "PAUSED"
                self._hint_lbl.text = "C=resume U=quit"
            return None
        if button == BTN_UP:
            if self._paused:
                self._end_game()
            elif self._flying:
                self._power = min(100, self._power + 10)
            return None
        if button == BTN_DOWN and self._flying:
            self._power = max(0, self._power - 10)
        return None

    def handle_encoder(self, direction):
        if self._paused or self._game_over or not self._flying:
            return None
        self._side_thrust = float(direction)
        self._side_ticks = 4
        return None

    # -- Tick --------------------------------------------------------------
    def tick(self, now):
        if self._paused or self._game_over:
            return False
        dt = now - self._last_tick
        if dt < _TICK:
            return False
        self._last_tick = now

        # Between-round result timer
        if not self._flying:
            if self._result_timer > 0:
                self._result_timer -= dt
                if self._result_timer <= 0:
                    self._next_round()
                    return True
            return False

        # Main thrust
        thr = 0.0
        if self._power > 0 and self._fuel > 0:
            thr = self._power * _THRUST
            self._fuel = max(0.0, self._fuel - self._power * _FUEL_MAIN)
        # Side thrust
        sa = 0.0
        if self._side_ticks > 0 and self._fuel > 0:
            sa = self._side_thrust * _SIDE_IMPULSE
            self._fuel = max(0.0, self._fuel - _FUEL_SIDE)
            self._side_ticks -= 1
        if self._fuel <= 0:
            self._power = 0

        self._vy += _GRAVITY - thr
        self._vx = (self._vx + sa) * _DRAG
        self._lx += self._vx
        self._ly += self._vy

        # Screen wrap x, clamp ceiling
        if self._lx < -_LW:
            self._lx = float(DISPLAY_WIDTH)
        elif self._lx > DISPLAY_WIDTH:
            self._lx = float(-_LW)
        if self._ly < _HUD_H:
            self._ly = float(_HUD_H)
            self._vy = 0.0

        ix, iy = int(self._lx), int(self._ly)
        self._lander.x = ix
        self._lander.y = iy

        # Flame visual
        if self._power > 0 and self._fuel > 0:
            self._flame.x = ix + _LW // 2 - 1
            self._flame.y = iy + _LH
        else:
            self._flame.y = -10

        # Collision
        ty = self._terrain_y_at(self._lx + _LW / 2.0)
        if self._ly + _LH >= ty:
            self._ly = ty - _LH
            self._lander.y = int(self._ly)
            self._flame.y = -10
            self._resolve_landing()
            return True

        self._update_hud()
        return True

    # -- Terrain -----------------------------------------------------------
    def _generate_terrain(self):
        import random
        for ln in self._terrain_lines:
            try:
                self._group.remove(ln)
            except ValueError:
                pass
        self._terrain_lines.clear()
        self._terrain_pts.clear()
        self._pads.clear()

        rough = 6 + self._level * 2
        n_pads = max(1, 4 - self._level)
        pad_w = max(10, 22 - self._level * 3)
        seg = DISPLAY_WIDTH // (n_pads + 1)
        centers = sorted(
            max(pad_w, min(DISPLAY_WIDTH - pad_w,
                seg * (i + 1) + random.randint(-10, 10)))
            for i in range(n_pads))

        pts, x, pi = [], 0, 0
        while x <= DISPLAY_WIDTH:
            if pi < len(centers) and abs(x - centers[pi]) < pad_w:
                py = random.randint(_TERR_TOP + 5, _TERR_BOT - 5)
                ps = max(0, centers[pi] - pad_w // 2)
                pe = min(DISPLAY_WIDTH, ps + pad_w)
                pts.append((ps, py))
                pts.append((pe, py))
                self._pads.append((ps, pe, py))
                x = pe + 1
                pi += 1
                continue
            y = random.randint(_TERR_TOP, _TERR_BOT)
            if pts:
                y = max(_TERR_TOP, min(_TERR_BOT,
                        pts[-1][1] + random.randint(-rough, rough)))
            pts.append((x, y))
            x += random.randint(6, 14)
        if pts[-1][0] < DISPLAY_WIDTH:
            pts.append((DISPLAY_WIDTH, pts[-1][1]))
        if pts[0][0] > 0:
            pts.insert(0, (0, pts[0][1]))
        self._terrain_pts = pts

        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            is_pad = any(x0 >= ps and x1 <= pe and y0 == y1 == py
                         for ps, pe, py in self._pads)
            ln = Line(x0, y0, x1, y1, color=_PAD if is_pad else _TERRAIN)
            self._terrain_lines.append(ln)
            self._group.append(ln)

    def _terrain_y_at(self, x):
        pts = self._terrain_pts
        if not pts:
            return _TERR_BOT
        if x <= pts[0][0]:
            return pts[0][1]
        if x >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            if pts[i][0] <= x <= pts[i + 1][0]:
                x0, y0 = pts[i]
                x1, y1 = pts[i + 1]
                if x1 == x0:
                    return y0
                return y0 + (x - x0) / (x1 - x0) * (y1 - y0)
        return _TERR_BOT

    def _on_pad(self, lx):
        cx = lx + _LW / 2.0
        return any(s <= cx <= e for s, e, _ in self._pads)

    # -- Landing -----------------------------------------------------------
    def _resolve_landing(self):
        self._flying = False
        self._power = 0
        avx, avy = abs(self._vx), abs(self._vy)
        on_pad = self._on_pad(self._lx)

        if on_pad and avy < 0.3 and avx < 0.3:
            pts, msg, color = 100, "PERFECT!", _OK
        elif on_pad and avy < 0.6 and avx < 0.5:
            pts, msg, color = 50, "GOOD LANDING", _OK
        elif on_pad and avy < 1.0 and avx < 0.8:
            pts, msg, color = 25, "ROUGH LANDING", _TXT
        else:
            pts, color = 0, _CRASH
            msg = "MISSED PAD!" if not on_pad else "TOO FAST!"
            self._lives -= 1
            self._crashed_last = True

        # Small-pad bonus
        if pts > 0:
            cx = self._lx + _LW / 2.0
            for s, e, _ in self._pads:
                if s <= cx <= e and e - s <= 12:
                    pts = int(pts * 1.5)
                    break

        self._score += pts
        if self._score > self._high_score:
            self._high_score = self._score
        self._vx = self._vy = 0.0
        self._status_lbl.color = color
        self._status_lbl.text = msg
        if pts > 0:
            self._hint_lbl.text = "+{} Sc:{} Lv:{}".format(pts, self._score, self._level)
        else:
            self._hint_lbl.text = "Lives:{} Sc:{}".format(self._lives, self._score)
        self._result_timer = 2.0 if self._lives <= 0 else 1.8

    def _next_round(self):
        self._status_lbl.text = ""
        self._hint_lbl.text = ""
        if self._lives <= 0:
            self._end_game()
            return
        if not self._crashed_last:
            self._level += 1
        self._crashed_last = False
        self._generate_terrain()
        self._reset_lander()

    def _reset_lander(self):
        import random
        self._lx = float(random.randint(20, DISPLAY_WIDTH - 20))
        self._ly = float(_HUD_H + 5)
        self._vx = self._vy = 0.0
        self._power = 0
        self._fuel = max(40.0, 100.0 - (self._level - 1) * 10.0)
        self._side_thrust = 0.0
        self._side_ticks = 0
        self._flying = True
        self._lander.x = int(self._lx)
        self._lander.y = int(self._ly)
        self._flame.y = -10
        self._update_hud()

    # -- HUD ---------------------------------------------------------------
    def _update_hud(self):
        f = int(self._fuel / 10.0)
        self._fuel_lbl.text = "F[{}{}]".format("#" * f, "." * (10 - f))
        self._vel_lbl.text = "Vx:{} Vy:{}".format(
            int(self._vx * 10), int(self._vy * 10))
        self._info_lbl.text = "Lv:{} Lf:{}".format(self._level, self._lives)
        self._pwr_lbl.text = "Pw:{} Sc:{}".format(self._power, self._score)

    # -- End / Destroy -----------------------------------------------------
    def _end_game(self):
        self._game_over = True
        self._flying = False
        self._status_lbl.color = _BRIGHT
        self._status_lbl.text = "GAME OVER"
        self._hint_lbl.text = "Sc:{} Hi:{}".format(self._score, self._high_score)

    def destroy(self):
        from . import save_high_score
        if self._score > 0:
            save_high_score('lunar', self._high_score)
        for ln in self._terrain_lines:
            try:
                self._group.remove(ln)
            except ValueError:
                pass
        self._terrain_lines.clear()
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
