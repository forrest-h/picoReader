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
    The ORP letter is centered at anchor_x (screen center).

    Positioning strategy:
      - prefix: right-anchored so its right edge meets the ORP left edge
      - orp_char: centered at anchor_x
      - suffix: left-anchored so its left edge meets the ORP right edge
    Callers must set anchor_point accordingly:
      - prefix label: anchor_point = (1.0, y) at prefix_x
      - orp label: anchor_point = (0.5, y) at orp_x
      - suffix label: anchor_point = (0.0, y) at suffix_x
    """
    idx = calc_orp_index(word)
    prefix = word[:idx]
    orp_char = word[idx]
    suffix = word[idx + 1:]

    # Get ORP character width from font glyph metrics
    orp_width = font.get_glyph(ord(orp_char)).shift_x

    # ORP char centered at anchor_x
    orp_x = anchor_x

    # Prefix right edge meets ORP left edge (with 1px gap)
    prefix_x = anchor_x - orp_width // 2 - 1

    # Suffix left edge meets ORP right edge (with 1px gap)
    suffix_x = anchor_x + (orp_width + 1) // 2 + 1

    # Clamp to screen bounds
    prefix_x = max(5, prefix_x)
    suffix_x = min(155, suffix_x)

    return prefix, orp_char, suffix, prefix_x, orp_x, suffix_x


def calc_bold_split(word):
    """Return (bold_part, fade_part) for Bold-Fade ORP mode."""
    split = max(1, int(len(word) * 0.4))
    return word[:split], word[split:]
