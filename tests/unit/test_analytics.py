import os
import time
from unittest.mock import patch

import pytest
from pico_reader.analytics import BookStats, SessionStats


class TestBookStatsDefaults:
    def test_fresh_stats_defaults(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        assert bs.words_read == 0
        assert bs.sessions == 0

    def test_missing_file_defaults(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("nonexistent.txt")
        assert bs.words_read == 0
        assert bs.sessions == 0


class TestBookStatsIncrement:
    def test_increment_word(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        for _ in range(5):
            bs.increment_word()
        assert bs.words_read == 5

    def test_start_session(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.start_session()
        assert bs.sessions == 1
        # start_session writes to disk
        assert os.path.exists(str(saves_dir / "stats_mybook.txt"))


class TestBookStatsSaveLoad:
    def test_save_load_round_trip(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 1234
        bs.sessions = 7
        bs.save()

        bs2 = BookStats("mybook.txt")
        assert bs2.words_read == 1234
        assert bs2.sessions == 7

    def test_corrupted_file(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        with open(str(saves_dir / "stats_bad.txt"), 'w') as f:
            f.write("garbage data\nmore garbage\n")
        bs = BookStats("bad.txt")
        assert bs.words_read == 0
        assert bs.sessions == 0

    def test_partially_corrupted_file(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        with open(str(saves_dir / "stats_partial.txt"), 'w') as f:
            f.write("words_read:500\nsessions:not_a_number\n")
        bs = BookStats("partial.txt")
        # ValueError on sessions line causes _load to abort,
        # but words_read was already parsed
        assert bs.words_read == 500
        assert bs.sessions == 0


class TestBookStatsDerived:
    def test_words_remaining(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 3000
        assert bs.words_remaining(10000) == 7000

    def test_words_remaining_clamped(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 12000
        assert bs.words_remaining(10000) == 0

    def test_estimated_minutes(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 3000
        assert bs.estimated_minutes(200, 10000) == 35

    def test_estimated_minutes_zero_wpm(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 3000
        assert bs.estimated_minutes(0, 10000) == 0

    def test_estimated_minutes_negative_wpm(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 3000
        assert bs.estimated_minutes(-10, 10000) == 0

    def test_completion_pct(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 5000
        assert bs.completion_pct(10000) == 50

    def test_completion_pct_zero_total(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 100
        assert bs.completion_pct(0) == 0

    def test_completion_pct_capped_at_100(self, tmp_path, monkeypatch):
        saves_dir = tmp_path / "saves"
        saves_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        bs = BookStats("mybook.txt")
        bs.words_read = 15000
        assert bs.completion_pct(10000) == 100


class TestSessionStats:
    def test_record_word_increments(self):
        ss = SessionStats()
        ss.record_word(200)
        assert ss.words == 1
        ss.record_word(220)
        assert ss.words == 2

    def test_average_wpm(self):
        ss = SessionStats()
        ss.record_word(200)
        ss.record_word(220)
        ss.record_word(180)
        assert ss.average_wpm() == 200

    def test_average_wpm_empty(self):
        ss = SessionStats()
        assert ss.average_wpm() == 0

    def test_rolling_window_cap(self):
        ss = SessionStats()
        # Fill with 60 samples of 100
        for _ in range(60):
            ss.record_word(100)
        assert len(ss._wpm_samples) == 60
        assert ss.average_wpm() == 100

        # Add one more at 160 -- oldest (100) should be dropped
        ss.record_word(160)
        assert len(ss._wpm_samples) == 60
        assert ss.words == 61
        # Average: (59 * 100 + 160) / 60 = 6060 / 60 = 101
        assert ss.average_wpm() == 101

    def test_reading_time_minutes(self):
        ss = SessionStats()
        # Simulate 5 minutes elapsed
        ss.start_time = time.monotonic() - 300
        assert ss.reading_time_minutes() == 5

    def test_reading_time_minutes_zero(self):
        ss = SessionStats()
        # Just created, should be 0 minutes
        assert ss.reading_time_minutes() == 0
