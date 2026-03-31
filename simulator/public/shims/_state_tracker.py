"""Tracks application state and sends updates to the main thread.

The state tracker is initialized after code_v2.py creates its objects.
We hook into it by having the worker set references after main() starts.
For now, we use a polling approach: on each display.refresh(), we try
to read state from well-known global variables.
"""
from _bridge import post_message

# These get set by a small wrapper around code_v2.py's main()
_app_state = None
_book_reader = None
_book_metadata = None


def register(state, book, metadata=None):
    """Register the application objects for state tracking."""
    global _app_state, _book_reader, _book_metadata
    _app_state = state
    _book_reader = book
    _book_metadata = metadata


def send_state():
    """Send current state to the main thread."""
    if _app_state is None:
        return

    msg = {
        "type": "state",
        "mode": _app_state.mode,
        "wpm": _app_state.wpm,
        "playing": _app_state.playing,
        "finished": _app_state.finished,
        "themeIndex": _app_state.theme_index,
        "brightness": _app_state.brightness,
        "bookId": 0,
        "lineNum": 0,
        "wordIdx": 0,
        "bookLen": 0,
        "bookTitle": "",
        "bookAuthor": "",
    }

    if _book_reader is not None:
        msg["bookId"] = _book_reader.book_id
        msg["lineNum"] = _book_reader.line_num
        msg["wordIdx"] = _book_reader.word_idx
        msg["bookLen"] = _book_reader.book_len

        if _book_metadata and _book_reader.book_id < len(_book_metadata):
            meta = _book_metadata[_book_reader.book_id]
            msg["bookTitle"] = meta[0] if len(meta) > 0 else ""
            msg["bookAuthor"] = meta[1] if len(meta) > 1 else ""

    post_message(msg)
