"""Bridge utilities for Python<->JS communication in the Pyodide worker."""
import json
from js import self as _worker_self, JSON as _JSON


def post_message(msg_dict):
    """Post a message to the main thread. Round-trips through JSON to create
    a native JS object (avoids Pyodide dict->Map conversion)."""
    js_obj = _JSON.parse(json.dumps(msg_dict))
    _worker_self.postMessage(js_obj)


def get_button_queue():
    """Read and clear the button event queue populated by JS onmessage handler."""
    queue = _worker_self.__buttonQueue
    result = []
    length = queue.length
    for i in range(length):
        item = queue[i]
        result.append({"keyNumber": item.keyNumber, "pressed": bool(item.pressed)})
    # Clear the queue by splicing
    queue.splice(0, length)
    return result


def get_encoder_position():
    """Read the current encoder position set by JS onmessage handler."""
    return int(_worker_self.__encoderPosition)
