import pytest
from pico_reader.recent import load_recent, update_recent, MAX_RECENT


@pytest.fixture
def recent_env(tmp_path, monkeypatch):
    """Set up saves directory for recent tests."""
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    return saves_dir


class TestLoadRecent:
    def test_no_file(self, recent_env):
        result = load_recent()
        assert result == []

    def test_loads_existing_file(self, recent_env):
        (recent_env / "recent_order.txt").write_text("a.txt\nb.txt\nc.txt\n")
        result = load_recent()
        assert result == ["a.txt", "b.txt", "c.txt"]

    def test_ignores_blank_lines(self, recent_env):
        (recent_env / "recent_order.txt").write_text("a.txt\n\nb.txt\n\n")
        result = load_recent()
        assert result == ["a.txt", "b.txt"]

    def test_caps_at_max_recent(self, recent_env):
        lines = ["book{}.txt".format(i) for i in range(15)]
        (recent_env / "recent_order.txt").write_text("\n".join(lines) + "\n")
        result = load_recent()
        assert len(result) == MAX_RECENT


class TestUpdateRecent:
    def test_adds_to_front(self, recent_env):
        update_recent("first.txt")
        update_recent("second.txt")
        result = load_recent()
        assert result[0] == "second.txt"
        assert result[1] == "first.txt"

    def test_deduplicates(self, recent_env):
        update_recent("a.txt")
        update_recent("b.txt")
        update_recent("a.txt")  # Move to front
        result = load_recent()
        assert result == ["a.txt", "b.txt"]

    def test_caps_at_10(self, recent_env):
        for i in range(11):
            update_recent("book{}.txt".format(i))
        result = load_recent()
        assert len(result) == MAX_RECENT
        assert result[0] == "book10.txt"
        # The first one added (book0) should have been pushed out
        assert "book0.txt" not in result

    def test_round_trip(self, recent_env):
        update_recent("c.txt")
        update_recent("b.txt")
        update_recent("a.txt")
        result = load_recent()
        assert result == ["a.txt", "b.txt", "c.txt"]

    def test_preserves_others(self, recent_env):
        update_recent("a.txt")
        update_recent("b.txt")
        update_recent("c.txt")
        # Now add d -- a, b, c should remain in order after d
        update_recent("d.txt")
        result = load_recent()
        assert result == ["d.txt", "c.txt", "b.txt", "a.txt"]

    def test_returns_updated_list(self, recent_env):
        result = update_recent("test.txt")
        assert result == ["test.txt"]
