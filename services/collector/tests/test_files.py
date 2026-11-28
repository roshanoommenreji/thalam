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


def test_a_repeated_key_is_a_problem_not_a_silent_last_wins(tmp_path: Path) -> None:
    path = tmp_path / "dup.yaml"
    path.write_text("needs:\n  db: 1\n  db: 2\n", encoding="utf-8")
    assert read_yaml(path, "dup.yaml") == (
        [], [Problem("dup.yaml", "(file)", "duplicate key 'db' at line 3")])


def test_a_repeated_key_is_found_at_any_depth(tmp_path: Path) -> None:
    path = tmp_path / "dup.yaml"
    path.write_text("a:\n  - b: 1\n    c: {d: 1, d: 2}\n", encoding="utf-8")
    _, problems = read_yaml(path, "dup.yaml")
    assert [p.message for p in problems] == ["duplicate key 'd' at line 3"]


def test_a_long_repeated_key_is_capped_in_the_message(tmp_path: Path) -> None:
    path = tmp_path / "dup.yaml"
    path.write_text(f"{'k' * 500}: 1\n{'k' * 500}: 2\n", encoding="utf-8")
    _, problems = read_yaml(path, "dup.yaml")
    assert len(problems) == 1 and len(problems[0].message) < 120


def test_a_yaml_merge_key_is_still_legal(tmp_path: Path) -> None:
    path = tmp_path / "merge.yaml"
    path.write_text("base: &b {x: 1, y: 1}\nd:\n  <<: *b\n  y: 2\n", encoding="utf-8")
    docs, problems = read_yaml(path, "merge.yaml")
    assert problems == []
    assert docs[0]["d"] == {"x": 1, "y": 2}


def test_a_repeated_json_key_is_a_problem(tmp_path: Path) -> None:
    path = tmp_path / "dup.json"
    path.write_text('{"a": {"id": 1, "id": 2}}\n', encoding="utf-8")
    assert read_json(path, "dup.json") == (
        None, [Problem("dup.json", "(file)", "duplicate key 'id'")])


def test_the_same_key_in_two_objects_is_fine(tmp_path: Path) -> None:
    path = tmp_path / "ok.json"
    path.write_text('[{"id": 1}, {"id": 2}]\n', encoding="utf-8")
    assert read_json(path, "ok.json") == ([{"id": 1}, {"id": 2}], [])
