GAME_LIST = [
    ('Sub Hunt', 'sub_hunt'),
    ('Hardball', 'hardball'),
    ('Snake', 'snake'),
    ('Missile Cmd', 'missile_cmd'),
    ('Invaders', 'space_invaders'),
    ('Lunar Lander', 'lunar_lander'),
    ('Asteroids', 'asteroids'),
    ('Adventures', 'adventure'),
]


def launch_game(module_name, hw_display, smallfont):
    """Lazy-import and instantiate a game by module name."""
    if module_name == 'sub_hunt':
        from .sub_hunt import SubHuntGame
        return SubHuntGame(hw_display, smallfont)
    elif module_name == 'hardball':
        from .hardball import HardballGame
        return HardballGame(hw_display, smallfont)
    elif module_name == 'snake':
        from .snake import SnakeGame
        return SnakeGame(hw_display, smallfont)
    elif module_name == 'missile_cmd':
        from .missile_command import MissileCommandGame
        return MissileCommandGame(hw_display, smallfont)
    elif module_name == 'space_invaders':
        from .space_invaders import SpaceInvadersGame
        return SpaceInvadersGame(hw_display, smallfont)
    elif module_name == 'lunar_lander':
        from .lunar_lander import LunarLanderGame
        return LunarLanderGame(hw_display, smallfont)
    elif module_name == 'asteroids':
        from .asteroids import AsteroidsGame
        return AsteroidsGame(hw_display, smallfont)
    elif module_name == 'adventure':
        from .adventure import AdventureSelect
        return AdventureSelect(hw_display, smallfont)
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
