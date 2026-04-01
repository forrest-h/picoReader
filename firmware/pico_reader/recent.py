MAX_RECENT = 10


def load_recent():
    """Load recent order from file. Returns list of filenames, most recent first."""
    try:
        with open("saves/recent_order.txt", 'r') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        return lines[:MAX_RECENT]
    except OSError:
        return []


def update_recent(filename):
    """Add filename to top of recent list. Removes duplicate if present. Writes to disk."""
    recent = load_recent()
    if filename in recent:
        recent.remove(filename)
    recent.insert(0, filename)
    recent = recent[:MAX_RECENT]
    with open("saves/recent_order.txt", 'w') as f:
        for name in recent:
            f.write(name + '\n')
    return recent
