import board
import digitalio
import rotaryio
import asyncio
import time
import keypad
import busio
import sdcardio
import storage
import terminalio
import displayio
from adafruit_display_text import label
from adafruit_st7735r import ST7735R
from adafruit_bitmap_font import bitmap_font
from adafruit_display_shapes.rect import Rect
from adafruit_itertools import islice
import os 
import pwmio

COMA = board.GP12
COMB = board.GP7





com_a = digitalio.DigitalInOut(COMA)
com_a.switch_to_output()
com_a = False
com_b = digitalio.DigitalInOut(COMB)
com_b.switch_to_output()
com_b = False

font = bitmap_font.load_font("fonts/Toronto_14.pcf")
smallfont = bitmap_font.load_font("fonts/Toronto_9.pcf")

def parse_book_filename(filename):
    """Parse '(Series) Author - Title (wordcount).txt' into components."""
    try:
        name = filename.rsplit('.', 1)[0]  # remove .txt
        parts = name.split(' - ', 1)       # split on first ' - '
        if len(parts) == 2:
            author_part, title_part = parts
            if author_part.startswith('('):
                close = author_part.find(')')
                series = author_part[1:close]
                author = author_part[close+1:].strip()
            else:
                series = ''
                author = author_part.strip()
            paren = title_part.rfind('(')
            if paren != -1:
                title = title_part[:paren].strip()
                wordcount = int(title_part[paren+1:title_part.rfind(')')])
            else:
                title = title_part.strip()
                wordcount = 10000
        else:
            title, author, series, wordcount = name, '', '', 10000
    except (IndexError, ValueError):
        title, author, series, wordcount = filename, '', '', 10000
    return title, author, series, wordcount
    


class eReader:
    DEFAULT_WPM = 200
    DEFAULT_BRIGHTNESS = 50
    PWM_FREQ = 5000
    BATCH_SIZE = 10
    SAVE_INTERVAL = 50

    #BG, Text, WPM, Highlight — BGR format (https://wamingo.net/rgbbgr/)
    THEMES = [
        [0x000000, 0xe7e7e7, 0x4c4c4c, 0x7c7c7c],
        [0xf3f3f3, 0x000000, 0xa1a1a1, 0x949494],
        [0x696969, 0x000000, 0x272727, 0x403f3f],
        [0x460808, 0xbdbdbd, 0x898888, 0x0e8ee6],
        [0x000000, 0x696969, 0x4c4c4c, 0x696969],
    ]

    def __init__(self):

        self.mode = 'menu'
        self.modes = ['menu', 'display', 'reader']

        self.wpm = self.DEFAULT_WPM
        self.speed = 60 / self.wpm
        self.encoder = rotaryio.IncrementalEncoder(board.GP14, board.GP13, divisor = 2)
        self.last_position = 0

        self.dutyc = self.DEFAULT_BRIGHTNESS

        self.ledback = pwmio.PWMOut(board.GP16, frequency=self.PWM_FREQ, duty_cycle=int(self.dutyc / 100 * 65535))

        self.pins = [board.GP11, board.GP9,  board.GP10, board.GP8, board.GP6]
        self.buttons = {
            0:True,
            1:False,
            2:False,
            3:False,
            4:False
            }

        displayio.release_displays()

        spi = busio.SPI(clock=board.GP2, MOSI=board.GP3, MISO=board.GP4)
        display_bus = displayio.FourWire(spi, command=board.GP17, chip_select=board.GP19, reset=board.GP18)
        self.display = ST7735R(display_bus, width=160, height=128, rotation=270, colstart=2, rowstart=1, auto_refresh=False)

        cs = board.GP15
        sdcard = sdcardio.SDCard(spi, cs)
        vfs = storage.VfsFat(sdcard)
        storage.mount(vfs, "/sd")

        self.display_count = 0
        self.progress_bar = 0
        self._build_reader_group()
        self.menu_dirty = True

        self.books = [x for x in os.listdir("/sd/books/") if x.endswith('.txt')]

        if len(self.books) == 0:
            self.text_area.text = "{:^30}".format("No books found")
            splash = displayio.Group()
            self.display.show(splash)
            color_bitmap = displayio.Bitmap(160, 128, 1)
            color_palette = displayio.Palette(1)
            color_palette[0] = 0x000000
            splash.append(displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0))
            splash.append(self.text_area)
            self.display.refresh()
            while True:
                pass

        self.book = self.books[0]

        self.book_metadata = [parse_book_filename(b) for b in self.books]
        self.book_lens = [m[3] for m in self.book_metadata]
        
        try:
            with open("saves/save_{}".format(self.book), "r") as savefile:
                line = savefile.read()
                places = int(line)
        except (OSError, ValueError):
            places = 0

        self.places = places
        self.word_index = 0
        self.booklen = self.book_lens[0]

        self.switch_line = False
        self.nav_lock = asyncio.Lock()
        self.cached_line_num = -1
        self.cached_line_words = []

        self.bookid = 0
        self.menu_type = 'books'
        


    def _build_reader_group(self):
        theme = self.THEMES[self.display_count]
        bgcolor, textcolor, wpmcolor, highlight = theme

        self.reader_group = displayio.Group()

        color_bitmap = displayio.Bitmap(160, 128, 1)
        self.bg_palette = displayio.Palette(1)
        self.bg_palette[0] = bgcolor
        bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=self.bg_palette, x=0, y=0)
        self.reader_group.append(bg_sprite)           # index 0: background

        self.text_area = label.Label(font, text="{:^30}".format(''), color=textcolor, base_alignment=False)
        self.text_area.anchor_point = (0.5, 1)
        self.text_area.anchored_position = (80, 70)
        self.reader_group.append(self.text_area)       # index 1: word

        self.guide_top = Rect(67, 42, 21, 1, fill=highlight)
        self.guide_bottom = Rect(67, 84, 21, 1, fill=highlight)
        self.guide_top_ind = Rect(77, 42, 1, 6, fill=highlight)
        self.guide_bottom_ind = Rect(77, 78, 1, 6, fill=highlight)
        self.reader_group.append(self.guide_top)       # index 2
        self.reader_group.append(self.guide_bottom)    # index 3
        self.reader_group.append(self.guide_top_ind)   # index 4
        self.reader_group.append(self.guide_bottom_ind)# index 5

        self.progress_rect = Rect(0, 0, max(1, self.progress_bar), 2, fill=highlight)
        self.reader_group.append(self.progress_rect)   # index 6

        self.wpm_text = label.Label(smallfont, text="{}".format(self.wpm), color=wpmcolor, base_alignment=False)
        self.wpm_text.anchor_point = (0.0, 1.0)
        self.wpm_text.anchored_position = (0, 128)
        self.reader_group.append(self.wpm_text)        # index 7

    def update_reader_theme(self):
        theme = self.THEMES[self.display_count]
        bgcolor, textcolor, wpmcolor, highlight = theme
        self.bg_palette[0] = bgcolor
        self.text_area.color = textcolor
        self.wpm_text.color = wpmcolor
        self.guide_top.fill = highlight
        self.guide_bottom.fill = highlight
        self.guide_top_ind.fill = highlight
        self.guide_bottom_ind.fill = highlight
        self.progress_rect.fill = highlight

    def show_reader(self):
        self.display.show(self.reader_group)
        self.update_reader_theme()
        self.display.refresh()

    def update_progress_bar(self, line):
        prog = max(1, int(line / self.booklen * 160))
        highlight = self.THEMES[self.display_count][3]
        self.reader_group[6] = Rect(0, 0, prog, 2, fill=highlight)
        self.progress_rect = self.reader_group[6]
        self.display.refresh()

    def change_display(self):
        self.display_count += 1
        if self.display_count >= len(self.THEMES):
            self.display_count = 0
        self.update_reader_theme()
        self.text_area.text = "{:^30}".format("picoReader")
        self.display.refresh()

    def _load_line(self, places):
        if places == self.cached_line_num:
            return self.cached_line_words
        with open("/sd/books/{}".format(self.book), 'r') as book:
            result = list(islice(book, places, places + 1))
        if result:
            self.cached_line_words = result[0].strip().split()
        else:
            self.cached_line_words = []
        self.cached_line_num = places
        return self.cached_line_words

    def _invalidate_line_cache(self):
        self.cached_line_num = -1
        self.cached_line_words = []

    def clean_word(self, word):
        return word.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")


    def set_mode(self, new_mode):
        if new_mode not in self.modes:
            return
        if self.mode == 'reader':
            self.save_place()
        self.mode = new_mode
        if new_mode == 'menu':
            self.menu_dirty = True

    def set_speed(self):
        self.speed = 60/self.wpm
        #print(self.speed)

    def update_wpm(self, wpm):
        self.wpm = wpm
        self.set_speed()
        
    def change_backlight(self, adding):
        self.dutyc += adding
        if self.dutyc < 1:
            self.dutyc = 1
        if self.dutyc > 100:
            self.dutyc = 100
        self.ledback.duty_cycle = int(self.dutyc / 100 * 65535)
        print(self.dutyc)

    def save_place(self):
        #print("save!")
        with open("saves/save_{}".format(self.book), 'w') as savefile:
            savefile.write("{}".format(self.places))
            
            
    def _book_info(self, index):
        if index < 0 or index >= len(self.books):
            return '', '', ''
        return self.book_metadata[index][:3]

    def update_book(self):
        
        
                              
        self.book = self.books[self.bookid]
        self.booklen = self.book_lens[self.bookid]
        try:
            with open("saves/save_{}".format(self.book), "r") as savefile:
                line = savefile.read()
                places = int(line)
        except (OSError, ValueError):
            with open("saves/save_{}".format(self.book), "w") as savefile:
                savefile.write("0")
                places = 0

        self.places = places
        self.word_index = 0
        self._invalidate_line_cache()
        self.menu_dirty = True
        self.menu_screen()


    def menu_screen(self):
        SELECT_COLORS = (0x000000, 0xf1f1f1, 0x000000)   # text, bg, border
        OTHER_COLORS  = (0x909090, 0x323232, 0x3b3b3b)
        MAINBG = 0x323232

        splash = displayio.Group()
        self.display.show(splash)
        color_bitmap = displayio.Bitmap(160, 128, 1)
        color_palette = displayio.Palette(1)
        color_palette[0] = MAINBG
        splash.append(displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0))

        title_label = label.Label(font, text='picoReader', color=0xffffff, base_alignment=False)
        title_label.anchor_point = (0.5, 0.5)
        title_label.anchored_position = (80, 10)
        splash.append(title_label)

        select = self.bookid

        # Compute 3-item visible window and which slot is selected
        if select <= 1:
            indices = [0, 1, 2]
            highlighted = select
        else:
            indices = [select - 1, select, select + 1]
            highlighted = 1

        # Slot layout: (y_position, height, max_label_count)
        SLOTS = [(20, 40, 3), (60, 40, 3), (100, 28, 2)]

        for slot, (y, h, max_labels) in enumerate(SLOTS):
            book_title, book_author, book_series = self._book_info(indices[slot])
            if not book_title and not book_author:
                continue

            txt_color, bg_color, bdr_color = SELECT_COLORS if slot == highlighted else OTHER_COLORS

            splash.append(Rect(4, y, 152, h, fill=bg_color, outline=bdr_color, stroke=2))

            lbl = label.Label(smallfont, text=book_title, color=txt_color, base_alignment=True)
            lbl.anchor_point = (0.5, 0.5)
            lbl.anchored_position = (80, y + 10)
            splash.append(lbl)

            lbl = label.Label(smallfont, text=book_author, color=txt_color, base_alignment=True)
            lbl.anchor_point = (0.5, 0.5)
            lbl.anchored_position = (80, y + 20)
            splash.append(lbl)

            if max_labels >= 3:
                lbl = label.Label(smallfont, text=book_series, color=txt_color, base_alignment=True)
                lbl.anchor_point = (0.5, 0.5)
                lbl.anchored_position = (80, y + 30)
                splash.append(lbl)

        self.display.refresh()



async def reader(eReader):

    with open("saves/save_prev_{}".format(eReader.book), 'w+') as savefile:
        savefile.write("{}".format(eReader.places))


    last_p = eReader.places
    last_u = eReader.places
    temp1 = 0

    while True:
    #try:
        #print("working")
        if eReader.mode == 'reader':
            playing = eReader.buttons[0]
            if playing:
                if eReader.places > last_p:
                    last_p += eReader.SAVE_INTERVAL
                    eReader.save_place()
                if eReader.places > last_u:
                    last_u += eReader.SAVE_INTERVAL
                    eReader.update_progress_bar(eReader.places)

                with open("/sd/books/{}".format(eReader.book), 'r') as book:
                    lines = list(islice(book, eReader.places, eReader.places + eReader.BATCH_SIZE))

                current_line = eReader.places
                for line in lines:

                    if len(line) > 1:

                        for i,word in enumerate(line.strip().split()):
                            if eReader.buttons[0] == True:
                                if eReader.word_index == i:
                                    if len(word) > 17:
                                        for wordx in word.split('-'):
                                            eReader.text_area.text = "{:^30}".format(eReader.clean_word(wordx) + '-')
                                            eReader.wpm_text.text = "{}".format(eReader.wpm)
                                            eReader.display.refresh()
                                            await asyncio.sleep(eReader.speed)
                                    else:
                                        eReader.text_area.text = "{:^30}".format(eReader.clean_word(word))
                                        eReader.wpm_text.text = "{}".format(eReader.wpm)
                                        eReader.display.refresh()

                                    eReader.word_index += 1
                                    if eReader.word_index >= len(line.strip().split()):
                                        eReader.word_index = 0
                                    await asyncio.sleep(eReader.speed)
                            else:
                                eReader.places = max(0, current_line - eReader.BATCH_SIZE)
                                break
                    if eReader.buttons[0] == False:
                        eReader.places = max(0, current_line - eReader.BATCH_SIZE)
                        break
                    current_line += 1

                eReader.places += eReader.BATCH_SIZE

            else:
                await asyncio.sleep(.1)

        elif eReader.mode == 'menu':
            if eReader.menu_dirty:
                eReader.menu_screen()
                eReader.menu_dirty = False
            await asyncio.sleep(.2)

        else:
            await asyncio.sleep(.05)
        #except:
            #with open("saves/save_prev.txt", "r") as savefile:
                #line = savefile.read()
                #eReader.places = int(line)
        #await asyncio.sleep(.01)

async def monitor_buttons(eReader):
    with keypad.Keys(eReader.pins, value_when_pressed = False, pull = True) as keys:
        while True:
            event = keys.events.get()
            if event:
                if eReader.mode == 'reader':
                    if event.key_number == 0:
                        if event.pressed:
                            eReader.save_place()
                            if eReader.buttons[0] == True:
                                eReader.buttons[0] = False
                            else:
                                eReader.buttons[0] = True

                            #print("{}".format(eReader.buttons[0]))

                    elif eReader.buttons[0] == False:
                        if event.key_number == 2:
                            if event.pressed:
                                eReader.set_mode('display')
                                #eReader.change_display()
                                #await asyncio.sleep(.2)
                        if event.key_number == 1:
                            if event.pressed:
                                eReader.set_mode('menu')
                                eReader.menu_screen()
                                #print("menu")
                if eReader.mode == 'display':
                    if event.key_number == 0:
                        eReader.set_mode('reader')
                        if event.pressed:
                            if eReader.buttons[0] == True:
                                eReader.buttons[0] = False
                            else:
                                eReader.buttons[0] = True
                    if event.key_number == 1:
                        if event.pressed:
                            eReader.set_mode('menu')
                            eReader.menu_screen()
                    elif event.key_number == 2:
                        if event.pressed:
                            eReader.change_display()
                    

                else:
                    if event.pressed:
                        #eReader.buttons[event.key_number] = True
                        #print("{} pressed".format(event.key_number))
                        if eReader.mode == "menu":
                            if event.key_number == 0:
                                eReader.set_mode('reader')
                                eReader.show_reader()
                                eReader.buttons[0] = True
                                #print("menu to reader")
                            

                    #else:
                        #eReader.buttons[event.key_number] = False
            await asyncio.sleep(.05)




async def monitor_rotary(eReader):
    while True:
        position = eReader.encoder.position
        if eReader.last_position is None or position != eReader.last_position:
            #print("Position: {}".format(position))


            if eReader.mode == 'reader':
                if eReader.buttons[0] == True:
                    if position > eReader.last_position:
                        wpm = eReader.wpm
                        eReader.update_wpm(wpm + 2)
                    else:
                        wpm = eReader.wpm
                        eReader.update_wpm(wpm - 2)
                else:
                    async with eReader.nav_lock:
                        words = eReader._load_line(eReader.places)
                        if position > eReader.last_position:
                            if len(words) > 0:
                                eReader.word_index += 1
                                if eReader.word_index >= len(words):
                                    eReader.word_index = 0
                                    eReader.places += 1
                                    eReader._invalidate_line_cache()
                                    eReader.save_place()
                                else:
                                    eReader.text_area.text = "{:^30}".format(eReader.clean_word(words[eReader.word_index]))
                                    eReader.wpm_text.text = "{}".format(eReader.wpm)
                                    eReader.display.refresh()
                                    await asyncio.sleep(.05)
                            else:
                                eReader.places += 1
                                eReader._invalidate_line_cache()
                                eReader.save_place()
                                eReader.word_index = 0
                        else:
                            if eReader.switch_line:
                                eReader.switch_line = False
                                eReader.save_place()
                                eReader.word_index = max(len(words), len(words))
                            if len(words) > 0:
                                if eReader.word_index <= -1:
                                    eReader.places = max(0, eReader.places - 1)
                                    eReader._invalidate_line_cache()
                                    eReader.switch_line = True
                                elif eReader.word_index < len(words):
                                    eReader.text_area.text = "{:^30}".format(eReader.clean_word(words[eReader.word_index]))
                                    eReader.wpm_text.text = "{}".format(eReader.wpm)
                                    eReader.display.refresh()
                                    eReader.word_index -= 1
                                else:
                                    eReader.word_index -= 1
                                    if eReader.word_index <= -1:
                                        eReader.places = max(0, eReader.places - 1)
                                        eReader._invalidate_line_cache()
                                        eReader.switch_line = True
                            else:
                                eReader.places = max(0, eReader.places - 1)
                                eReader._invalidate_line_cache()
                                eReader.switch_line = True







                eReader.last_position = position

            elif eReader.mode == 'menu':
                if eReader.menu_type == 'books':
                    if position > eReader.last_position:
                        eReader.bookid += 1
                    else:
                        eReader.bookid -= 1
                        
                    if eReader.bookid == len(eReader.books):
                        eReader.bookid = 0
                        
                    elif eReader.bookid < 0:
                        eReader.bookid = len(eReader.books) - 1
                    #print("Position: {}".format(position))
                    eReader.update_book()
                    eReader.last_position = position
                elif eReader.menu_type == 'author':
                    pass
            elif eReader.mode == 'display':
                if position > eReader.last_position:
                    eReader.change_backlight(2)
                else:
                    eReader.change_backlight(-2)
                eReader.last_position = position
                
                
        await asyncio.sleep(.05)




async def main(eReader):
    rotary_task = asyncio.create_task(monitor_rotary(eReader))
    button_task = asyncio.create_task(monitor_buttons(eReader))
    reader_task = asyncio.create_task(reader(eReader))


    await asyncio.gather(rotary_task, button_task, reader_task)


eread = eReader()
asyncio.run(main(eread))
