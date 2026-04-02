import os
import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT,
                         BTN_CENTER, BTN_UP)

_BG = 0x1a1a1a
_TEXT = 0xc8c8c8
_BRIGHT = 0xe7e7e7
_HIGHLIGHT = 0x005500
_LOCKED = 0x606060


class AdventureSelect:
    def __init__(self, hw_display, smallfont):
        self._display = hw_display
        self._font = smallfont
        self._group = displayio.Group()
        self._cursor = 0
        self._engine = None

        bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        pal = displayio.Palette(1)
        pal[0] = _BG
        self._group.append(displayio.TileGrid(bmp, pixel_shader=pal))

        tl = label.Label(smallfont, text="Adventures", color=_BRIGHT,
                         base_alignment=True)
        tl.anchor_point = (0.5, 0.0)
        tl.anchored_position = (80, 2)
        self._group.append(tl)

        self._episodes = []
        self._scan_episodes()

        self._labels = []
        self._rects = []
        for i in range(min(8, max(1, len(self._episodes)))):
            y = 18 + i * 13
            r = Rect(2, y - 1, DISPLAY_WIDTH - 4, 13, fill=_BG)
            self._group.append(r)
            self._rects.append(r)
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (6, y)
            self._group.append(lb)
            self._labels.append(lb)

        self._hint = label.Label(smallfont, text="", color=_LOCKED,
                                 base_alignment=True)
        self._hint.anchor_point = (0.5, 1.0)
        self._hint.anchored_position = (80, DISPLAY_HEIGHT - 2)
        self._group.append(self._hint)

        if not self._episodes:
            self._hint.text = "No .adv in /sd/adventures/"
        else:
            self._hint.text = "C=play  U=back"
            self._refresh_list()

    def _scan_episodes(self):
        try:
            files = os.listdir("/sd/adventures")
        except OSError:
            return
        for fn in sorted(files):
            if not fn.endswith(".adv"):
                continue
            title = fn[:-4].replace("_", " ")
            try:
                with open("/sd/adventures/" + fn, "r") as f:
                    for _ in range(10):
                        line = f.readline()
                        if not line:
                            break
                        if line.startswith("@TITLE "):
                            title = line[7:].strip()
                            break
            except OSError:
                pass
            has_save = False
            try:
                os.stat("saves/adv_" + fn[:-4])
                has_save = True
            except OSError:
                pass
            suffix = " [SAVED]" if has_save else ""
            self._episodes.append((title + suffix, fn))

    def _refresh_list(self):
        n = len(self._episodes)
        for i, lb in enumerate(self._labels):
            if i < n:
                lb.text = self._episodes[i][0][:22]
                lb.color = _BRIGHT if i == self._cursor else _TEXT
            else:
                lb.text = ""
            self._rects[i].fill = _HIGHLIGHT if i == self._cursor else _BG

    def get_group(self):
        if self._engine:
            return self._engine.get_group()
        return self._group

    def handle_button(self, button):
        if self._engine:
            result = self._engine.handle_button(button)
            if result == 'quit':
                self._engine.destroy()
                self._engine = None
                self._display.show(self._group)
                return None
            return result
        if button == BTN_UP:
            return 'quit'
        if button == BTN_CENTER and self._episodes:
            _, fn = self._episodes[self._cursor]
            path = "/sd/adventures/" + fn
            from .adventure_engine import AdventureEngine
            self._engine = AdventureEngine(
                self._display, self._font, path, fn[:-4])
            self._display.show(self._engine.get_group())
        return None

    def handle_encoder(self, direction):
        if self._engine:
            return self._engine.handle_encoder(direction)
        if not self._episodes:
            return None
        self._cursor = (self._cursor + direction) % len(self._episodes)
        self._refresh_list()
        return None

    def tick(self, now):
        if self._engine:
            return self._engine.tick(now)
        return False

    def destroy(self):
        if self._engine:
            self._engine.destroy()
            self._engine = None
        while len(self._group) > 0:
            self._group.pop()
        self._group = None
