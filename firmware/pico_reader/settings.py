DEFAULTS = {
    'skin': 'default',
    'palette': '0',
    'orp': 'off',
    'animation': 'off',
    'font': 'Toronto_14.pcf',
    'smart_pacing': 'off',
    'brightness': '50',
}


def load_settings():
    """Load from saves/settings.txt. Missing keys filled from DEFAULTS."""
    settings = dict(DEFAULTS)
    try:
        with open("saves/settings.txt", 'r') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    key, val = line.split(':', 1)
                    if key in settings:
                        settings[key] = val
    except OSError:
        pass
    return settings


def save_settings(settings):
    """Write all key:value pairs to saves/settings.txt."""
    with open("saves/settings.txt", 'w') as f:
        for key, val in settings.items():
            f.write("{}:{}\n".format(key, val))


def set_setting(settings, key, value):
    """Update one setting and persist immediately."""
    settings[key] = value
    save_settings(settings)
