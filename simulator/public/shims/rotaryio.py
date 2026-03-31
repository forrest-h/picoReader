"""Shim for CircuitPython 'rotaryio' module."""
from _bridge import get_encoder_position


class IncrementalEncoder:
    def __init__(self, pin_a, pin_b, divisor=1):
        self._divisor = divisor

    @property
    def position(self):
        return get_encoder_position()
