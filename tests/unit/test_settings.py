import pytest
from pico_reader.settings import load_settings, save_settings, set_setting, DEFAULTS


class TestLoadSettings:
    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        s = load_settings()
        assert s == DEFAULTS

    def test_partial_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        (tmp_path / "saves" / "settings.txt").write_text("skin:terminal\n")
        s = load_settings()
        assert s['skin'] == 'terminal'
        assert s['brightness'] == '50'

    def test_full_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        content = "skin:rpg\npalette:2\norp:color\nanimation:walker\nfont:Bitter-Regular-14.pcf\nsmart_pacing:on\nbrightness:80\n"
        (tmp_path / "saves" / "settings.txt").write_text(content)
        s = load_settings()
        assert s['skin'] == 'rpg'
        assert s['palette'] == '2'
        assert s['orp'] == 'color'
        assert s['animation'] == 'walker'
        assert s['font'] == 'Bitter-Regular-14.pcf'
        assert s['smart_pacing'] == 'on'
        assert s['brightness'] == '80'

    def test_unknown_keys_ignored(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        (tmp_path / "saves" / "settings.txt").write_text("bogus:value\nskin:rpg\n")
        s = load_settings()
        assert 'bogus' not in s
        assert s['skin'] == 'rpg'


class TestSaveSettings:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        original = dict(DEFAULTS)
        original['skin'] = 'terminal'
        original['brightness'] = '75'
        save_settings(original)
        loaded = load_settings()
        assert loaded == original


class TestSetSetting:
    def test_persists_immediately(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        s = dict(DEFAULTS)
        set_setting(s, 'brightness', '75')
        assert s['brightness'] == '75'
        loaded = load_settings()
        assert loaded['brightness'] == '75'

    def test_updates_dict(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "saves").mkdir()
        s = dict(DEFAULTS)
        set_setting(s, 'skin', 'typewriter')
        assert s['skin'] == 'typewriter'
