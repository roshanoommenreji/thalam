#!/usr/bin/env python3
"""Every spec requirement stays tied to its proof (SPEC-001-R8, ADR-0010, KAV-120 Stage 2).

    python scripts/dev/spec_coverage.py              # this repository
    python scripts/dev/spec_coverage.py --root DIR   # another tree (the tests build small ones)

A spec, docs/specs/SPEC-NNN-<slug>.md, lists requirements as table rows `| SPEC-NNN-Rn | ... |`.
The last cell says what proves each one: file paths in backticks, or `live:` and a lab doc.
A file proves a requirement by carrying a tag: the word "covers", a colon, then the IDs, in
any comment syntax. (The tag is not written out here, so this file cites nothing.)

Fails, for every spec:
  * a spec with no Status line or no requirement rows (it fails closed)
  * a requirement ID that does not start with its own spec's number, or appears twice
  * a path in "Proved by" that does not exist
  * a cited ID that no spec defines, or that belongs to a Retired spec
And for a Built or Amended spec, also:
  * a requirement that no file cites and no existing `live:` lab doc mentions

Prints one row per requirement and, under GitHub Actions, the same table as the job summary.
Stdlib only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_FILE = re.compile(r"^SPEC-(\d{3})-[a-z0-9-]+\.md$")
STATUS = re.compile(
    r"^- \*\*Status:\*\*\s*(Draft|Approved|Built|Amended|Retired)\s*$", re.MULTILINE
)
ROW = re.compile(r"^\|\s*(SPEC-\d{3}-R\d+)\s*\|")
ID = re.compile(r"SPEC-\d{3}-R\d+")
TAG = re.compile(r"covers:\s*(SPEC-\d{3}-R\d+(?:\s*,\s*SPEC-\d{3}-R\d+)*)")
BACKTICKED = re.compile(r"`([^`\s]+)`")
LIVE = re.compile(r"live:\s*`([^`\s]+)`")
SCANNED = ("services", "scripts", ".github", "policy", "evals")
NOT_SCANNED = {
    ".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
ENFORCED = {"Built", "Amended"}


@dataclass(frozen=True)
class Requirement:
    rid: str
    spec: str
    status: str
    proofs: tuple[str, ...]
    lives: tuple[str, ...]


def load_specs(root: Path) -> tuple[list[Requirement], list[str]]:
    """Every requirement row of every spec, and what is wrong with the specs themselves."""
    reqs: list[Requirement] = []
    problems: list[str] = []
    for path in sorted((root / "docs" / "specs").glob("SPEC-*.md")):
        name = SPEC_FILE.match(path.name)
        if not name:
            problems.append(f"{path.name}: name is not SPEC-NNN-<slug>.md")
            continue
        text = path.read_text(encoding="utf-8")
        status = STATUS.search(text)
        rows = [line for line in text.splitlines() if ROW.match(line)]
        if not status or not rows:
            problems.append(f"{path.name}: no Status line or no requirement rows")
            continue
        for line in rows:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rid, proved_by = cells[0], cells[-1]
            if not rid.startswith(f"SPEC-{name.group(1)}-"):
                problems.append(f"{path.name}: {rid} does not belong to SPEC-{name.group(1)}")
            proofs = tuple(p.split("::")[0] for p in BACKTICKED.findall(proved_by))
            lives = tuple(LIVE.findall(proved_by))
            reqs.append(Requirement(rid, path.name, status.group(1), proofs, lives))
    return reqs, problems


def find_citations(root: Path) -> dict[str, set[str]]:
    """Requirement ID -> the files (relative, forward slashes) whose tags cite it."""
    cited: dict[str, set[str]] = {}
    for top in SCANNED:
        base = root / top
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            rel = path.relative_to(root)
            if not path.is_file() or NOT_SCANNED.intersection(rel.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for group in TAG.findall(text):
                for rid in ID.findall(group):
                    cited.setdefault(rid, set()).add(rel.as_posix())
    return cited


def _live_proof(root: Path, req: Requirement) -> bool:
    """A `live:` lab doc that exists and names this exact ID (R1 is not R10)."""
    pattern = re.compile(rf"\b{re.escape(req.rid)}\b")
    for lab in req.lives:
        path = root / lab
        if path.is_file() and pattern.search(path.read_text(encoding="utf-8")):
            return True
    return False


def check(root: Path) -> tuple[list[Requirement], dict[str, set[str]], list[str]]:
    """(requirements, citations, problems); no problems means the repository passes."""
    reqs, problems = load_specs(root)
    cited = find_citations(root)
    seen: set[str] = set()
    for req in reqs:
        if req.rid in seen:
            problems.append(f"{req.spec}: {req.rid} is defined twice")
        seen.add(req.rid)
        for proof in req.proofs:
            if not (root / proof).exists():
                problems.append(f"{req.rid}: proof {proof} does not exist")
    by_id = {req.rid: req for req in reqs}
    for rid, files in sorted(cited.items()):
        where = ", ".join(sorted(files))
        owner = by_id.get(rid)
        if owner is None:
            problems.append(f"{rid} is cited by {where} but no spec defines it")
        elif owner.status == "Retired":
            problems.append(f"{rid} is cited by {where} but {owner.spec} is Retired")
    for req in reqs:
        if req.status in ENFORCED and not cited.get(req.rid) and not _live_proof(root, req):
            problems.append(
                f"{req.rid}: {req.spec} is {req.status}, but nothing proves it "
                "(no file cites it and no live: lab names it)"
            )
    return reqs, cited, problems


def table(reqs: list[Requirement], cited: dict[str, set[str]], root: Path) -> list[str]:
    lines = ["| Requirement | Spec status | Cited by | Live proof |", "|---|---|---|---|"]
    for req in reqs:
        files = ", ".join(sorted(cited.get(req.rid, set()))) or "—"
        live = ", ".join(req.lives) if _live_proof(root, req) else "—"
        lines.append(f"| {req.rid} | {req.status} | {files} | {live} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="the repository to check")
    args = parser.parse_args(argv)
    reqs, cited, problems = check(args.root)
    lines = table(reqs, cited, args.root)
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Spec coverage\n\n" + "\n".join(lines) + "\n")
            if problems:
                fh.write("\n**Problems**\n\n" + "".join(f"- {p}\n" for p in problems))
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
