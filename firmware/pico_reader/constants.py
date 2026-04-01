import board

# =============================================================================
# Constants
# =============================================================================

DEFAULT_WPM = 200
DEFAULT_BRIGHTNESS = 50
PWM_FREQ = 5000
SAVE_INTERVAL = 50

# BGR format (https://wamingo.net/rgbbgr/)
# Each theme: [background, text, wpm, highlight]
THEMES = [
    [0x000000, 0xe7e7e7, 0x4c4c4c, 0x7c7c7c],
    [0xf3f3f3, 0x000000, 0xa1a1a1, 0x949494],
    [0x696969, 0x000000, 0x272727, 0x403f3f],
    [0x460808, 0xbdbdbd, 0x898888, 0x0e8ee6],
    [0x000000, 0x696969, 0x4c4c4c, 0x696969],
]

# Display geometry
DISPLAY_WIDTH = 160
DISPLAY_HEIGHT = 128
WORD_CENTER = (80, 70)
WPM_POS = (0, 128)
GUIDE_RECTS = [(67, 42, 21, 1), (67, 84, 21, 1), (77, 42, 1, 6), (77, 78, 1, 6)]
MENU_TITLE_POS = (80, 10)
MENU_SLOTS = [(20, 40), (60, 40), (100, 28)]
MENU_SELECT_COLORS = (0x000000, 0xf1f1f1, 0x000000)   # text, bg, border
MENU_OTHER_COLORS = (0x909090, 0x323232, 0x3b3b3b)
MENU_BG = 0x323232

# Pin assignments
PIN_SPI_CLK = board.GP2
PIN_SPI_MOSI = board.GP3
PIN_SPI_MISO = board.GP4
PIN_DISPLAY_DC = board.GP17
PIN_DISPLAY_RST = board.GP18
PIN_DISPLAY_CS = board.GP19
PIN_SD_CS = board.GP15
PIN_ENC_A = board.GP14
PIN_ENC_B = board.GP13
PIN_BACKLIGHT = board.GP16
# 5-way keypad: CENTER, UP, LEFT, RIGHT, DOWN
PIN_BUTTONS = [board.GP11, board.GP9, board.GP10, board.GP8, board.GP6]
BTN_CENTER = 0  # GP11 — select / play / pause
BTN_UP     = 1  # GP9  — back to menu
BTN_LEFT   = 2  # GP10 — previous theme (when paused)
BTN_RIGHT  = 3  # GP8  — next theme (when paused)
BTN_DOWN   = 4  # GP6  — unused
PIN_COM = [board.GP12, board.GP7]
