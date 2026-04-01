"""Animation registry with lazy imports.

Only one animation module loaded at a time to conserve RAM.
"""

ANIMATION_NAMES = ['off', 'walker', 'particles', 'page_turn']


def load_animation(name):
    """Return an Animation instance for *name*, or None for 'off'."""
    if name == 'walker':
        from .walker import Animation
    elif name == 'particles':
        from .particles import Animation
    elif name == 'page_turn':
        from .page_turn import Animation
    else:
        return None
    return Animation()
