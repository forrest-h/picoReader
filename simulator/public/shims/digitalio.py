"""Shim for CircuitPython 'digitalio' module."""


class DigitalInOut:
    def __init__(self, pin):
        self.pin = pin

    def switch_to_output(self):
        pass

    def deinit(self):
        pass
