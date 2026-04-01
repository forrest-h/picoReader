import digitalio
import busio
import sdcardio
import storage
import displayio
import pwmio
import rotaryio
from adafruit_st7735r import ST7735R
from .constants import (PIN_SPI_CLK, PIN_SPI_MOSI, PIN_SPI_MISO,
    PIN_DISPLAY_DC, PIN_DISPLAY_RST, PIN_DISPLAY_CS, PIN_SD_CS,
    PIN_ENC_A, PIN_ENC_B, PIN_BACKLIGHT, PIN_COM,
    DISPLAY_WIDTH, DISPLAY_HEIGHT, DEFAULT_BRIGHTNESS, PWM_FREQ)


def init_hardware():
    # COM pins (unused, set to output)
    for pin in PIN_COM:
        p = digitalio.DigitalInOut(pin)
        p.switch_to_output()

    displayio.release_displays()

    spi = busio.SPI(clock=PIN_SPI_CLK, MOSI=PIN_SPI_MOSI, MISO=PIN_SPI_MISO)
    display_bus = displayio.FourWire(spi, command=PIN_DISPLAY_DC,
                                     chip_select=PIN_DISPLAY_CS, reset=PIN_DISPLAY_RST)
    hw_display = ST7735R(display_bus, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT,
                         rotation=270, colstart=2, rowstart=1, auto_refresh=False)

    sdcard = sdcardio.SDCard(spi, PIN_SD_CS)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, "/sd")

    backlight = pwmio.PWMOut(PIN_BACKLIGHT, frequency=PWM_FREQ,
                             duty_cycle=int(DEFAULT_BRIGHTNESS / 100 * 65535))

    encoder = rotaryio.IncrementalEncoder(PIN_ENC_A, PIN_ENC_B, divisor=2)

    return hw_display, backlight, spi, encoder
