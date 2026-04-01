from .constants import DEFAULT_WPM, DEFAULT_BRIGHTNESS


class AppState:
    MODE_MENU = 0
    MODE_READER = 1
    MODE_DISPLAY = 2

    def __init__(self, settings=None):
        self.mode = self.MODE_MENU
        self.playing = False
        self.finished = False
        self.wpm = DEFAULT_WPM
        self.speed = 60.0 / DEFAULT_WPM
        self.brightness = DEFAULT_BRIGHTNESS
        self.theme_index = 0
        if settings:
            self.theme_index = int(settings.get('palette', '0'))
            self.brightness = int(settings.get('brightness', str(DEFAULT_BRIGHTNESS)))

    def set_wpm(self, wpm):
        self.wpm = max(10, wpm)
        self.speed = 60.0 / self.wpm
