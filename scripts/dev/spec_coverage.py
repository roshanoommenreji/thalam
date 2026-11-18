#!/usr/bin/env python3
"""Every spec requirement stays tied to its proof (SPEC-001-R8, ADR-0010, KAV-120 Stage 2).

    python scripts/dev/spec_coverage.py              # this repository
    python scripts/dev/spec_coverage.py --root DIR   # another tree (the tests build small ones)

Specs are the Markdown files directly in docs/specs/, named SPEC-NNN-<slug>.md (TEMPLATE.md,
README.md and the plans/ folder are not specs). A spec lists requirements as table rows
`| SPEC-NNN-Rn | requirement | Proved by |`, cells split on unescaped pipes. The last cell names
the proof: repository paths in backticks, where `path::test_name` also names a test, and/or
`live:` followed by one or more comma-separated lab docs under docs/labs/.

A file cites a requirement with a tag on a comment line of its own: a comment marker (#, //,
--, ;, * or <!--), the word "covers" in lower case, a colon, then one or more IDs separated by
commas or spaces. (The tag is not written out here, so this file cites nothing.) The scan reads
services/, scripts/, .github/, policy/ and evals/, skipping VCS, virtualenv, cache and build
folders.

Fails closed, for every spec:
  * docs/specs missing, or holding no spec with requirement rows
  * any other Markdown file in docs/specs not named SPEC-NNN-<slug>.md
  * a spec that cannot be read as UTF-8, or has no Status line or no requirement rows
  * a table row whose first cell mentions SPEC- but is not exactly SPEC-NNN-Rn
  * a requirement row with fewer than three cells
  * a requirement ID that does not start with its own spec's number, or is defined twice
  * a cited ID that no spec defines, or that belongs to a Retired spec
For every spec but a Retired one (its proof files may be gone), each path in "Proved by":
  * must be relative, use forward slashes, hold no "..", and stay inside the repository
  * must be an existing file; a named test (less any [parametrize id]) must appear in it
  * after live:, must also lie under docs/labs/ and be readable as UTF-8
And for a Built or Amended spec, also:
  * a requirement that no file cites and no valid live: lab names by its exact ID
  * a live: lab that still says _not run yet_ (its evidence is blank), reported once per lab

Writes the table and the problems to the GitHub job summary when there is one, then prints one
row per requirement, as UTF-8 whatever the console's encoding. Stdlib only.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
SPECS = Path("docs") / "specs"
NOT_SPECS = {"TEMPLATE.md", "README.md"}
LABS = "docs/labs/"
SPEC_FILE = re.compile(r"^SPEC-(\d{3})-[a-z0-9-]+\.md$")
STATUS = re.compile(
    r"^- \*\*Status:\*\*[ \t]*(Draft|Approved|Built|Amended|Retired)[ \t]*$", re.MULTILINE
)
REQ_ID = re.compile(r"SPEC-\d{3}-R\d+")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
ID = re.compile(r"SPEC-\d{3}-R\d+\b")
TAG = re.compile(
    r"^[ \t]*(?:#|//|--|;|\*|<!--)[ \t]*covers:[ \t]*"
    r"(SPEC-\d{3}-R\d+\b(?:[ \t,]+SPEC-\d{3}-R\d+\b)*)",
    re.MULTILINE,
)
BACKTICKED = re.compile(r"`([^`\s]+)`")
LIVE = re.compile(r"live:[ \t]*(`[^`\s]+`(?:[ \t]*,[ \t]*`[^`\s]+`)*)")
SCANNED = ("services", "scripts", ".github", "policy", "evals")
NOT_SCANNED = {
    ".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "build", "dist", ".tox",
}
ENFORCED = {"Built", "Amended"}
PENDING = "_not run yet_"  # a lab's placeholder for evidence that has not been recorded


@dataclass(frozen=True)
class Requirement:
    rid: str
    spec: str
    status: str
    proofs: tuple[str, ...]  # every backticked path in "Proved by", as written (maybe ::test)
    lives: tuple[str, ...]  # those of them named after live:
    proven_live: tuple[str, ...] = ()  # set by check(): valid labs that name this exact ID


def _read(path: Path) -> str | None:
    """The file's text, or None when it cannot be read as UTF-8."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _cells(line: str) -> list[str] | None:
    """The stripped cells of a Markdown table line, or None when the line is not one."""
    body = line.strip()
    if not body.startswith("|"):
        return None
    body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip().replace("\\|", "|") for cell in UNESCAPED_PIPE.split(body)]


def load_specs(root: Path) -> tuple[list[Requirement], list[str]]:
    """Every requirement row of every spec, and what is wrong with the specs themselves."""
    reqs: list[Requirement] = []
    problems: list[str] = []
    folder = root / SPECS
    paths = sorted(
        p for p in (folder.iterdir() if folder.is_dir() else ())
        if p.is_file() and p.suffix.lower() == ".md" and p.name not in NOT_SPECS
    )
    for path in paths:
        name = SPEC_FILE.match(path.name)
        if not name:
            problems.append(f"{path.name}: name is not SPEC-NNN-<slug>.md")
            continue
        text = _read(path)
        if text is None:
            problems.append(f"{path.name}: cannot be read as UTF-8 text")
            continue
        number = name.group(1)
        rows: list[list[str]] = []
        for line in text.splitlines():
            cells = _cells(line)
            if cells is None or "SPEC-" not in cells[0]:
                continue
            if not REQ_ID.fullmatch(cells[0]):
                problems.append(f"{path.name}: row ID cell {cells[0]!r} is not SPEC-NNN-Rn")
            elif len(cells) < 3:
                problems.append(
                    f"{path.name}: {cells[0]} row has {len(cells)} cells; "
                    "a requirement row needs ID, requirement and Proved by"
                )
            else:
                rows.append(cells)
        status = STATUS.search(text)
        if not status or not rows:
            problems.append(f"{path.name}: no Status line or no requirement rows")
            continue
        for cells in rows:
            rid, proved_by = cells[0], cells[-1]
            if not rid.startswith(f"SPEC-{number}-"):
                problems.append(f"{path.name}: {rid} does not belong to SPEC-{number}")
            proofs = tuple(BACKTICKED.findall(proved_by))
            lives = tuple(p for group in LIVE.findall(proved_by) for p in BACKTICKED.findall(group))
            reqs.append(Requirement(rid, path.name, status.group(1), proofs, lives))
    if not reqs:
        problems.append("no specs found under docs/specs")
    return reqs, problems


def _skipped(folder: str) -> bool:
    return folder in NOT_SCANNED or folder.endswith(".egg-info")


def find_citations(root: Path) -> dict[str, set[str]]:
    """Requirement ID -> the files (relative, forward slashes) whose tags cite it."""
    cited: dict[str, set[str]] = {}
    for top in SCANNED:
        for dirpath, dirnames, filenames in os.walk(root / top):
            dirnames[:] = sorted(d for d in dirnames if not _skipped(d))
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                text = _read(path)
                if text is None:
                    continue
                rel = path.relative_to(root).as_posix()
                for group in TAG.findall(text):
                    for rid in ID.findall(group):
                        cited.setdefault(rid, set()).add(rel)
    return cited


def _path_problem(root: Path, path: str, *, lab: bool) -> str | None:
    """Why `path` cannot stand as a proof, or None when it is a file inside the repository."""
    if "\\" in path:
        return f"proof {path} uses backslashes; write repository paths with /"
    pure = PurePosixPath(path)
    if pure.is_absolute() or PureWindowsPath(path).drive:
        return f"proof {path} is absolute; write it relative to the repository root"
    if ".." in pure.parts:
        return f"proof {path} climbs with ..; write it from the repository root"
    if lab and not path.startswith(LABS):
        return f"live proof {path} is not a lab under {LABS}"
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        return f"proof {path} resolves outside the repository"
    if not target.exists():
        return f"proof {path} does not exist"
    if not target.is_file():
        return f"proof {path} is not a file"
    return None


def _check_proofs(root: Path, req: Requirement) -> tuple[list[str], tuple[str, ...]]:
    """Problems with a row's "Proved by" paths, and the labs that prove it live."""
    problems: list[str] = []
    proven: list[str] = []
    for token in req.proofs:
        path, *tests = token.split("::")
        lab = token in req.lives
        problem = _path_problem(root, path, lab=lab)
        if problem:
            problems.append(f"{req.rid}: {problem}")
            continue
        if not tests and not lab:
            continue
        text = _read(root / path)
        if text is None:
            problems.append(f"{req.rid}: proof {path} cannot be read as UTF-8 text")
            continue
        for test in tests:
            name = test.split("[", 1)[0]
            if not name or not re.search(rf"\b{re.escape(name)}\b", text):
                problems.append(f"{req.rid}: test {name or '(no name)'} not found in {path}")
        if lab and re.search(rf"\b{re.escape(req.rid)}\b", text):
            proven.append(path)
    return problems, tuple(proven)


def check(root: Path) -> tuple[list[Requirement], dict[str, set[str]], list[str]]:
    """(requirements, citations, problems); no problems means the repository passes."""
    loaded, problems = load_specs(root)
    cited = find_citations(root)
    first: dict[str, str] = {}
    reqs: list[Requirement] = []
    for req in loaded:
        if req.rid in first:
            problems.append(f"{req.spec}: {req.rid} is defined twice (also in {first[req.rid]})")
        first.setdefault(req.rid, req.spec)
        if req.status == "Retired":
            reqs.append(req)
            continue
        found, proven = _check_proofs(root, req)
        problems += found
        reqs.append(replace(req, proven_live=proven))
    by_id = {req.rid: req for req in reqs}
    for rid, files in sorted(cited.items()):
        where = ", ".join(sorted(files))
        owner = by_id.get(rid)
        if owner is None:
            problems.append(f"{rid} is cited by {where} but no spec defines it")
        elif owner.status == "Retired":
            problems.append(f"{rid} is cited by {where} but {owner.spec} is Retired")
    for req in reqs:
        if req.status in ENFORCED and not cited.get(req.rid) and not req.proven_live:
            problems.append(
                f"{req.rid}: {req.spec} is {req.status}, but nothing proves it "
                "(no file cites it and no live: lab names it)"
            )
    problems += _pending_evidence(root, reqs)
    return reqs, cited, problems


def _pending_evidence(root: Path, reqs: list[Requirement]) -> list[str]:
    """A Built or Amended spec whose live: lab still holds the PENDING marker, once per lab.

    Naming a requirement is enough for a lab to count as its live proof, so without this a spec
    could be set to Built while the lab's evidence is still blank.
    """
    pending: dict[tuple[str, str], str] = {}
    for req in reqs:
        if req.status in ENFORCED:
            for token in req.lives:
                pending.setdefault((req.spec, token.split("::")[0]), req.status)
    found = []
    for (spec, lab), status in sorted(pending.items()):
        if _path_problem(root, lab, lab=True):
            continue  # already reported by _check_proofs
        count = (_read(root / lab) or "").count(PENDING)
        if count:
            found.append(
                f"{spec} is {status}, but {lab} still says {PENDING} ({count}x): "
                "record the live evidence before calling the spec Built"
            )
    return found


def table(reqs: list[Requirement], cited: dict[str, set[str]]) -> list[str]:
    lines = ["| Requirement | Spec status | Cited by | Live proof |", "|---|---|---|---|"]
    for req in reqs:
        files = ", ".join(sorted(cited.get(req.rid, set()))) or "—"
        live = ", ".join(req.proven_live) or "—"
        lines.append(f"| {req.rid} | {req.status} | {files} | {live} |")
    return lines


def _utf8_console() -> None:
    """Print UTF-8 even where the console's own encoding (cp437, cp1252) lacks the dash."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="the repository to check")
    args = parser.parse_args(argv)
    reqs, cited, problems = check(args.root)
    lines = table(reqs, cited)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Spec coverage\n\n" + "\n".join(lines) + "\n")
            if problems:
                fh.write("\n**Problems**\n\n" + "".join(f"- {p}\n" for p in problems))
    print("\n".join(lines))
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
