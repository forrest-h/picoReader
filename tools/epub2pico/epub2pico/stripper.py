"""Content stripping heuristics for cleaned epub text.

Removes junk content (copyright pages, page numbers, dividers, etc.)
while preserving actual story content. Conservative by design -- it is
better to leave a stray page number than to eat a paragraph.
"""

import re
from dataclasses import dataclass, field


@dataclass
class StrippedSection:
    """Record of a section that was stripped from the text."""
    reason: str       # e.g. "copyright_page", "page_number", "divider"
    content: str      # The actual text that was removed
    line_range: tuple  # (start_line, end_line) in the original text


# --- Individual heuristic functions ---

COPYRIGHT_KEYWORDS = [
    "copyright",
    "all rights reserved",
    "isbn",
    "published by",
    "library of congress",
    "printed in",
]


def detect_copyright_blocks(lines):
    """Detect copyright page blocks.

    A copyright block is a contiguous set of paragraph-separated lines
    where 2+ copyright keywords appear in the block.
    """
    stripped = []
    blocks = _split_into_blocks(lines)

    for start, end, block_text in blocks:
        lower = block_text.lower()
        matches = sum(1 for kw in COPYRIGHT_KEYWORDS if kw in lower)
        if matches >= 2:
            stripped.append(StrippedSection(
                reason="copyright_page",
                content=block_text,
                line_range=(start, end),
            ))

    return stripped


def detect_page_numbers(lines):
    """Detect standalone page number lines.

    Matches: "42", "  42  ", "- 42 -", " -42- "
    Does NOT match lines with other content.
    """
    stripped = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        # Bare number: "42"
        if re.match(r'^\d{1,4}$', s):
            stripped.append(StrippedSection(
                reason="page_number",
                content=line,
                line_range=(i, i),
            ))
        # Formatted: "- 42 -"
        elif re.match(r'^-\s*\d+\s*-$', s):
            stripped.append(StrippedSection(
                reason="page_number",
                content=line,
                line_range=(i, i),
            ))

    return stripped


def detect_dividers(lines):
    """Detect decorative separator lines.

    Matches: "---", "***", "===", "* * *", "- - -", etc.
    Does NOT match lines that contain other text content (like em-dashes
    within sentences).
    """
    stripped = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        # Three or more of the same separator character
        if re.match(r'^[-*=]{3,}$', s):
            stripped.append(StrippedSection(
                reason="divider",
                content=line,
                line_range=(i, i),
            ))
        # Spaced pattern: "* * *" or "- - -"
        elif re.match(r'^(\*\s+){2,}\*$', s) or re.match(r'^(-\s+){2,}-$', s):
            stripped.append(StrippedSection(
                reason="divider",
                content=line,
                line_range=(i, i),
            ))

    return stripped


def detect_toc_duplicates(lines, chapter_titles):
    """Detect table-of-contents text reproduced in the body.

    A TOC duplicate is a contiguous sequence of short lines (< 40 chars)
    where >60% of non-empty lines match known chapter titles.
    """
    if not chapter_titles:
        return []

    stripped = []
    title_set = {t.strip().lower() for t in chapter_titles if t.strip()}
    if not title_set:
        return []

    # Scan for candidate sequences of short lines (separated by blank lines)
    i = 0
    while i < len(lines):
        # Find start of a candidate block of short non-empty lines
        if len(lines[i].strip()) > 40 or not lines[i].strip():
            i += 1
            continue

        # Collect consecutive non-empty short lines (stop at blank lines)
        block_start = i
        block_lines = []
        while i < len(lines) and lines[i].strip() and len(lines[i].strip()) <= 40:
            block_lines.append(lines[i].strip())
            i += 1

        if len(block_lines) < 3:
            continue

        # Check what fraction match chapter titles
        matches = sum(1 for bl in block_lines if bl.lower() in title_set)
        ratio = matches / len(block_lines)

        if ratio > 0.6:
            block_end = block_start + len(block_lines) - 1
            block_text = "\n".join(lines[block_start:block_end + 1])
            stripped.append(StrippedSection(
                reason="toc_duplicate",
                content=block_text,
                line_range=(block_start, block_end),
            ))

    return stripped


def detect_repeated_headers(lines, chapter_marker_prefix="---CHAPTER:"):
    """Detect running headers/footers repeated at chapter boundaries.

    Short lines (< 30 chars) appearing identically at 3+ chapter boundaries.
    """
    stripped = []

    # Find chapter boundary indices
    chapter_indices = []
    for i, line in enumerate(lines):
        if line.strip().startswith(chapter_marker_prefix):
            chapter_indices.append(i)

    if len(chapter_indices) < 3:
        return []

    # For each chapter boundary, collect short lines within 3 lines
    boundary_lines = {}  # text -> list of line indices
    for ci in chapter_indices:
        for offset in range(-3, 4):
            idx = ci + offset
            if idx < 0 or idx >= len(lines) or idx == ci:
                continue
            text = lines[idx].strip()
            if text and len(text) < 30 and not text.startswith(chapter_marker_prefix):
                if text not in boundary_lines:
                    boundary_lines[text] = []
                boundary_lines[text].append(idx)

    # Lines appearing at 3+ chapter boundaries
    for text, indices in boundary_lines.items():
        # Deduplicate to unique chapter boundaries
        boundary_count = len(set(
            min(chapter_indices, key=lambda ci: abs(ci - idx))
            for idx in indices
        ))
        if boundary_count >= 3:
            for idx in indices:
                stripped.append(StrippedSection(
                    reason="repeated_header",
                    content=lines[idx],
                    line_range=(idx, idx),
                ))

    return stripped


def strip_content(text, chapter_titles=None):
    """Apply all stripping heuristics to the text.

    Returns (cleaned_text, list[StrippedSection]).

    Heuristics are applied in order:
    1. Copyright pages (paragraph-level)
    2. TOC duplicates (block-level)
    3. Page numbers (line-level)
    4. Dividers (line-level)
    5. Repeated headers (line-level)
    """
    lines = text.split('\n')
    all_stripped = []

    # Collect all sections to strip
    all_stripped.extend(detect_copyright_blocks(lines))
    all_stripped.extend(detect_toc_duplicates(lines, chapter_titles or []))
    all_stripped.extend(detect_page_numbers(lines))
    all_stripped.extend(detect_dividers(lines))
    all_stripped.extend(detect_repeated_headers(lines))

    # Build set of lines to remove
    lines_to_remove = set()
    for section in all_stripped:
        start, end = section.line_range
        for i in range(start, end + 1):
            lines_to_remove.add(i)

    # Rebuild text without removed lines
    cleaned_lines = [
        line for i, line in enumerate(lines)
        if i not in lines_to_remove
    ]

    # Clean up excessive blank lines (more than 2 consecutive)
    cleaned_text = _collapse_blank_lines("\n".join(cleaned_lines))

    return cleaned_text, all_stripped


# --- Helper functions ---

def _split_into_blocks(lines):
    """Split lines into paragraph blocks separated by blank lines.

    Returns list of (start_line, end_line, block_text).
    """
    blocks = []
    i = 0
    while i < len(lines):
        # Skip blank lines
        if not lines[i].strip():
            i += 1
            continue

        # Collect non-blank lines
        start = i
        block_lines = []
        while i < len(lines) and lines[i].strip():
            block_lines.append(lines[i])
            i += 1

        blocks.append((start, i - 1, "\n".join(block_lines)))

    return blocks


def _collapse_blank_lines(text):
    """Collapse more than 2 consecutive blank lines into exactly 2."""
    return re.sub(r'\n{4,}', '\n\n\n', text)
