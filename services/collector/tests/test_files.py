"""The shared hardened YAML reader, called directly."""
# covers: SPEC-002-R6

from __future__ import annotations

from pathlib import Path

from thalam_collector.files import MAX_FILE_BYTES, read_json, read_yaml
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


def test_a_good_json_file_reads(tmp_path: Path) -> None:
    path = tmp_path / "ok.json"
    path.write_text('{"a": [1, 2]}\n', encoding="utf-8")
    assert read_json(path, "ok.json") == ({"a": [1, 2]}, [])


def test_bad_utf8_json_is_one_problem(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_bytes(b'{"a": "\xff\xfe"}\n')
    assert read_json(path, "bad.json") == (None, [Problem("bad.json", "(file)", "not UTF-8")])


def test_an_oversize_json_file_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "big.json"
    path.write_bytes(b'["' + b"x" * MAX_FILE_BYTES + b'"]\n')
    assert read_json(path, "big.json") == (
        None, [Problem("big.json", "(file)", "larger than 1 MiB")])


def test_bad_json_names_its_line_and_never_quotes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"a": 1,\n "secret-value": oops}\n', encoding="utf-8")
    data, problems = read_json(path, "bad.json")
    assert data is None
    assert [(p.file, p.field) for p in problems] == [("bad.json", "(file)")]
    assert problems[0].message.startswith("not valid JSON at line 2: ")
    assert "secret-value" not in problems[0].message


def test_deeply_nested_json_is_a_problem_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "deep.json"
    path.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    _, problems = read_json(path, "deep.json")
    assert [p.message for p in problems] == [
        "not valid JSON: a value could not be read (RecursionError)"]


def test_a_missing_json_file_is_unreadable_not_a_crash(tmp_path: Path) -> None:
    _, problems = read_json(tmp_path / "nope.json", "nope.json")
    assert [p.message for p in problems] == ["unreadable: FileNotFoundError"]
