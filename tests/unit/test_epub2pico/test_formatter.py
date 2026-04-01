"""Tests for epub2pico.formatter -- metadata extraction and filename generation."""

import pytest

from epub2pico.formatter import (
    format_filename,
    sanitize_filename,
    extract_metadata,
    get_calibre_meta,
)


class TestFormatFilename:
    """Test filename generation from metadata."""

    def test_full_metadata(self):
        """Full metadata: series, genre, author, title."""
        meta = {
            'author': 'James S.A. Corey',
            'title': 'Leviathan Wakes',
            'series': 'The Expanse',
            'series_index': '1',
            'genre': 'Science Fiction',
        }
        result = format_filename(meta, 186423)
        assert result == '(The Expanse 1) [Science Fiction] James S.A. Corey - Leviathan Wakes (186423).txt'

    def test_no_series(self):
        """No series: genre, author, title."""
        meta = {
            'author': 'John Author',
            'title': 'Great Book',
            'series': None,
            'series_index': None,
            'genre': 'Mystery',
        }
        result = format_filename(meta, 45200)
        assert result == '[Mystery] John Author - Great Book (45200).txt'

    def test_no_genre(self):
        """No genre: series, author, title."""
        meta = {
            'author': 'Patrick Rothfuss',
            'title': 'The Name of the Wind',
            'series': 'The Kingkiller Chronicle',
            'series_index': '1',
            'genre': None,
        }
        result = format_filename(meta, 248532)
        assert result == '(The Kingkiller Chronicle 1) Patrick Rothfuss - The Name of the Wind (248532).txt'

    def test_no_series_no_genre(self):
        """No series, no genre: just author - title."""
        meta = {
            'author': 'Ursula K. Le Guin',
            'title': 'The Left Hand of Darkness',
            'series': None,
            'series_index': None,
            'genre': None,
        }
        result = format_filename(meta, 72610)
        assert result == 'Ursula K. Le Guin - The Left Hand of Darkness (72610).txt'

    def test_no_author(self):
        """No author: uses 'Unknown'."""
        meta = {
            'author': 'Unknown',
            'title': 'Mystery Book',
            'series': None,
            'series_index': None,
            'genre': 'Mystery',
        }
        result = format_filename(meta, 45200)
        assert result == '[Mystery] Unknown - Mystery Book (45200).txt'

    def test_series_without_index(self):
        """Series name but no index number."""
        meta = {
            'author': 'Author Name',
            'title': 'Book Title',
            'series': 'Cool Series',
            'series_index': None,
            'genre': None,
        }
        result = format_filename(meta, 50000)
        assert result == '(Cool Series) Author Name - Book Title (50000).txt'

    def test_fractional_series_index(self):
        """Series index is a fraction like '2.5'."""
        meta = {
            'author': 'Author',
            'title': 'Title',
            'series': 'Series',
            'series_index': '2.5',
            'genre': None,
        }
        result = format_filename(meta, 10000)
        assert result == '(Series 2.5) Author - Title (10000).txt'

    def test_integer_series_index_as_float(self):
        """Series index '1.0' should be formatted as '1'."""
        meta = {
            'author': 'Author',
            'title': 'Title',
            'series': 'Series',
            'series_index': '1.0',
            'genre': None,
        }
        result = format_filename(meta, 10000)
        assert result == '(Series 1) Author - Title (10000).txt'

    def test_integer_series_index(self):
        """Series index '3' stays as '3'."""
        meta = {
            'author': 'Author',
            'title': 'Title',
            'series': 'Series',
            'series_index': '3',
            'genre': None,
        }
        result = format_filename(meta, 10000)
        assert result == '(Series 3) Author - Title (10000).txt'


class TestSanitizeFilename:
    """Test FAT32 filename sanitization."""

    def test_illegal_characters_replaced(self):
        """Characters illegal on FAT32 are replaced with underscores."""
        result = sanitize_filename('Book: A Story? <Yes>')
        assert ':' not in result
        assert '?' not in result
        assert '<' not in result
        assert '>' not in result

    def test_colons_replaced(self):
        """Colons in titles are replaced."""
        meta = {
            'author': 'Author',
            'title': 'Book: Subtitle',
            'series': None,
            'series_index': None,
            'genre': None,
        }
        result = format_filename(meta, 10000)
        assert ':' not in result
        assert 'Book' in result
        assert 'Subtitle' in result

    def test_question_marks_replaced(self):
        """Question marks in titles are replaced."""
        meta = {
            'author': 'Author',
            'title': 'What Now?',
            'series': None,
            'series_index': None,
            'genre': None,
        }
        result = format_filename(meta, 10000)
        assert '?' not in result

    def test_multiple_spaces_collapsed(self):
        """Multiple consecutive spaces/underscores are collapsed."""
        result = sanitize_filename('Too   Many   Spaces')
        assert '   ' not in result

    def test_double_underscores_collapsed(self):
        """Double underscores from replacements are collapsed."""
        # : and / both become _, adjacent illegal chars shouldn't make "__"
        result = sanitize_filename('A:/B')
        assert '__' not in result


class TestExtractMetadata:
    """Test metadata extraction from mock epub books."""

    def test_full_metadata(self, mock_epub_book):
        book = mock_epub_book(
            author='Author Name',
            title='Book Title',
            series='Series Name',
            series_index='1',
            genre='Fantasy',
        )
        meta = extract_metadata(book)
        assert meta['author'] == 'Author Name'
        assert meta['title'] == 'Book Title'
        assert meta['series'] == 'Series Name'
        assert meta['series_index'] == '1'
        assert meta['genre'] == 'Fantasy'

    def test_missing_author(self, mock_epub_book):
        book = mock_epub_book(title='Book Title')
        meta = extract_metadata(book)
        assert meta['author'] == 'Unknown'

    def test_missing_title_with_fallback(self, mock_epub_book):
        book = mock_epub_book(author='Author')
        meta = extract_metadata(book, fallback_title='fallback_name')
        assert meta['title'] == 'fallback_name'

    def test_missing_series(self, mock_epub_book):
        book = mock_epub_book(author='Author', title='Title')
        meta = extract_metadata(book)
        assert meta['series'] is None
        assert meta['series_index'] is None

    def test_missing_genre(self, mock_epub_book):
        book = mock_epub_book(author='Author', title='Title')
        meta = extract_metadata(book)
        assert meta['genre'] is None


class TestGetCalibreMeta:
    """Test Calibre metadata extraction from OPF meta tags."""

    def test_calibre_series(self, mock_epub_book):
        book = mock_epub_book(series='The Expanse', series_index='1')
        result = get_calibre_meta(book, 'calibre:series')
        assert result == 'The Expanse'

    def test_calibre_series_index(self, mock_epub_book):
        book = mock_epub_book(series='The Expanse', series_index='1')
        result = get_calibre_meta(book, 'calibre:series_index')
        assert result == '1'

    def test_calibre_meta_missing(self, mock_epub_book):
        book = mock_epub_book(author='Author', title='Title')
        result = get_calibre_meta(book, 'calibre:series')
        assert result is None
