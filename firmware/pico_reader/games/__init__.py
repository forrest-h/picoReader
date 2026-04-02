GAME_LIST = [
    ('Sub Hunt', 'sub_hunt'),
    ('Hardball', 'hardball'),
]


def launch_game(module_name, hw_display, smallfont):
    """Lazy-import and instantiate a game by module name."""
    if module_name == 'sub_hunt':
        from .sub_hunt import SubHuntGame
        return SubHuntGame(hw_display, smallfont)
    elif module_name == 'hardball':
        from .hardball import HardballGame
        return HardballGame(hw_display, smallfont)
    return None


def load_high_score(game_name):
    try:
        with open("saves/game_{}".format(game_name), 'r') as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def save_high_score(game_name, score):
    try:
        with open("saves/game_{}".format(game_name), 'w') as f:
            f.write(str(score))
    except OSError:
        pass
