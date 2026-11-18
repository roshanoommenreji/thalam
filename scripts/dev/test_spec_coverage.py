"""Tests for the requirement-to-test check (SPEC-001-R8). Each test builds a tiny repository."""
# covers: SPEC-001-R8

from __future__ import annotations

from pathlib import Path

import pytest
from spec_coverage import check, main


def _tag(*ids: str) -> str:
    # Built in pieces so this file's own source never holds a tag: the scan of the real
    # repository reads this file, and these fixture IDs belong to no real spec.
    return "# " + "covers" + ": " + ", ".join(ids) + "\n"


def _spec(number: str, status: str, rows: list[tuple[str, str]]) -> str:
    lines = [
        f"# SPEC-{number} — fixture",
        "",
        f"- **Status:** {status}",
        "",
        "| ID | Requirement | Proved by |",
        "|---|---|---|",
    ]
    lines += [f"| {rid} | a requirement | {proof} |" for rid, proof in rows]
    return "\n".join(lines) + "\n"


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _problems(root: Path) -> list[str]:
    return check(root)[2]


PROOF = "`services/a/test_a.py`"


def test_a_built_spec_whose_requirements_are_cited_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": _tag("SPEC-900-R1"),
    })
    assert _problems(root) == []


def test_a_built_spec_with_an_uncited_requirement_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "def test_nothing() -> None: ...\n",
    })
    assert any(p.startswith("SPEC-900-R1:") and "nothing proves it" in p for p in _problems(root))


def test_an_approved_spec_need_not_be_cited_yet(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Approved", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "def test_nothing() -> None: ...\n",
    })
    assert _problems(root) == []


def test_a_live_proof_counts_when_the_lab_names_the_requirement(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Built", [("SPEC-900-R1", "live: `docs/labs/00-x.md`")]
        ),
        "docs/labs/00-x.md": "Proof for SPEC-900-R1: done.\n",
    })
    assert _problems(root) == []


def test_a_lab_naming_only_a_longer_id_does_not_count(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Built", [("SPEC-900-R1", "live: `docs/labs/00-x.md`")]
        ),
        "docs/labs/00-x.md": "Proof for SPEC-900-R10 only.\n",
    })
    assert any(p.startswith("SPEC-900-R1:") for p in _problems(root))


def test_a_duplicate_id_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", PROOF), ("SPEC-900-R1", PROOF)]
        ),
        "services/a/test_a.py": "",
    })
    assert any("defined twice" in p for p in _problems(root))


def test_an_id_from_another_spec_number_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Draft", [("SPEC-901-R1", PROOF)]),
        "services/a/test_a.py": "",
    })
    assert any("does not belong to SPEC-900" in p for p in _problems(root))


def test_a_cited_id_that_no_spec_defines_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Draft", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": _tag("SPEC-900-R2"),
    })
    assert any("SPEC-900-R2" in p and "no spec defines it" in p for p in _problems(root))


def test_citing_a_retired_spec_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Retired", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": _tag("SPEC-900-R1"),
    })
    assert any("is Retired" in p for p in _problems(root))


def test_a_missing_proof_path_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", "`services/a/missing.py`")]
        ),
    })
    assert any("services/a/missing.py does not exist" in p for p in _problems(root))


def test_a_spec_without_a_status_line_fails_closed(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": "# SPEC-900\n\n| SPEC-900-R1 | x | y |\n",
    })
    assert any("no Status line" in p for p in _problems(root))


def test_a_badly_named_spec_file_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-9-x.md": _spec("9", "Draft", []),
    })
    assert any("name is not SPEC-NNN-<slug>.md" in p for p in _problems(root))


def test_caches_are_not_scanned(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Draft", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "",
        "services/a/__pycache__/stale.txt": _tag("SPEC-900-R9"),
    })
    assert _problems(root) == []


def test_main_prints_the_table_and_returns_1_on_a_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "",
    })
    assert main(["--root", str(root)]) == 1
    out = capsys.readouterr()
    assert "| SPEC-900-R1 | Built | — | — |" in out.out
    assert "nothing proves it" in out.err


def test_main_writes_the_github_job_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path / "repo", {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": _tag("SPEC-900-R1"),
    })
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["--root", str(root)]) == 0
    assert "## Spec coverage" in summary.read_text(encoding="utf-8")
