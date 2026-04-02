import pytest
from pico_reader.utils import parse_book_filename, clean_word


class TestParseBookFilename:
    def test_series_author_title_wordcount(self):
        r = parse_book_filename("(Earthsea 1) Ursula K Le Guin - A Wizard Of Earthsea (1835).txt")
        assert r == ("A Wizard Of Earthsea", "Ursula K Le Guin", "Earthsea 1", 1835, "Uncategorized")

    def test_no_series(self):
        r = parse_book_filename("Pierce Brown - Red Rising (5000).txt")
        assert r == ("Red Rising", "Pierce Brown", "", 5000, "Uncategorized")

    def test_missing_wordcount(self):
        r = parse_book_filename("Author - Title.txt")
        assert r == ("Title", "Author", "", 10000, "Uncategorized")

    def test_malformed(self):
        r = parse_book_filename("garbage.txt")
        assert r == ("garbage", "", "", 10000, "Uncategorized")

    def test_empty_filename(self):
        r = parse_book_filename("")
        assert r[0] == ""

    # --- Genre parsing tests ---

    def test_parse_genre_with_series(self):
        r = parse_book_filename("(Earthsea 1) [Fantasy] Ursula K Le Guin - A Wizard Of Earthsea (1835).txt")
        assert r == ("A Wizard Of Earthsea", "Ursula K Le Guin", "Earthsea 1", 1835, "Fantasy")

    def test_parse_genre_without_series(self):
        r = parse_book_filename("[Science Fiction] Andy Weir - The Martian (3500).txt")
        assert r == ("The Martian", "Andy Weir", "", 3500, "Science Fiction")

    def test_parse_no_genre_defaults_uncategorized(self):
        r = parse_book_filename("Terry Pratchett - Guards Guards (9200).txt")
        assert r == ("Guards Guards", "Terry Pratchett", "", 9200, "Uncategorized")

    def test_parse_genre_and_series_together(self):
        r = parse_book_filename("(Red Rising 1) [Science Fiction] Pierce Brown - Red Rising (5000).txt")
        assert r == ("Red Rising", "Pierce Brown", "Red Rising 1", 5000, "Science Fiction")

    def test_parse_malformed_bracket_falls_back(self):
        """Missing closing ] should fall back gracefully without crashing."""
        r = parse_book_filename("[Broken Author - Title (100).txt")
        # ValueError from index(']') is caught by outer except
        # Falls back to full filename as title
        assert r[0] == "[Broken Author - Title (100).txt"
        assert r[4] == "Uncategorized"


class TestCleanWord:
    def test_smart_double_quotes(self):
        assert clean_word("\u201cHello\u201d") == '"Hello"'

    def test_smart_apostrophe(self):
        assert clean_word("it\u2019s") == "it's"

    def test_left_single_quote(self):
        assert clean_word("\u2018twas") == "'twas"

    def test_normal_text(self):
        assert clean_word("hello") == "hello"

    def test_empty(self):
        assert clean_word("") == ""
