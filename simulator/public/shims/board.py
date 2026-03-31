"""Shim for CircuitPython 'board' module - pin definitions."""


class Pin:
    def __init__(self, name):
        self.id = name

    def __repr__(self):
        return f"board.{self.id}"


# SPI
GP2 = Pin("GP2")
GP3 = Pin("GP3")
GP4 = Pin("GP4")

# Display
GP17 = Pin("GP17")
GP18 = Pin("GP18")
GP19 = Pin("GP19")

# SD Card
GP15 = Pin("GP15")

# Encoder
GP14 = Pin("GP14")
GP13 = Pin("GP13")

# Backlight
GP16 = Pin("GP16")

# Buttons
GP11 = Pin("GP11")
GP9 = Pin("GP9")
GP10 = Pin("GP10")
GP8 = Pin("GP8")
GP6 = Pin("GP6")

# COM pins
GP12 = Pin("GP12")
GP7 = Pin("GP7")
