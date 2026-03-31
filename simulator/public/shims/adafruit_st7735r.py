"""Shim for adafruit_st7735r — ST7735R display driver."""
from _bridge import post_message
import _state_tracker


class ST7735R:
    def __init__(self, bus, width=160, height=128, rotation=0,
                 colstart=0, rowstart=0, auto_refresh=True, **kwargs):
        self.width = width
        self.height = height
        self.rotation = rotation
        self._root_group = None
        self._auto_refresh = auto_refresh

    def show(self, group):
        self._root_group = group

    def refresh(self):
        if self._root_group is None:
            return
        scene_graph = self._root_group.serialize()
        post_message({"type": "refresh", "sceneGraph": scene_graph})
        # Also send current state if tracker has been initialized
        _state_tracker.send_state()
