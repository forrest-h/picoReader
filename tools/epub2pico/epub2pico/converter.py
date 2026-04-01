"""Epub to ordered chapter text extraction.

Reads an epub file, extracts chapters in spine order, converts HTML to
plain text, and inserts chapter markers.
"""

import re

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from .stripper import StrippedSection


# Epub types to skip (front/back matter)
SKIP_EPUB_TYPES = {
    'frontmatter', 'titlepage', 'colophon', 'index',
    'toc', 'loi', 'lot',  # list of illustrations, list of tables
    'backmatter',
}


def read_epub(epub_path):
    """Read an epub file and return the book object."""
    return epub.read_epub(str(epub_path))


def build_toc_map(toc):
    """Flatten nested TOC into { href: title } map.

    The epub TOC can be nested (parts containing chapters). We flatten
    it to a simple href -> title mapping. Fragment identifiers in hrefs
    are stripped for matching.
    """
    result = {}
    for entry in toc:
        if isinstance(entry, tuple):
            # Nested: (Section, [children])
            section, children = entry
            href = _strip_fragment(section.href) if section.href else None
            if href:
                result[href] = section.title
            result.update(build_toc_map(children))
        else:
            # Leaf: Link object
            href = _strip_fragment(entry.href) if entry.href else None
            if href:
                result[href] = entry.title
    return result


def should_skip_spine_item(item, book):
    """Check if a spine item should be skipped based on epub:type.

    Returns (should_skip, reason) tuple.
    """
    content = item.get_content().decode('utf-8', errors='replace')
    soup = BeautifulSoup(content, 'lxml')

    # Check epub:type attributes on the body or root elements
    for tag in soup.find_all(True):
        epub_type = tag.get('epub:type', '') or tag.get('epub_type', '')
        if epub_type:
            types = set(epub_type.lower().split())
            overlap = types & SKIP_EPUB_TYPES
            if overlap:
                return True, "epub:type={}".format(", ".join(overlap))

    return False, ""


def extract_chapters(book):
    """Extract chapters in spine order, mapping to TOC for titles.

    Returns (chapters, skipped_sections) where:
    - chapters is a list of dicts with 'title', 'html', 'href' keys
    - skipped_sections is a list of StrippedSection for front/back matter
    """
    toc_map = build_toc_map(book.toc)

    chapters = []
    skipped_sections = []

    for item_id, linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None:
            continue
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        # Check if this spine item should be skipped
        if linear == 'no':
            html = item.get_content().decode('utf-8', errors='replace')
            skipped_sections.append(StrippedSection(
                reason="front_matter",
                content="[linear=no] {}".format(item.get_name()),
                line_range=(0, 0),
            ))
            continue

        should_skip, reason = should_skip_spine_item(item, book)
        if should_skip:
            skipped_sections.append(StrippedSection(
                reason="front_matter",
                content="[{}] {}".format(reason, item.get_name()),
                line_range=(0, 0),
            ))
            continue

        href = item.get_name()
        bare_href = _strip_fragment(href)
        title = toc_map.get(bare_href, "")
        html = item.get_content().decode('utf-8', errors='replace')

        chapters.append({
            'title': title,
            'html': html,
            'href': href,
        })

    return chapters, skipped_sections


def html_to_text(html):
    """Convert HTML to plain text preserving paragraph structure.

    Uses BeautifulSoup with lxml to handle malformed epub HTML.
    Block-level elements become double-newline separated paragraphs.
    """
    soup = BeautifulSoup(html, 'lxml')

    # Remove script, style, nav elements
    for tag in soup.find_all(['script', 'style', 'nav']):
        tag.decompose()

    # Get text from block-level elements
    blocks = []
    for element in soup.find_all(
        ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote']
    ):
        text = element.get_text(separator=' ', strip=True)
        if text:
            # Normalize internal whitespace
            text = re.sub(r'\s+', ' ', text)
            blocks.append(text)

    # If no block elements found, fall back to raw text extraction
    if not blocks:
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text

    return "\n\n".join(blocks)


def chapters_to_text(chapters):
    """Convert extracted chapters to full text with chapter markers.

    Chapters with a title get a ---CHAPTER: title--- marker.
    Chapters with no title (continuation sections) get no marker.
    Empty chapters (no text after conversion) are silently dropped.
    """
    parts = []
    for chapter in chapters:
        text = html_to_text(chapter['html'])
        if not text.strip():
            continue

        if chapter.get('title'):
            parts.append("---CHAPTER: {}---".format(chapter['title']))
            parts.append("")
            parts.append(text)
        else:
            parts.append(text)

        parts.append("")
        parts.append("")

    return "\n".join(parts).strip()


def count_words(text):
    """Count words in the text, excluding chapter markers."""
    count = 0
    for line in text.split('\n'):
        if line.strip().startswith("---CHAPTER:") and line.strip().endswith("---"):
            continue
        count += len(line.split())
    return count


def _strip_fragment(href):
    """Strip fragment identifier from an href (e.g., 'ch1.xhtml#sec2' -> 'ch1.xhtml')."""
    if '#' in href:
        return href.split('#', 1)[0]
    return href
