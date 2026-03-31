"""Shim for CircuitPython 'pwmio' module."""
from _bridge import post_message


class PWMOut:
    def __init__(self, pin, frequency=500, duty_cycle=0):
        self._duty_cycle = duty_cycle
        self._frequency = frequency

    @property
    def duty_cycle(self):
        return self._duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value):
        self._duty_cycle = value
        brightness = round(value / 65535 * 100)
        post_message({"type": "brightness", "value": brightness})

    @property
    def frequency(self):
        return self._frequency

    def deinit(self):
        pass
