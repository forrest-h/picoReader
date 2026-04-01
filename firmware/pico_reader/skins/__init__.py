SKIN_NAMES = ['default', 'terminal', 'rpg', 'typewriter']


def load_skin(name):
    """Lazy-import and return Skin class. Only one skin in RAM at a time."""
    if name == 'default':
        from .default import Skin
    elif name == 'terminal':
        from .terminal import Skin
    elif name == 'rpg':
        from .rpg import Skin
    elif name == 'typewriter':
        from .typewriter import Skin
    else:
        from .default import Skin
    return Skin
