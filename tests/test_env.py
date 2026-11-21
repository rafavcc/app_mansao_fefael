import os

from app.env import load_env_file


def _clear(monkeypatch, *keys):
    for key in keys:
        # setenv first so monkeypatch restores the unset state after the test
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)


def test_loads_values_ignoring_comments_and_blank_lines(tmp_path, monkeypatch):
    _clear(monkeypatch, "CASA_X", "CASA_Y")
    env = tmp_path / ".env"
    env.write_text("# c\n\nCASA_X=1\nexport CASA_Y = two \n")
    load_env_file(env)
    assert os.environ["CASA_X"] == "1"
    assert os.environ["CASA_Y"] == "two"


def test_strips_quotes(tmp_path, monkeypatch):
    _clear(monkeypatch, "CASA_Q", "CASA_R")
    env = tmp_path / ".env"
    env.write_text("CASA_Q=\"a b\"\nCASA_R='c'\n")
    load_env_file(env)
    assert os.environ["CASA_Q"] == "a b"
    assert os.environ["CASA_R"] == "c"


def test_real_environment_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("CASA_X", "env")
    env = tmp_path / ".env"
    env.write_text("CASA_X=file\n")
    load_env_file(env)
    assert os.environ["CASA_X"] == "env"


def test_missing_file_is_ignored(tmp_path):
    load_env_file(tmp_path / "nope")


def test_value_may_contain_equals(tmp_path, monkeypatch):
    _clear(monkeypatch, "CASA_K")
    env = tmp_path / ".env"
    env.write_text("CASA_K=a=b\n")
    load_env_file(env)
    assert os.environ["CASA_K"] == "a=b"
