import displayio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from ..constants import (DISPLAY_WIDTH, DISPLAY_HEIGHT,
                         BTN_CENTER, BTN_UP, BTN_DOWN, BTN_LEFT)

_BG = 0x1a1a1a
_TEXT = 0xc8c8c8
_BRIGHT = 0xe7e7e7
_HL = 0x005500
_TBG = 0x2a2a2a
_LOCKED = 0x606060
_INV_BG = 0x282828
_TH = 12
_DY = 14
_DL = 5
_LH = 11
_CY = _DY + _DL * _LH + 4
_MC = 4
_CPL = 25


def _wrap(text, mx):
    lines = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        words = raw.split()
        cur = ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > mx:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w) if cur else w
        if cur:
            lines.append(cur)
    return lines


class AdventureEngine:
    def __init__(self, hw_display, smallfont, filepath, save_name):
        self._dsp = hw_display
        self._fnt = smallfont
        self._fp = filepath
        self._sn = save_name
        self._g = displayio.Group()
        self._inv = []
        self._flags = set()
        self._score = 0
        self._rid = None
        self._title = ""
        self._start = ""
        self._dl = []
        self._ch = []
        self._got = None
        self._wt = None
        self._idx = {}
        self._ds = 0
        self._cc = 0
        self._foc = 'c'
        self._si = False
        self._ic = 0
        self._ended = False
        self._build_idx()
        bmp = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        pal = displayio.Palette(1)
        pal[0] = _BG
        self._g.append(displayio.TileGrid(bmp, pixel_shader=pal))
        self._g.append(Rect(0, 0, DISPLAY_WIDTH, _TH, fill=_TBG))
        self._tl = label.Label(smallfont, text=self._title[:20],
                               color=_BRIGHT, base_alignment=True)
        self._tl.anchor_point = (0.0, 0.0)
        self._tl.anchored_position = (3, 2)
        self._g.append(self._tl)
        self._ii = label.Label(smallfont, text="", color=_LOCKED,
                               base_alignment=True)
        self._ii.anchor_point = (1.0, 0.0)
        self._ii.anchored_position = (DISPLAY_WIDTH - 3, 2)
        self._g.append(self._ii)
        self._dls = []
        for i in range(_DL):
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (4, _DY + i * _LH)
            self._g.append(lb)
            self._dls.append(lb)
        self._g.append(Rect(4, _CY - 3, DISPLAY_WIDTH - 8, 1, fill=_TBG))
        self._fl = label.Label(smallfont, text="", color=0x00cc66,
                               base_alignment=True)
        self._fl.anchor_point = (1.0, 0.0)
        self._fl.anchored_position = (DISPLAY_WIDTH - 2, _DY)
        self._g.append(self._fl)
        self._crs = []
        self._cls = []
        for i in range(_MC):
            y = _CY + i * _LH
            r = Rect(2, y - 1, DISPLAY_WIDTH - 4, _LH, fill=_BG)
            self._g.append(r)
            self._crs.append(r)
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (6, y)
            self._g.append(lb)
            self._cls.append(lb)
        self._ibg = Rect(4, -DISPLAY_HEIGHT, DISPLAY_WIDTH - 8,
                         DISPLAY_HEIGHT - 24, fill=_INV_BG)
        self._g.append(self._ibg)
        self._ils = []
        for i in range(7):
            lb = label.Label(smallfont, text="", color=_TEXT,
                             base_alignment=True)
            lb.anchor_point = (0.0, 0.0)
            lb.anchored_position = (8, 16 + i * _LH)
            self._g.append(lb)
            self._ils.append(lb)
        self._load_save()
        if self._rid and self._rid in self._idx:
            self._enter(self._rid)
        else:
            self._enter(self._start)

    def get_group(self):
        return self._g

    def _build_idx(self):
        with open(self._fp, "r") as f:
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if line.startswith("@TITLE "):
                    self._title = line[7:]
                elif line.startswith("@START "):
                    self._start = line[7:]
                elif line.startswith("@ROOM "):
                    self._idx[line[6:]] = pos

    def _load_room(self, rid):
        off = self._idx.get(rid)
        if off is None:
            return ["Room not found: " + rid], [], [], [], None, None, 0
        dp, ch, it, oe = [], [], [], []
        go, wi, sd = None, None, 0
        ind, sk = False, False
        with open(self._fp, "r") as f:
            f.seek(off)
            f.readline()
            while True:
                ln = f.readline()
                if not ln:
                    break
                r = ln.strip()
                if r.startswith("@ROOM "):
                    break
                if r.startswith("@IF "):
                    fl = r[4:]
                    neg = fl.startswith("!")
                    if neg:
                        fl = fl[1:]
                    has = fl in self._flags
                    sk = has if neg else not has
                    continue
                if r == "@ENDIF":
                    sk = False
                    continue
                if sk:
                    continue
                if r == "@DESC":
                    ind = True
                    continue
                if r == "@ENDDESC":
                    ind = False
                    continue
                if ind:
                    dp.append(r)
                    continue
                if r.startswith("@CHOICE "):
                    c = self._pc(r[8:])
                    if c:
                        ch.append(c)
                elif r.startswith("@ITEM "):
                    p = r[6:].split('"')
                    if len(p) >= 4:
                        it.append((p[0].strip(), p[1], p[3]))
                elif r.startswith("@ON_ENTER "):
                    rest = r[10:]
                    if rest.startswith("@SET "):
                        oe.append(("s", rest[5:]))
                    elif rest.startswith("@GIVE "):
                        oe.append(("g", rest[6:]))
                elif r.startswith("@GAMEOVER "):
                    go = r[10:].strip('"')
                elif r.startswith("@WIN "):
                    wi = r[5:].strip('"').replace(
                        "{score}", str(self._score))
                elif r.startswith("@SCORE "):
                    try:
                        sd = int(r[7:])
                    except ValueError:
                        pass
        return dp, ch, it, oe, go, wi, sd

    def _pc(self, raw):
        if not raw.startswith('"'):
            return None
        eq = raw.find('"', 1)
        if eq < 0:
            return None
        txt = raw[1:eq]
        rest = raw[eq + 1:].strip()
        ai = rest.find("->")
        if ai < 0:
            return None
        parts = rest[ai + 2:].strip().split()
        tgt = parts[0] if parts else ""
        nd, pu, us, sf = None, None, None, None
        i = 1
        while i < len(parts):
            p = parts[i]
            if p == "@NEED" and i + 1 < len(parts):
                nd = parts[i + 1]; i += 2
            elif p == "@PICKUP" and i + 1 < len(parts):
                pu = parts[i + 1]; i += 2
            elif p == "@USE" and i + 1 < len(parts):
                us = parts[i + 1]; i += 2
            elif p == "@SET" and i + 1 < len(parts):
                sf = parts[i + 1]; i += 2
            else:
                i += 1
        return (txt, tgt, nd, pu, us, sf)

    def _enter(self, rid):
        self._rid = rid
        dp, ch, it, oe, go, wi, sd = self._load_room(rid)
        for a, v in oe:
            if a == "s":
                self._flags.add(v)
            elif a == "g" and v not in self._inv:
                self._inv.append(v)
        if sd:
            self._score += sd
        self._got = go
        self._wt = wi
        vis = []
        for c in ch:
            if not self._cn(c[2]):
                continue
            if c[3] and c[3] in self._inv:
                continue
            vis.append(c)
        for iid, nm, _ in it:
            if iid not in self._inv:
                vis.append(("Take " + nm, rid, None, iid, None, None))
        self._dl = _wrap("\n".join(dp), _CPL)
        self._ch = vis
        self._ds = 0
        self._cc = 0
        self._foc = 'c'
        self._render()
        self._save()

    def _cn(self, need):
        if need is None:
            return True
        if need.startswith("!"):
            k = need[1:]
            return k not in self._flags and k not in self._inv
        return need in self._flags or need in self._inv

    def _render(self):
        self._ii.text = "[{}]".format(len(self._inv)) if self._inv else ""
        if self._got:
            self._rend_end("GAME OVER", self._got)
            return
        if self._wt:
            self._rend_end("YOU WIN!", self._wt)
            return
        for i, lb in enumerate(self._dls):
            idx = self._ds + i
            lb.text = self._dl[idx] if idx < len(self._dl) else ""
        if self._foc == 'd' and len(self._dl) > _DL:
            self._fl.text = "^" if self._ds < len(self._dl) - _DL else ""
        else:
            self._fl.text = ""
        for i in range(_MC):
            if i < len(self._ch):
                c = self._ch[i]
                sel = i == self._cc and self._foc == 'c'
                pf = "> " if sel else "  "
                self._cls[i].text = (pf + c[0])[:_CPL]
                self._cls[i].color = _BRIGHT if sel else _TEXT
                self._crs[i].fill = _HL if sel else _BG
            else:
                self._cls[i].text = ""
                self._crs[i].fill = _BG

    def _rend_end(self, title, text):
        lines = _wrap(text, _CPL)
        for i, lb in enumerate(self._dls):
            if i == 0:
                lb.text = title
                lb.color = _BRIGHT
            elif i - 1 < len(lines):
                lb.text = lines[i - 1]
                lb.color = _TEXT
            else:
                lb.text = ""
        self._cls[0].text = "  Score: {}".format(self._score) if self._score else ""
        self._cls[1].text = "  Press any button"
        for i in range(2, _MC):
            self._cls[i].text = ""
        for r in self._crs:
            r.fill = _BG
        self._ended = True

    def handle_button(self, button):
        if self._ended:
            return 'quit'
        if self._si:
            if button == BTN_UP:
                self._si = False
                self._ibg.y = -DISPLAY_HEIGHT
                for lb in self._ils:
                    lb.text = ""
                return None
            if button == BTN_DOWN and self._inv:
                iid = self._inv[self._ic]
                _, _, it, _, _, _, _ = self._load_room(self._rid)
                desc = "A " + iid.replace("_", " ") + "."
                for ii, _, ex in it:
                    if ii == iid:
                        desc = ex
                        break
                self._ils[0].text = iid.replace("_", " ")
                self._ils[0].color = _BRIGHT
                lines = _wrap(desc, _CPL - 2)
                for i in range(1, len(self._ils)):
                    self._ils[i].text = lines[i - 1] if i - 1 < len(lines) else ""
                    self._ils[i].color = _TEXT
                return None
            return None
        if button == BTN_UP:
            self._si = True
            self._ic = 0
            self._ibg.y = 12
            self._ri()
            return None
        if button == BTN_DOWN:
            if len(self._dl) > _DL:
                self._foc = 'd' if self._foc == 'c' else 'c'
                self._render()
            return None
        if button == BTN_CENTER:
            if self._ch:
                self._sel(self._cc)
            return None
        if button == BTN_LEFT:
            return 'quit'
        return None

    def handle_encoder(self, direction):
        if self._ended:
            return None
        if self._si:
            if self._inv:
                self._ic = (self._ic + direction) % len(self._inv)
                self._ri()
            return None
        if self._foc == 'd':
            mx = max(0, len(self._dl) - _DL)
            self._ds = max(0, min(mx, self._ds + direction))
            self._render()
        else:
            if self._ch:
                self._cc = (self._cc + direction) % len(self._ch)
                self._render()
        return None

    def tick(self, now):
        return False

    def _ri(self):
        self._ils[0].text = "=== Inventory ==="
        self._ils[0].color = _BRIGHT
        if not self._inv:
            self._ils[1].text = "(empty)"
            self._ils[1].color = _LOCKED
            for i in range(2, len(self._ils)):
                self._ils[i].text = ""
            return
        for i in range(1, len(self._ils) - 1):
            idx = i - 1
            if idx < len(self._inv):
                pf = "> " if idx == self._ic else "  "
                self._ils[i].text = pf + self._inv[idx].replace("_", " ")
                self._ils[i].color = _BRIGHT if idx == self._ic else _TEXT
            else:
                self._ils[i].text = ""
        self._ils[-1].text = "Score: {}".format(self._score)
        self._ils[-1].color = _LOCKED

    def _sel(self, idx):
        if idx >= len(self._ch):
            return
        c = self._ch[idx]
        if c[4] and c[4] in self._inv:
            self._inv.remove(c[4])
        if c[3] and c[3] not in self._inv:
            self._inv.append(c[3])
        if c[5]:
            self._flags.add(c[5])
        self._enter(c[1])

    def _save(self):
        try:
            with open("saves/adv_" + self._sn, "w") as f:
                f.write("room={}\n".format(self._rid))
                f.write("inventory={}\n".format(",".join(self._inv)))
                f.write("flags={}\n".format(",".join(sorted(self._flags))))
                f.write("score={}\n".format(self._score))
        except OSError:
            pass

    def _load_save(self):
        try:
            with open("saves/adv_" + self._sn, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("room="):
                        self._rid = line[5:]
                    elif line.startswith("inventory="):
                        v = line[10:]
                        self._inv = [x for x in v.split(",") if x]
                    elif line.startswith("flags="):
                        v = line[6:]
                        self._flags = set(x for x in v.split(",") if x)
                    elif line.startswith("score="):
                        try:
                            self._score = int(line[6:])
                        except ValueError:
                            pass
        except OSError:
            pass

    def destroy(self):
        while len(self._g) > 0:
            self._g.pop()
        self._g = None
