import pytest
from pico_reader.book_reader import BookReader


class TestStepForward:
    def test_reads_words_in_order(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("hello world foo\n")
        br = BookReader(["test.txt"], [("T", "A", "", 3)], [3])
        assert br.step_forward() == "hello"
        assert br.step_forward() == "world"
        assert br.step_forward() == "foo"

    def test_crosses_lines(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("line one\nline two\n")
        br = BookReader(["test.txt"], [("T", "A", "", 2)], [2])
        assert br.step_forward() == "line"
        assert br.step_forward() == "one"
        assert br.step_forward() == "line"
        assert br.step_forward() == "two"

    def test_returns_none_at_eof(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("only\n")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        assert br.step_forward() == "only"
        assert br.step_forward() is None

    def test_skips_empty_lines(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("first\n\nsecond\n")
        br = BookReader(["test.txt"], [("T", "A", "", 3)], [3])
        assert br.step_forward() == "first"
        assert br.step_forward() == "second"


class TestStepBackward:
    def test_returns_previous(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("one two three\n")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        br.step_forward()  # one (word_idx now 1)
        br.step_forward()  # two (word_idx now 2)
        br.step_forward()  # three (word_idx now 3)
        # step_backward decrements word_idx to 2, returns words[2] = "three"
        assert br.step_backward() == "three"
        # step_backward again: word_idx 1, returns words[1] = "two"
        assert br.step_backward() == "two"

    def test_returns_none_at_start(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("one\n")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        assert br.step_backward() is None


class TestSaveLoad:
    def test_save_writes_line_word(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("a b c\n")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        br.line_num = 5
        br.word_idx = 3
        br.save_place()
        content = (saves_dir / "save_test.txt").read_text()
        assert content == "5:3"

    def test_backup_writes_line_word(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("a\n")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        br.line_num = 10
        br.word_idx = 2
        br.save_backup()
        content = (saves_dir / "save_prev_test.txt").read_text()
        assert content == "10:2"

    def test_load_new_format(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("a\n")
        (saves_dir / "save_test.txt").write_text("5:3")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        br.load_place()
        assert br.line_num == 5
        assert br.word_idx == 3

    def test_load_old_format(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("a\n")
        (saves_dir / "save_test.txt").write_text("42")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        br.load_place()
        assert br.line_num == 42
        assert br.word_idx == 0

    def test_load_missing_file(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "test.txt").write_text("a\n")
        br = BookReader(["test.txt"], [("T", "A", "", 1)], [1])
        br.load_place()
        assert br.line_num == 0
        assert br.word_idx == 0


class TestSelectBook:
    def test_switches_book(self, book_reader_env):
        tmp_path, books_dir, saves_dir = book_reader_env
        (books_dir / "a.txt").write_text("a\n")
        (books_dir / "b.txt").write_text("b\n")
        br = BookReader(
            ["a.txt", "b.txt"],
            [("A", "", "", 1), ("B", "", "", 2)],
            [1, 2],
        )
        br.select_book(1)
        assert br.book == "b.txt"
        assert br.book_len == 2
        assert br.book_id == 1
