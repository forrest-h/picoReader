import pytest
from pico_reader.utils import parse_book_filename, clean_word


class TestParseBookFilename:
    def test_series_author_title_wordcount(self):
        r = parse_book_filename("(Earthsea 1) Ursula K Le Guin - A Wizard Of Earthsea (1835).txt")
        assert r == ("A Wizard Of Earthsea", "Ursula K Le Guin", "Earthsea 1", 1835)

    def test_no_series(self):
        r = parse_book_filename("Pierce Brown - Red Rising (5000).txt")
        assert r == ("Red Rising", "Pierce Brown", "", 5000)

    def test_missing_wordcount(self):
        r = parse_book_filename("Author - Title.txt")
        assert r == ("Title", "Author", "", 10000)

    def test_malformed(self):
        r = parse_book_filename("garbage.txt")
        assert r == ("garbage", "", "", 10000)

    def test_empty_filename(self):
        r = parse_book_filename("")
        assert r[0] == ""


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
