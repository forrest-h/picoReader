"""Shared fixtures for epub2pico tests.

Provides mock epub book objects, sample HTML, and TOC structures
without requiring actual .epub files on disk.
"""

from unittest.mock import MagicMock
import pytest
import ebooklib
from ebooklib import epub


@pytest.fixture
def mock_epub_book():
    """Factory fixture that creates a mock ebooklib Book with configurable metadata.

    Usage:
        book = mock_epub_book(
            author="Author Name",
            title="Book Title",
            series="Series Name",
            series_index="1",
            genre="Fantasy",
            spine_items=[...],
            toc=[...],
        )
    """
    def _factory(
        author=None,
        title=None,
        series=None,
        series_index=None,
        genre=None,
        spine_items=None,
        toc=None,
    ):
        book = MagicMock()

        # Metadata
        def get_metadata(ns, key):
            if ns == 'DC':
                if key == 'creator':
                    return [(author, {})] if author else []
                elif key == 'title':
                    return [(title, {})] if title else []
                elif key == 'subject':
                    return [(genre, {})] if genre else []
            elif ns == 'OPF':
                if key == 'meta':
                    metas = []
                    if series:
                        metas.append(('', {'name': 'calibre:series', 'content': series}))
                    if series_index:
                        metas.append(('', {'name': 'calibre:series_index', 'content': series_index}))
                    return metas
            return []

        book.get_metadata = get_metadata

        # TOC
        book.toc = toc or []

        # Spine
        if spine_items:
            book.spine = [(item['id'], item.get('linear', 'yes')) for item in spine_items]

            items_by_id = {}
            for si in spine_items:
                item = MagicMock()
                item.get_name.return_value = si.get('href', si['id'] + '.xhtml')
                item.get_type.return_value = ebooklib.ITEM_DOCUMENT
                html = si.get('html', '<html><body><p>Text</p></body></html>')
                item.get_content.return_value = html.encode('utf-8')
                items_by_id[si['id']] = item

            book.get_item_with_id = lambda item_id: items_by_id.get(item_id)
        else:
            book.spine = []
            book.get_item_with_id = lambda item_id: None

        return book

    return _factory


@pytest.fixture
def sample_html_chapter():
    """Returns a realistic HTML string from a typical epub chapter."""
    return """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 1</title></head>
<body>
<h1>Chapter 1: The Beginning</h1>
<p>It was a dark and stormy night. The wind howled through the trees.</p>
<p>Sarah pulled her coat tighter and stepped outside into the rain.</p>
<p>"Where are you going?" called a voice from behind her.</p>
<p>She didn't answer. She just kept walking.</p>
</body>
</html>"""


@pytest.fixture
def sample_copyright_html():
    """Returns HTML for a typical copyright page."""
    return """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Copyright</title></head>
<body>
<p>Copyright 2023 by John Author</p>
<p>All rights reserved. No part of this publication may be reproduced.</p>
<p>Published by Example Press</p>
<p>ISBN 978-0-123456-78-9</p>
<p>Printed in the United States of America</p>
<p>First Edition: January 2023</p>
</body>
</html>"""


@pytest.fixture
def sample_toc():
    """Returns a nested TOC structure for testing flattening."""
    # Simulates: Part 1 > [Chapter 1, Chapter 2], Part 2 > [Chapter 3]
    ch1 = MagicMock()
    ch1.href = "chapter1.xhtml"
    ch1.title = "Chapter 1: The Beginning"

    ch2 = MagicMock()
    ch2.href = "chapter2.xhtml"
    ch2.title = "Chapter 2: The Journey"

    ch3 = MagicMock()
    ch3.href = "chapter3.xhtml#section1"
    ch3.title = "Chapter 3: The End"

    part1 = MagicMock()
    part1.href = "part1.xhtml"
    part1.title = "Part 1"

    part2 = MagicMock()
    part2.href = "part2.xhtml"
    part2.title = "Part 2"

    return [
        (part1, [ch1, ch2]),
        (part2, [ch3]),
    ]
