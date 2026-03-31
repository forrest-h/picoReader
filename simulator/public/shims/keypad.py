"""Shim for CircuitPython 'keypad' module."""
from _bridge import get_button_queue


class Event:
    def __init__(self, key_number, pressed):
        self.key_number = key_number
        self.pressed = pressed


class EventQueue:
    def __init__(self):
        self._events = []

    def get(self):
        # Poll the JS-side button queue
        new_events = get_button_queue()
        for ev in new_events:
            self._events.append(Event(ev["keyNumber"], ev["pressed"]))

        if self._events:
            return self._events.pop(0)
        return None


class Keys:
    def __init__(self, pins, value_when_pressed=False, pull=True):
        self._pins = pins
        self.events = EventQueue()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def deinit(self):
        pass
