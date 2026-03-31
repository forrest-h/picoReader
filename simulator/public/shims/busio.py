"""Shim for CircuitPython 'busio' module."""


class SPI:
    def __init__(self, clock=None, MOSI=None, MISO=None):
        pass

    def deinit(self):
        pass
