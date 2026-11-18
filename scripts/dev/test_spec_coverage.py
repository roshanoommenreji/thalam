"""Tests for the requirement-to-test check (SPEC-001-R8). Each test builds a tiny repository."""
# covers: SPEC-001-R8

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from spec_coverage import ROOT, check, main

# The scan of the real repository reads this file, and the fixture IDs below belong to no real
# spec, so no line here may hold a tag: every tag is assembled at run time from this word.
COVERS = "covers"


def _tag(*ids: str, lead: str = "# ", gap: str = " ", sep: str = ", ") -> str:
    return lead + COVERS + ":" + gap + sep.join(ids) + "\n"


def _spec(
    number: str, status: str, rows: list[tuple[str, str]], extra: tuple[str, ...] = ()
) -> str:
    lines = [
        f"# SPEC-{number} — fixture",
        "",
        f"- **Status:** {status}",
        "",
        "| ID | Requirement | Proved by |",
        "|---|---|---|",
    ]
    lines += [f"| {rid} | a requirement | {proof} |" for rid, proof in rows]
    lines += extra
    return "\n".join(lines) + "\n"


def _tree(root: Path, files: dict[str, str | bytes]) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return root


def _problems(root: Path) -> list[str]:
    return check(root)[2]


@pytest.fixture(autouse=True)
def _no_job_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    # On CI, GITHUB_STEP_SUMMARY is set while pytest runs; fixture trees must not write to it.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


PROOF = "`services/a/test_a.py`"
NOTHING = "nothing proves it"


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


# --- 1. Malformed rows fail closed ---------------------------------------------------------


@pytest.mark.parametrize(
    "cell", ["SPEC-900-R1a", "**SPEC-900-R1**", "SPEC-1-R1", "SPEC-0001-R1", "`SPEC-900-R2`"]
)
def test_a_row_whose_id_cell_is_not_exactly_an_id_fails(tmp_path: Path, cell: str) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Built", [("SPEC-900-R1", PROOF)], (f"| {cell} | a requirement | {PROOF} |",)
        ),
        "services/a/test_a.py": _tag("SPEC-900-R1"),
    })
    assert any(p.startswith("SPEC-900-x.md:") and cell in p for p in _problems(root))


def test_an_indented_requirement_row_is_still_read(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Built", [("SPEC-900-R1", PROOF)], (f"  | SPEC-900-R2 | indented | {PROOF} |",)
        ),
        "services/a/test_a.py": _tag("SPEC-900-R1"),
    })
    assert any(p.startswith("SPEC-900-R2:") and NOTHING in p for p in _problems(root))


def test_a_requirement_row_with_fewer_than_three_cells_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", PROOF)], ("| SPEC-900-R2 | no proof column |",)
        ),
        "services/a/test_a.py": "",
    })
    assert any("SPEC-900-R2" in p and "cells" in p for p in _problems(root))


def test_an_escaped_pipe_stays_inside_its_cell(tmp_path: Path) -> None:
    good = _tree(tmp_path / "good", {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", "`services/a/test_a.py::test_x[a\\|b]`")]
        ),
        "services/a/test_a.py": "def test_x() -> None: ...\n",
    })
    assert _problems(good) == []
    bad = _tree(tmp_path / "bad", {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", "`services/a/missing.py::test_x[a\\|b]`")]
        ),
    })
    assert any("services/a/missing.py does not exist" in p for p in _problems(bad))


# --- 2. Nothing to check is a failure ------------------------------------------------------


def test_a_repository_without_docs_specs_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"services/a/test_a.py": ""})
    assert "no specs found under docs/specs" in _problems(root)


def test_a_specs_folder_holding_only_the_template_and_readme_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/TEMPLATE.md": "| SPEC-NNN-R1 | x |\n",
        "docs/specs/README.md": "Specs live here.\n",
    })
    assert _problems(root) == ["no specs found under docs/specs"]


@pytest.mark.parametrize("name", ["spec-900-x.md", "notes.md", "SPEC-900_x.md"])
def test_any_other_markdown_file_in_docs_specs_must_be_named_like_a_spec(
    tmp_path: Path, name: str
) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-901-ok.md": _spec("901", "Draft", [("SPEC-901-R1", PROOF)]),
        f"docs/specs/{name}": "# notes\n",
        "services/a/test_a.py": "",
    })
    assert any(p.startswith(f"{name}:") and "SPEC-NNN-<slug>.md" in p for p in _problems(root))


def test_the_plans_subfolder_is_not_read(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Draft", [("SPEC-900-R1", PROOF)]),
        "docs/specs/plans/SPEC-9-bad.md": "| SPEC-9-R1 | broken |\n",
        "docs/specs/plans/notes.md": "",
        "services/a/test_a.py": "",
    })
    assert _problems(root) == []


# --- 3. A live proof must be a lab ----------------------------------------------------------


def test_a_live_proof_outside_docs_labs_fails_and_proves_nothing(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", "live: `notes/x.md`")]),
        "notes/x.md": "Proof for SPEC-900-R1.\n",
    })
    problems = _problems(root)
    assert any("notes/x.md" in p and "docs/labs/" in p for p in problems)
    assert any(p.startswith("SPEC-900-R1:") and NOTHING in p for p in problems)


@pytest.mark.parametrize(
    "lab", ["docs/labs/../labs/00-x.md", "/docs/labs/00-x.md", "docs\\labs\\00-x.md", "docs/labs"]
)
def test_a_live_proof_must_be_a_plain_relative_lab_file(tmp_path: Path, lab: str) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", f"live: `{lab}`")]),
        "docs/labs/00-x.md": "Proof for SPEC-900-R1.\n",
    })
    problems = _problems(root)
    assert any(lab in p for p in problems)
    assert any(p.startswith("SPEC-900-R1:") and NOTHING in p for p in problems)


def test_every_live_path_in_the_cell_is_read(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Built", [("SPEC-900-R1", "live: `docs/labs/00-a.md`, `docs/labs/00-b.md`")]
        ),
        "docs/labs/00-a.md": "Nothing about it here.\n",
        "docs/labs/00-b.md": "Proof for SPEC-900-R1.\n",
    })
    assert _problems(root) == []


# --- 4. Proof paths stay inside the repository and name real files and tests ----------------


def test_an_absolute_proof_path_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path / "repo", {"services/a/test_a.py": ""})
    target = (root / "services/a/test_a.py").as_posix()
    spec = _spec("900", "Draft", [("SPEC-900-R1", f"`{target}`")])
    _tree(root, {"docs/specs/SPEC-900-x.md": spec})
    assert any("absolute" in p for p in _problems(root))


def test_a_proof_path_that_climbs_out_of_the_repository_fails(tmp_path: Path) -> None:
    _tree(tmp_path, {"outside.py": ""})
    root = _tree(tmp_path / "repo", {
        "docs/specs/SPEC-900-x.md": _spec("900", "Draft", [("SPEC-900-R1", "`../outside.py`")]),
    })
    assert any("../outside.py" in p for p in _problems(root))


def test_a_proof_path_with_backslashes_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", "`services\\a\\test_a.py`")]
        ),
        "services/a/test_a.py": "",
    })
    assert any("backslash" in p for p in _problems(root))


def test_a_proof_that_is_a_directory_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Draft", [("SPEC-900-R1", "`services/a`")]),
        "services/a/test_a.py": "",
    })
    assert any("services/a is not a file" in p for p in _problems(root))


def test_a_named_test_must_appear_in_its_proof_file(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", "`services/a/test_a.py::test_gone`")]
        ),
        "services/a/test_a.py": "def test_here() -> None: ...\n",
    })
    assert any("test test_gone not found in services/a/test_a.py" in p for p in _problems(root))


def test_a_named_test_is_matched_as_a_whole_word_without_its_parametrize_id(
    tmp_path: Path,
) -> None:
    files: dict[str, str | bytes] = {"services/a/test_a.py": "def test_xy() -> None: ...\n"}
    whole = _tree(tmp_path / "whole", files | {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", "`services/a/test_a.py::test_xy[case-1]`")]
        ),
    })
    assert _problems(whole) == []
    part = _tree(tmp_path / "part", files | {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Draft", [("SPEC-900-R1", "`services/a/test_a.py::test_x`")]
        ),
    })
    assert any("test test_x not found" in p for p in _problems(part))


# --- 5. Only a comment-line tag cites -------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        's = "' + COVERS + ': SPEC-900-R1"\n',
        "# dis" + COVERS + ": SPEC-900-R1\n",
        _tag("SPEC-900-R1a"),
        _tag("SPEC-900-R1").replace(COVERS, COVERS.title()),
        "x = 1  " + _tag("SPEC-900-R1"),
    ],
    ids=["in-a-string", "discovers", "longer-id", "capitalised", "trailing-comment"],
)
def test_text_that_is_not_a_comment_line_tag_cites_nothing(tmp_path: Path, text: str) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": text,
    })
    assert any(p.startswith("SPEC-900-R1:") and NOTHING in p for p in _problems(root))


@pytest.mark.parametrize("lead", ["# ", "#", "    # ", "// ", "-- ", "; ", " * ", "<!-- "])
def test_a_tag_in_any_comment_syntax_cites(tmp_path: Path, lead: str) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "x = 1\n" + _tag("SPEC-900-R1", lead=lead),
    })
    assert _problems(root) == []


@pytest.mark.parametrize("sep", [", ", ",", " "])
def test_one_tag_can_cite_several_ids(tmp_path: Path, sep: str) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Built", [("SPEC-900-R1", PROOF), ("SPEC-900-R2", PROOF)]
        ),
        "services/a/test_a.py": _tag("SPEC-900-R1", "SPEC-900-R2", sep=sep),
    })
    _, cited, problems = check(root)
    assert problems == []
    assert set(cited) == {"SPEC-900-R1", "SPEC-900-R2"}


def test_a_tag_needs_no_space_after_the_colon(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": _tag("SPEC-900-R1", gap=""),
    })
    assert _problems(root) == []


# --- 6. Output never crashes on the console's encoding; the summary comes first -------------


def test_main_writes_utf8_even_to_a_console_that_cannot_encode_the_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "",
    })
    out, err = io.BytesIO(), io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, encoding="cp437"))
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(err, encoding="cp437"))
    assert main(["--root", str(root)]) == 1
    sys.stdout.flush()
    sys.stderr.flush()
    assert "| SPEC-900-R1 | Built | — | — |" in out.getvalue().decode("utf-8")
    assert NOTHING in err.getvalue().decode("utf-8")


def test_main_puts_the_problems_in_the_job_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path / "repo", {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "",
    })
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["--root", str(root)]) == 1
    text = summary.read_text(encoding="utf-8")
    assert "**Problems**" in text
    assert NOTHING in text


class _ClosedConsole(io.StringIO):
    def write(self, s: str) -> int:
        raise OSError("console closed")


def test_main_writes_the_job_summary_before_printing_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path / "repo", {
        "docs/specs/SPEC-900-x.md": _spec("900", "Built", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "",
    })
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(sys, "stdout", _ClosedConsole())
    monkeypatch.setattr(sys, "stderr", _ClosedConsole())
    with pytest.raises(OSError):
        main(["--root", str(root)])
    text = summary.read_text(encoding="utf-8")
    assert "**Problems**" in text
    assert NOTHING in text


# --- 7. Unreadable specs and labs are problems, not tracebacks ------------------------------


def test_a_spec_that_is_not_utf8_is_a_problem(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"docs/specs/SPEC-900-x.md": b"- **Status:** Draft\n\xff\xfe\n"})
    assert any(p.startswith("SPEC-900-x.md:") and "UTF-8" in p for p in _problems(root))


def test_a_lab_that_is_not_utf8_is_a_problem(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Built", [("SPEC-900-R1", "live: `docs/labs/00-x.md`")]
        ),
        "docs/labs/00-x.md": b"Proof for SPEC-900-R1 \xff\n",
    })
    assert any("docs/labs/00-x.md" in p and "UTF-8" in p for p in _problems(root))


# --- 8. A Retired spec's proof files may be gone --------------------------------------------


def test_a_retired_spec_may_lose_its_proof_files(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec(
            "900", "Retired", [("SPEC-900-R1", "`services/a/gone.py`, live: `docs/labs/gone.md`")]
        ),
    })
    assert _problems(root) == []


# --- Also -----------------------------------------------------------------------------------


@pytest.mark.parametrize("folder", ["build", "dist", ".tox", "thalam.egg-info"])
def test_build_output_is_not_scanned(tmp_path: Path, folder: str) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": _spec("900", "Draft", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "",
        f"services/a/{folder}/stale.py": _tag("SPEC-900-R9"),
    })
    assert _problems(root) == []


def test_a_spec_with_windows_line_endings_passes(tmp_path: Path) -> None:
    spec = _spec("900", "Built", [("SPEC-900-R1", PROOF)]).replace("\n", "\r\n")
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-x.md": spec.encode("utf-8"),
        "services/a/test_a.py": _tag("SPEC-900-R1").replace("\n", "\r\n").encode("utf-8"),
    })
    assert _problems(root) == []


def test_a_duplicate_id_across_two_spec_files_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "docs/specs/SPEC-900-a.md": _spec("900", "Draft", [("SPEC-900-R1", PROOF)]),
        "docs/specs/SPEC-900-b.md": _spec("900", "Draft", [("SPEC-900-R1", PROOF)]),
        "services/a/test_a.py": "",
    })
    assert any("SPEC-900-R1" in p and "defined twice" in p for p in _problems(root))


def test_the_real_repository_passes() -> None:
    assert check(ROOT)[2] == []
