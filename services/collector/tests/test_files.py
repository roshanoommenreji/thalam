"""The shared hardened YAML reader, called directly."""
# covers: SPEC-002-R6

from __future__ import annotations

from pathlib import Path

from thalam_collector.files import MAX_FILE_BYTES, read_yaml
from thalam_collector.problems import Problem


def test_a_good_two_document_file_reads(tmp_path: Path) -> None:
    path = tmp_path / "ok.yaml"
    path.write_text("a: 1\n---\nb: 2\n", encoding="utf-8")
    assert read_yaml(path, "ok.yaml") == ([{"a": 1}, {"b": 2}], [])


def test_bad_utf8_is_one_problem(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_bytes(b"a: \xff\xfe\n")
    assert read_yaml(path, "bad.yaml") == ([], [Problem("bad.yaml", "(file)", "not UTF-8")])


def test_an_oversize_file_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "big.yaml"
    path.write_bytes(b"# " + b"x" * MAX_FILE_BYTES + b"\n")
    assert read_yaml(path, "big.yaml") == (
        [], [Problem("big.yaml", "(file)", "larger than 1 MiB")])
