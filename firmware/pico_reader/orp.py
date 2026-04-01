"""Shared ORP (Optimal Recognition Point) helper.

Used by all skins to compute the fixation point for RSVP display.
"""


def calc_orp_index(word):
    """Return the index of the ORP letter (roughly 1/3 into the word)."""
    n = len(word)
    if n <= 1:
        return 0
    return min(n - 1, max(1, (n + 1) // 3 - 1))


def calc_orp_positions(word, font, anchor_x=80):
    """Return (prefix, orp_char, suffix, prefix_x, orp_x, suffix_x).

    Uses font glyph metrics to calculate pixel positions.
    The ORP letter is anchored at anchor_x (screen center).
    """
    idx = calc_orp_index(word)
    prefix = word[:idx]
    orp_char = word[idx]
    suffix = word[idx + 1:]

    # Get pixel widths from font glyph metrics
    if prefix:
        prefix_width = sum(font.get_glyph(ord(c)).shift_x for c in prefix)
    else:
        prefix_width = 0
    orp_width = font.get_glyph(ord(orp_char)).shift_x

    prefix_x = anchor_x - prefix_width - orp_width // 2
    orp_x = anchor_x - orp_width // 2
    suffix_x = anchor_x + orp_width // 2

    # Clamp to screen bounds
    prefix_x = max(0, prefix_x)
    suffix_x = min(155, suffix_x)  # Leave 5px margin

    return prefix, orp_char, suffix, prefix_x, orp_x, suffix_x


def calc_bold_split(word):
    """Return (bold_part, fade_part) for Bold-Fade ORP mode."""
    split = max(1, int(len(word) * 0.4))
    return word[:split], word[split:]
