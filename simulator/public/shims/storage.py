"""Shim for CircuitPython 'storage' module."""
import os


class VfsFat:
    def __init__(self, sdcard):
        pass


def mount(vfs, path):
    pass


def remount(path, readonly):
    pass
