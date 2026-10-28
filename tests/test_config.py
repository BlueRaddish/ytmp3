"""Bad persisted input fails clearly, and interrupted saves preserve old data."""
from unittest.mock import patch

import pytest

from ytmp3.cli import main
from ytmp3.config import Config


@pytest.mark.parametrize("data", [
    [], {"default": []}, {"template": []}, {"dest": []},
    {"dest": {"music": []}}, {"dest": {"music": {}}},
    {"dest": {"music": {"target": 42}}},
    {"dest": {"music": {"target": "   "}}},
    {"dest": {"music": {"target": "gdrive:music", "template": []}}},
])
def test_invalid_config_types_are_actionable(tmp_path, data):
    with pytest.raises(ValueError, match="config"):
        Config(data, tmp_path / "config.toml")


def test_missing_empty_and_malformed_config(tmp_path, monkeypatch, capsys):
    path = tmp_path / "한글 folder" / "config.toml"
    monkeypatch.setenv("YTMP3_CONFIG", str(path))
    assert Config.load().dests == {}
    path.parent.mkdir()
    path.write_text("", encoding="utf-8")
    assert Config.load().dests == {}
    path.write_text("[not valid", encoding="utf-8")
    assert main(["dest", "list"]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_atomic_config_save_preserves_old_file_on_failure(tmp_path):
    path = tmp_path / "한글 folder" / "config.toml"
    config = Config({"default": "music", "dest": {"music": {"target": "gdrive:music"}}}, path)
    config.save()
    original = path.read_bytes()
    config.default = "other"
    with patch("ytmp3.config.os.replace", side_effect=PermissionError("locked")):
        with pytest.raises(PermissionError):
            config.save()
    assert path.read_bytes() == original
    assert list(path.parent.iterdir()) == [path]
    config.save()
    assert 'default = "other"' in path.read_text(encoding="utf-8")
