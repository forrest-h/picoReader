"""Metadata extraction and filename generation for picoReader .txt files."""

import re


ILLEGAL_CHARS = '<>:"/\\|?*'


def get_calibre_meta(book, name: str):
    """Extract a Calibre metadata value from OPF meta tags.

    Calibre stores series info as OPF <meta> elements:
        <meta name="calibre:series" content="The Expanse"/>
        <meta name="calibre:series_index" content="1"/>

    ebooklib exposes these via book.get_metadata('OPF', 'meta').
    Each entry is (value, attributes_dict).
    """
    for meta in book.get_metadata('OPF', 'meta'):
        attrs = meta[1]  # ebooklib returns (value, attributes)
        if attrs.get('name') == name:
            return attrs.get('content')
    return None


def extract_metadata(book, fallback_title=None):
    """Extract metadata from an epub book object.

    Returns a dict with keys: author, title, series, series_index, genre.
    """
    # Author
    creators = book.get_metadata('DC', 'creator')
    author = creators[0][0] if creators else "Unknown"

    # Title
    titles = book.get_metadata('DC', 'title')
    title = titles[0][0] if titles else (fallback_title or "Unknown")

    # Calibre series metadata
    series = get_calibre_meta(book, 'calibre:series')
    series_index = get_calibre_meta(book, 'calibre:series_index')

    # Genre from subject
    subjects = book.get_metadata('DC', 'subject')
    genre = subjects[0][0] if subjects else None

    return {
        'author': _clean_name(author),
        'title': _clean_title(title),
        'series': series,
        'series_index': series_index,
        'genre': genre,
    }


def _clean_name(name):
    """Clean up an author name."""
    return name.strip()


def _clean_title(title):
    """Clean up a book title."""
    return title.strip()


def format_filename(metadata, word_count):
    """Generate a picoReader-compatible filename from metadata and word count.

    Format: (Series N) [Genre] Author - Title (wordcount).txt

    Components are omitted when their metadata is absent:
    - No series -> no "(Series N) " prefix
    - No genre -> no "[Genre] " prefix
    """
    parts = []

    # Series: "(Series N) " or "(Series) " if no index
    if metadata.get('series'):
        if metadata.get('series_index'):
            idx = metadata['series_index']
            # Format index: "1.0" -> "1", "2.5" -> "2.5"
            try:
                float_idx = float(idx)
                if float_idx == int(float_idx):
                    idx = str(int(float_idx))
                else:
                    idx = str(float_idx)
            except (ValueError, TypeError):
                idx = str(idx)
            parts.append("({} {}) ".format(metadata['series'], idx))
        else:
            parts.append("({}) ".format(metadata['series']))

    # Genre: "[Genre] "
    if metadata.get('genre'):
        parts.append("[{}] ".format(metadata['genre']))

    # Author - Title
    parts.append("{} - {}".format(metadata['author'], metadata['title']))

    # Word count
    parts.append(" ({})".format(word_count))

    # Extension
    parts.append(".txt")

    filename = "".join(parts)
    return sanitize_filename(filename)


def sanitize_filename(name):
    """Replace characters that are illegal on FAT32 filesystems."""
    for ch in ILLEGAL_CHARS:
        name = name.replace(ch, '_')
    # Collapse multiple spaces/underscores
    name = re.sub(r'[_ ]{2,}', ' ', name)
    return name.strip()
