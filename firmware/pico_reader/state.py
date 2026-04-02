import time
from .constants import DEFAULT_WPM, DEFAULT_BRIGHTNESS
from .settings import DEFAULTS


def calculate_word_delay(word, base_wpm, is_paragraph_start, ramp_factor):
    """Calculate display duration for a word based on complexity multipliers.

    Multipliers stack multiplicatively:
      - long word (>8 chars): 1.3x
      - short word (<=3 chars): 0.8x
      - comma/semicolon/colon ending: 1.5x
      - sentence end (.!?): 1.8x
      - paragraph start: 1.4x
    """
    effective_wpm = base_wpm * ramp_factor
    delay = 60.0 / effective_wpm
    multiplier = 1.0

    stripped = word.rstrip('"\')')
    if not stripped:
        return delay

    if len(word) > 8:
        multiplier *= 1.3
    elif len(word) <= 3:
        multiplier *= 0.8

    last_char = stripped[-1]
    if last_char in '.!?':
        multiplier *= 1.8
    elif last_char in ',;:':
        multiplier *= 1.5

    if is_paragraph_start:
        multiplier *= 1.4

    return delay * multiplier


class AppState:
    MODE_MENU = 0
    MODE_READER = 1
    MODE_DISPLAY = 2
    MODE_JUMP = 3
    MODE_BRIGHTNESS = 4
    MODE_STATS = 5
    MODE_PALETTE = 6
    MODE_FONT = 7

    def __init__(self, settings=None):
        self.mode = self.MODE_MENU
        self.playing = False
        self.finished = False
        self.wpm = DEFAULT_WPM
        self.speed = 60.0 / DEFAULT_WPM
        self.brightness = DEFAULT_BRIGHTNESS
        self.theme_index = 0
        self.book_stats = None
        self.session_stats = None
        self.smart_pacing = False
        self.play_start_time = 0.0
        self._next_word_delay = 60.0 / DEFAULT_WPM
        self.jump_pct = 0
        self.font_preview_idx = 0
        self.active_animations = set()
        self.menu_state = None  # Set after menu tree is built in main()
        self.orp_mode = None  # None, 'color', or 'bold'
        self.skin_name = 'default'
        self.font_name = DEFAULTS['font']
        self.settings = settings if settings else dict(DEFAULTS)
        if settings:
            self.theme_index = int(settings.get('palette', '0'))
            self.brightness = int(settings.get('brightness', str(DEFAULT_BRIGHTNESS)))
            self.smart_pacing = settings.get('smart_pacing', 'off') == 'on'
            self.skin_name = settings.get('skin', 'default')
            self.font_name = settings.get('font', DEFAULTS['font'])
            orp_val = settings.get('orp', 'off')
            if orp_val == 'color':
                self.orp_mode = 'color'
            elif orp_val == 'bold':
                self.orp_mode = 'bold'
            else:
                self.orp_mode = None
            anim_val = settings.get('animation', 'off')
            if anim_val and anim_val != 'off':
                self.active_animations = set(anim_val.split(','))

    def set_wpm(self, wpm):
        self.wpm = max(10, wpm)
        self.speed = 60.0 / self.wpm

    def start_playing(self):
        """Set playing to True and record start time for ramp-up."""
        self.playing = True
        self.play_start_time = time.monotonic()

    def get_ramp_factor(self):
        """Return WPM ramp factor: 0.5 -> 1.0 over 10 seconds.

        When smart_pacing is off, always returns 1.0.
        """
        if not self.smart_pacing:
            return 1.0
        elapsed = time.monotonic() - self.play_start_time
        ramp = min(1.0, elapsed / 10.0)
        return 0.5 + 0.5 * ramp
