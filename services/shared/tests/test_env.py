"""Settings by name: the environment first, then .env, for that one name only."""

from __future__ import annotations

from pathlib import Path

import pytest
from thalam_shared.env import MissingSetting, setting


def _env_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_environment_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THALAM_X", "from-env")
    assert setting("THALAM_X", _env_file(tmp_path, "THALAM_X=from-file\n")) == "from-env"


def test_dot_env_is_read_for_that_name_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("THALAM_X", raising=False)
    path = _env_file(tmp_path, "# a comment\nTHALAM_X=one\nOTHER=two\n")
    assert setting("THALAM_X", path) == "one"


def test_quotes_and_trailing_comments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("A", "B"):
        monkeypatch.delenv(name, raising=False)
    path = _env_file(tmp_path, 'A="has # inside"\nB=plain # a note\n')
    assert setting("A", path) == "has # inside"
    assert setting("B", path) == "plain"


def test_a_missing_setting_names_itself(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("THALAM_NOPE", raising=False)
    with pytest.raises(MissingSetting) as caught:
        setting("THALAM_NOPE", tmp_path / "absent.env")
    assert caught.value.args[0] == "THALAM_NOPE"


def test_dot_env_is_read_like_the_sandbox_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("A", "B", "C"):
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / ".env"
    path.write_text("export A=1\nB=\"x y\" # a note\nC='z' # note\n", encoding="utf-8-sig")
    assert setting("A", path) == "1"
    assert setting("B", path) == "x y"
    assert setting("C", path) == "z"


def test_an_empty_value_in_dot_env_counts_as_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("THALAM_EMPTY", raising=False)
    with pytest.raises(MissingSetting) as caught:
        setting("THALAM_EMPTY", _env_file(tmp_path, "THALAM_EMPTY=\n"))
    assert caught.value.args[0] == "THALAM_EMPTY"


def test_an_empty_environment_variable_does_not_hide_dot_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("THALAM_X", "")
    assert setting("THALAM_X", _env_file(tmp_path, "THALAM_X=one\n")) == "one"
