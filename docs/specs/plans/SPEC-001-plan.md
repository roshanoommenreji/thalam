# SPEC-001 Phase 0 Foundations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build what [SPEC-001](../SPEC-001-phase-0-foundations.md) asks for: a public `thalam` repo whose `main` only changes through green CI, a requirement-to-test check, and proved read-only access to every sandbox.

**Architecture:** Three small stdlib-only scripts in `scripts/dev/` (commit-message check, spec coverage check, sandbox check), each with pytest tests beside it, plus an empty `thalam_shared` package so CI has something to build. CI copies Kaval's supply-chain habits: actions pinned by SHA, gitleaks checked against a sha256, a read-only token. Live proofs that code cannot run (ruleset, sign-ups, spend limit) are recorded in `docs/labs/00-foundations.md`.

**Tech Stack:** Python 3.11, uv, hatchling, pytest, ruff, mypy `--strict`, gitleaks 8.30.1, GitHub Actions, CodeQL, Dependabot, the GitHub CLI.

**Conventions for whoever runs this:**
- Run every command from the repo root (`Desktop\Claude\Release Agent`) in **Git Bash**.
- `THL-1` is the Phase 0 epic. Each task also has its own story under it (created 2026-11-18), and from Task 3 on, a task's commits and branch names use **its story key** where this plan says `THL-1`: Task 0 `THL-10`, 1 `THL-11`, 2 `THL-12`, 3 `THL-13`, 4 `THL-14`, 5 `THL-15`, 6 `THL-16`, 7 `THL-17`, 8 `THL-18`, 9 `THL-19`, 10 `THL-20`, 11 `THL-21`.
- Steps marked **STOP — Roshan** are outward-facing or need his accounts. Do not do them without his go.
- Never paste a real site address, tenant ID or token into a committed file (CLAUDE.md rule 6).

---

## File map

| File | Responsibility | Task |
|---|---|---|
| `.gitattributes` | LF line endings, so the bash hooks work on Windows | 1 |
| `.gitleaks.toml` | Secret rules, retargeted from Kaval, plus two rule-6 address rules | 1 |
| `docs/adr/0010-ai-dlc-spec-driven-workflow.md` | Real Jira link replaced with plain text | 1 |
| `pyproject.toml`, `.python-version`, `uv.lock` | The project, its dev tools and the lock | 2 |
| `services/shared/thalam_shared/__init__.py`, `py.typed` | The empty package | 2 |
| `services/shared/tests/test_bootstrap.py` | R3 | 2 |
| `scripts/dev/check_commits.py`, `test_check_commits.py` | R5 | 3 |
| `scripts/dev/install-hooks.sh` | pre-commit (gitleaks) and commit-msg hooks | 3 |
| `scripts/dev/spec_coverage.py`, `test_spec_coverage.py` | R8 | 4, 8 |
| `docs/specs/SPEC-001-phase-0-foundations.md` | Two planning amendments | 4 |
| `scripts/dev/check_sandboxes.py`, `test_check_sandboxes.py` | R10–R13 | 5 |
| `.env.example` | The sandbox check's settings, placeholders only | 5 |
| `Makefile` | `lint`, `test`, `hooks`, `secrets-scan`, `sandboxes` | 6 |
| `docs/labs/00-foundations.md` | Live proofs: R1, R2, R6, R9, R13 | 7, 9, 10 |
| `.github/workflows/ci.yml`, `codeql.yml`, `dependabot.yml` | R4, R6, R7 | 8 |
| `.github/rulesets/main.json` | The ruleset for `main`, applied in Task 9 | 8 |
| `docs/adr/0011-phase-0-shape.md`, `ROADMAP.md`, `README.md`, journal | Docs that follow | 11 |

---

### Task 0: Jira planning project (STOP — Roshan, about 10 minutes)

This gives the commits a real `THL` key. It is lab step 1 (SPEC-001-R9).

- [ ] **Step 1:** On your existing Jira site: sidebar → Spaces → **Create space** (Jira Cloud renamed projects to spaces in 2025) → Kanban template → **team-managed**, name **Thalam**, key **THL**. Type the key yourself and check it before Create: on Kaval the wizard produced `SCRUM`, not `KAV` (Kaval journal 2026-09-14). If `THL` is taken, use `THLM` (ADR-0009) and replace `THL` throughout this plan. Before Step 2, make sure the space is empty; sample work items use up key numbers.
- [ ] **Step 2:** Create nine epics, in this order, so their keys follow the phases: `Phase 0 — Foundations`, `Phase 1 — The release graph, local`, `Phase 2 — Read-only chat agent`, `Phase 3 — Proposals, policy, approval, executor`, `Phase 4 — Pre-release readiness gate`, `Phase 5 — Release notes and calendar`, `Phase 6 — Post-release verification`, `Phase 7 — Kubernetes and AWS`, `Phase 8 — Harden and publish`.
- [ ] **Step 3:** Confirm that Settings → User management lists no bot account on this site.
- [ ] **Step 4:** Tell the session the Phase 0 epic's key (expected `THL-1`).

---

### Task 1: git init, privacy and public-repo hygiene

**Files:**
- Create: `.gitattributes`
- Modify: `.gitleaks.toml` (whole file)
- Modify: `docs/adr/0010-ai-dlc-spec-driven-workflow.md:9`

- [ ] **Step 1: Initialise git and commit under GitHub's no-reply address** (the repo is public, so a personal email in commits would be published)

```bash
git init -b main
git config user.email "$(gh api user -q .id)+roshanoommenreji@users.noreply.github.com"
git config user.name "Roshan Oommen Reji"
git config core.autocrlf false
```

Expected: `Initialized empty Git repository in .../Release Agent/.git/`

- [ ] **Step 2: Write `.gitattributes`**

```gitattributes
# LF everywhere, so the bash hooks and scripts run the same on Windows and in CI.
* text=auto eol=lf
*.png binary
```

- [ ] **Step 3: Replace the real Jira site link in ADR-0010**

In `docs/adr/0010-ai-dlc-spec-driven-workflow.md`, line 9 starts with `Kaval's epic [KAV-120](` followed by the real Jira address in parentheses. Replace the whole markdown link (brackets and parenthesised address) with the plain text `KAV-120`, so the line reads:

```
Kaval's epic KAV-120 (FS-9 in Kaval's
```

(This plan does not quote the address, so that the plan itself passes the rule it adds.)

- [ ] **Step 4: Replace `.gitleaks.toml` with Thalam's version**

```toml
# gitleaks configuration for Thalam (SPEC-001-R6).
#
# This repository is public from its first push (ADR-0011), so the HISTORY must be clean, not
# just the working tree. Copied from Kaval's and trimmed. Two rules are added for CLAUDE.md
# rule 6 (no real instance addresses), and docs are no longer exempt: a doc is where a real
# address is most likely to be pasted.
#
#   gitleaks git --staged    the pre-commit hook (scripts/dev/install-hooks.sh)
#   gitleaks git .           the whole history (CI's `secrets` job, `make secrets-scan`)
#   gitleaks dir .           the working tree

[extend]
useDefault = true

# ─── project-specific rules ──────────────────────────────────

[[rules]]
id = "aws-account-id"
description = "AWS account ID in a committed file"
regex = '''(?i)(aws_?account_?id|account[_-]?id)["'\s:=]+["']?([0-9]{12})["']?'''
tags = ["aws", "identifier"]

[[rules]]
id = "aws-arn-with-account"
description = "ARN containing a real 12-digit account ID"
# re2 has no lookahead, so the 000000000000 placeholder is cleared by the allowlist below.
regex = '''arn:aws[a-z-]*:[a-z0-9-]+:[a-z0-9-]*:[0-9]{12}:'''
tags = ["aws", "identifier"]

# CLAUDE.md rule 6. A placeholder such as <your-site>.atlassian.net does not match, because the
# character before the dot is `>`, which is not a host character.
[[rules]]
id = "real-atlassian-site"
description = "A real Atlassian site address; write <your-site>.atlassian.net instead"
regex = '''\b[a-z0-9][a-z0-9-]*\.atlassian\.net\b'''
keywords = ["atlassian.net"]
tags = ["identifier", "rule-6"]

[[rules]]
id = "real-servicenow-instance"
description = "A real ServiceNow instance address; write <your-pdi>.service-now.com instead"
regex = '''\b[a-z0-9][a-z0-9-]*\.service-now\.com\b'''
keywords = ["service-now.com"]
tags = ["identifier", "rule-6"]

# ─── allowlist ───────────────────────────────────────────────

[allowlist]
description = "Placeholders and examples"

paths = [
  '''\.gitleaks\.toml$''',
  '''\.env\.example$''',
  '''.*\.tfvars\.example$''',
]

regexes = [
  '''000000000000''',                 # placeholder account ID
  '''(?i)you@example\.com''',
  '''(?i)change-?me''',
  '''(?i)<[a-z_-]+>''',               # <your-key-here>
  '''(?i)xxx+''',
  '''(?i)placeholder''',
]
```

- [ ] **Step 5: Prove the rule-6 rule catches a real-looking address** (the negative case)

```bash
mkdir -p .probe && printf 'url = "https://acme-test.%s"\n' atlassian.net > .probe/x.txt
gitleaks dir --config .gitleaks.toml --no-banner --redact .probe; echo "exit $?"
rm -rf .probe
```

Expected: `leaks found: 1` and `exit 1`.

- [ ] **Step 6: Scan the working tree**

```bash
gitleaks dir --config .gitleaks.toml --no-banner --redact .
```

Expected: `no leaks found`. If something is flagged, read it. A real value gets removed. A false positive gets an allowlist entry with a comment saying why, never `--no-verify`.

- [ ] **Step 7: Check that no real Jira address remains anywhere**

```bash
grep -rniE '\b[a-z0-9][a-z0-9-]*\.atlassian\.net' . --exclude-dir=.git --exclude-dir=.venv || echo "none"
```

Expected: `none`.

- [ ] **Step 8: First commit**

```bash
git add -A
git status --short   # read it: no .env, nothing unexpected
git commit -m "chore: THL-1 project docs, ADRs 0001-0010, SPEC-001 and its plan"
```

---

### Task 2: The Python project and the empty package (SPEC-001-R3)

**Files:**
- Create: `pyproject.toml`, `.python-version`
- Create: `services/shared/tests/test_bootstrap.py`
- Create: `services/shared/thalam_shared/__init__.py`, `services/shared/thalam_shared/py.typed`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "thalam"
version = "0.0.1"
description = "Release-coordination agent with human-in-the-loop approval"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=9.2.0",
    "ruff>=0.17.4",
    "mypy>=2.4.1",
]

[build-system]
requires = ["hatchling==1.33.0"]   # pinned, as in Kaval
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["services/shared/thalam_shared"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["services", "scripts/dev"]
```

And `.python-version`:

```
3.11
```

- [ ] **Step 2: Write the failing test** at `services/shared/tests/test_bootstrap.py`

```python
"""The empty package installs from the lock and imports (SPEC-001-R3)."""
# covers: SPEC-001-R3

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_package_imports_and_reports_the_project_version() -> None:
    import thalam_shared

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert thalam_shared.__version__ == project["version"]
```

- [ ] **Step 3: Run it to see it fail**

Run: `uv sync --all-extras && uv run pytest services -v`
Expected: FAIL in one of two ways, because the package does not exist yet: either the build reports the missing `services/shared/thalam_shared`, or it builds an empty wheel and the test fails with `ModuleNotFoundError: No module named 'thalam_shared'`.

- [ ] **Step 4: Create the package**

`services/shared/thalam_shared/__init__.py`:

```python
"""Thalam's shared package. Empty in Phase 0: it exists so CI has something to check."""

from importlib.metadata import version

__version__ = version("thalam")
```

`services/shared/thalam_shared/py.typed`: an empty file. It tells mypy the package ships its own types.

- [ ] **Step 5: Sync and run the test**

```bash
uv sync --all-extras
uv run pytest services -v
```

Expected: `uv.lock` is created, and `test_the_package_imports_and_reports_the_project_version PASSED`.

- [ ] **Step 6: Check that the lock holds still**

Run: `uv sync --locked --all-extras`
Expected: no error, which is what CI will run.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .python-version uv.lock services/
git commit -m "feat: THL-1 empty thalam_shared package, installable from uv.lock"
```

---

### Task 3: The commit-message check and the hooks (SPEC-001-R5, SPEC-001-R6 locally)

**Files:**
- Create: `scripts/dev/test_check_commits.py`
- Create: `scripts/dev/check_commits.py`
- Create: `scripts/dev/install-hooks.sh`

- [ ] **Step 1: Write the failing tests** at `scripts/dev/test_check_commits.py`

```python
"""Tests for the commit-message check (SPEC-001-R5; copied from Kaval KAV-25)."""
# covers: SPEC-001-R5

from __future__ import annotations

import pytest
from check_commits import problems

STORY = "feat/THL-1-foundations"


@pytest.mark.parametrize(
    "message",
    [
        "feat: THL-1 commit-msg hook",
        "fix(ci): THL-1 pin the gitleaks checksum",
        "infra!: THL-7 move the database to its own server",
        "docs: THL-1 Lab 00\n\nBody text with #hashtag and a PR ref #1.",
        "Merge pull request #2 from roshanoommenreji/feat/THL-1-foundations",
        "Merge branch 'feat/THL-2-release-graph'",
        'Revert "feat: THL-1 commit-msg hook"',
        "# Please enter the commit message\nchore: THL-1 tidy\n# comment line",
    ],
)
def test_accepts(message: str) -> None:
    assert problems(message, STORY) == []


def test_housekeeping_branch_needs_no_key() -> None:
    assert problems("chore: tidy the root", "chore/repo-structure") == []


@pytest.mark.parametrize(
    ("message", "fragment"),
    [
        ("added the hook", "must start with"),
        ("feature: THL-1 hook", "must start with"),
        ("feat:THL-1 no space", "must start with"),
        ("Feat: THL-1 capital", "must start with"),
        ("feat: add the hook", "needs its THL key"),
        ("feat: THL-1 " + "x" * 100, "keep it to 100"),
        ("feat: THL-1 hook #comment done", "smart-commit"),
        ("feat: THL-1 hook\n\nTHL-1 #time 2h", "smart-commit"),
        ("feat: THL-1 #done", "smart-commit"),
        ("", "empty"),
        ("# only comments", "empty"),
    ],
)
def test_rejects(message: str, fragment: str) -> None:
    found = problems(message, STORY)
    assert any(fragment in p for p in found), found


def test_autosquash_allowed_locally_refused_in_ci() -> None:
    message = "fixup! feat: THL-1 hook"
    assert problems(message, STORY) == []
    assert problems(message, STORY, in_ci=True)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest scripts/dev/test_check_commits.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_commits'`

- [ ] **Step 3: Write `scripts/dev/check_commits.py`**

```python
#!/usr/bin/env python3
"""Check commit messages against the repo's convention (SPEC-001-R5, from Kaval KAV-25).

Two callers, one rule set:

    # the commit-msg hook (scripts/dev/install-hooks.sh), on every local commit
    python scripts/dev/check_commits.py --file .git/COMMIT_EDITMSG --branch feat/THL-1-x

    # CI (the lint job), on every commit a pull request adds
    python scripts/dev/check_commits.py --range <base-sha>..<head-sha> --branch feat/THL-1-x

Rules:
  1. The subject is a conventional commit: `<type>[(scope)][!]: <text>`, where type is one of
     feat, fix, docs, infra, chore. Merge and revert commits are generated, so exempt.
  2. The subject is at most 100 characters.
  3. On a story branch (its name carries THL-<n>), the subject carries a THL key. That key is
     what links the commit to its Jira issue (CLAUDE.md, "Commits and branches").
  4. No smart-commit commands (`THL-1 #comment ...`, `#time`, `#done`). Jira runs those only
     when the commit email matches a Jira user, and this repo commits under the GitHub no-reply
     address, so a command would be silently ignored.
  5. In CI only: no `fixup!`/`squash!` commits. They're fine locally, but get squashed away
     (`git rebase --autosquash`) before a pull request.

Stdlib only, so the hook works before `uv sync` has ever run.
"""
# covers: SPEC-001-R5

from __future__ import annotations

import argparse
import re
import subprocess
import sys

TYPES = ("feat", "fix", "docs", "infra", "chore")
SUBJECT = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([a-z0-9-]+\))?!?: \S")
MAX_SUBJECT = 100
KEY = re.compile(r"\bTHL-\d+\b")
# A key followed, on the same line, by `#` and a letter: `#comment`, `#time`, `#done`.
# `#1` (a PR number) doesn't count.
SMART_COMMAND = re.compile(r"\bTHL-\d+\b[^\n]*?(?<![\w#])#[A-Za-z]")
GENERATED = ("Merge ", 'Revert "')
AUTOSQUASH = ("fixup! ", "squash! ", "amend! ")


def problems(message: str, branch: str = "", *, in_ci: bool = False) -> list[str]:
    """Everything wrong with one commit message; empty means it passes."""
    # git drops `#` lines from an edited message; the hook sees them before it does.
    lines = [ln for ln in message.splitlines() if not ln.startswith("#")]
    subject = next((ln for ln in lines if ln.strip()), "").rstrip()
    if not subject:
        return ["the message is empty"]
    if subject.startswith(GENERATED):
        return []
    if subject.startswith(AUTOSQUASH):
        return ["squash fixup!/squash! commits before opening a pull request"] if in_ci else []

    found = []
    if not SUBJECT.match(subject):
        found.append(
            f"the subject must start with one of {', '.join(TYPES)}, then ': ' "
            f"(e.g. 'feat: THL-1 ...'); got {subject[:60]!r}"
        )
    if len(subject) > MAX_SUBJECT:
        found.append(f"the subject is {len(subject)} characters; keep it to {MAX_SUBJECT}")
    if KEY.search(branch) and not KEY.search(subject):
        found.append(
            f"branch {branch!r} is a story branch, so the subject needs its THL key; "
            "the key is what links the commit to the Jira issue"
        )
    if SMART_COMMAND.search("\n".join(lines)):
        found.append(
            "smart-commit commands (#comment, #time, #done ...) don't run here: commits use "
            "the GitHub no-reply email, which matches no Jira user. Keep the key, drop the "
            "command, and move the issue in Jira"
        )
    return found


def commits_in(rev_range: str) -> list[tuple[str, str]]:
    """(short sha, full message) for every commit in the range, oldest first."""
    out = subprocess.run(
        ["git", "log", "--reverse", "--format=%h%x00%B%x1e", rev_range],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    pairs = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if record:
            sha, _, body = record.partition("\x00")
            pairs.append((sha, body))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="a commit message file (the commit-msg hook)")
    source.add_argument("--range", help="a git revision range, e.g. base..head (CI)")
    parser.add_argument("--branch", default="", help="the branch the commits are on")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            checked = [("this commit", fh.read())]
    else:
        checked = commits_in(args.range)

    failed = 0
    for sha, message in checked:
        for problem in problems(message, args.branch, in_ci=bool(args.range)):
            print(f"  {sha}: {problem}", file=sys.stderr)
            failed += 1
    if failed:
        print('\n  Commit convention: CLAUDE.md, "Commits and branches"', file=sys.stderr)
        return 1
    if args.range:
        print(f"{len(checked)} commit(s) follow the convention")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest scripts/dev/test_check_commits.py -v`
Expected: all PASS (21 tests).

- [ ] **Step 5: Write `scripts/dev/install-hooks.sh`**

```bash
#!/usr/bin/env bash
# Install the Git hooks. Run once after cloning: make hooks
#
#   pre-commit  gitleaks + account-ID check on what's staged (SPEC-001-R6)
#   commit-msg  the commit convention (scripts/dev/check_commits.py, SPEC-001-R5)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOK="$ROOT/.git/hooks/pre-commit"
MSG_HOOK="$ROOT/.git/hooks/commit-msg"

[[ -d "$ROOT/.git" ]] || { echo "not a git repository — run 'git init' first"; exit 1; }

cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# Thalam pre-commit — block secrets before they enter history. The repository is public, so a
# secret committed today and removed tomorrow is still published. This is the cheap moment.

set -euo pipefail

if command -v gitleaks >/dev/null 2>&1; then
  # `git --staged` is the working scan in gitleaks v8.20+; the old `protect` is a silent no-op.
  if ! gitleaks git --staged --redact --config .gitleaks.toml --no-banner; then
    echo ""
    echo "  Commit blocked: a possible secret or real address is staged."
    echo "  A genuine false positive goes in .gitleaks.toml's allowlist with a comment saying why."
    echo "  Do not use --no-verify."
    echo ""
    exit 1
  fi
else
  echo "  WARNING: gitleaks not installed — commit NOT scanned (CI still scans)."
fi

# Belt and braces: a real 12-digit account ID that slipped past the rules. The boundaries
# exclude hex letters, so a digit run inside a sha256 (uv.lock) doesn't count.
if git diff --cached -U0 | grep -nE '^\+(.*[^0-9a-fA-F])?[0-9]{12}([^0-9a-fA-F]|$)' \
     | grep -vE '000000000000' >/dev/null 2>&1; then
  echo ""
  echo "  A 12-digit number is being committed. If that is an AWS account ID,"
  echo "  replace it with a variable or the 000000000000 placeholder."
  echo ""
  read -p "  Continue anyway? [y/N] " ok < /dev/tty
  [[ "$ok" == "y" ]] || exit 1
fi
EOF
chmod +x "$HOOK"
echo "installed: .git/hooks/pre-commit"

cat > "$MSG_HOOK" <<'EOF'
#!/usr/bin/env bash
# Thalam commit-msg — the commit convention, checked before the commit exists (SPEC-001-R5).

set -euo pipefail

PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "  WARNING: no python found — commit message NOT checked (CI still checks it)."
  exit 0
fi
BRANCH="$(git symbolic-ref --short -q HEAD || true)"
exec "$PY" scripts/dev/check_commits.py --file "$1" --branch "$BRANCH"
EOF
chmod +x "$MSG_HOOK"
echo "installed: .git/hooks/commit-msg"
```

- [ ] **Step 6: Install the hooks and prove the commit-msg hook refuses a bad message**

```bash
bash scripts/dev/install-hooks.sh
git add scripts/dev/check_commits.py scripts/dev/test_check_commits.py scripts/dev/install-hooks.sh
git commit -m "added the commit check"; echo "exit $?"
```

Expected: `the subject must start with one of feat, fix, docs, infra, chore` and `exit 1`. Nothing is committed.

- [ ] **Step 7: Prove the pre-commit hook blocks a planted fake secret (SPEC-001-R6, local half)**

The token is random and was never issued, so it is shaped like a GitHub token without being one.

```bash
python -c "import secrets,string;print('TOKEN = \"ghp_'+''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(36))+'\"')" > scripts/dev/leak_probe.py
git add scripts/dev/leak_probe.py
git commit -m "chore: THL-1 leak probe"; echo "exit $?"
git restore --staged scripts/dev/leak_probe.py && rm scripts/dev/leak_probe.py
```

Expected: `Commit blocked: a possible secret or real address is staged.` and `exit 1`. Copy the gitleaks finding line (it is redacted) into lab section 7 in Task 7.

- [ ] **Step 8: Commit for real**

```bash
git commit -m "feat: THL-1 commit-message check and git hooks"
```

Expected: the hooks pass and the commit is made.

---

### Task 4: The requirement-to-test check (SPEC-001-R8)

**Files:**
- Create: `scripts/dev/test_spec_coverage.py`
- Create: `scripts/dev/spec_coverage.py`
- Modify: `docs/specs/SPEC-001-phase-0-foundations.md` (two planning amendments)

- [ ] **Step 1: Write the failing tests** at `scripts/dev/test_spec_coverage.py`

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest scripts/dev/test_spec_coverage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spec_coverage'`

- [ ] **Step 3: Write `scripts/dev/spec_coverage.py`**

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest scripts/dev/test_spec_coverage.py -v`
Expected: all 15 PASS.

- [ ] **Step 5: Record the two planning amendments in SPEC-001** (Roshan approved them with this plan)

In `docs/specs/SPEC-001-phase-0-foundations.md`, replace:

```
- **Approved by / date:** Roshan, 2026-11-18
```

with:

```
- **Approved by / date:** Roshan, 2026-11-18
- **Amended in planning:** 2026-11-18. R5's key rule applies on story branches; the R8 fixtures are built by the test in a temporary directory (approved with the plan)
```

Replace the R5 row:

```
| SPEC-001-R5 | Commit messages are conventional and carry a `THL-<n>` key; a message without one fails | `scripts/dev/test_check_commits.py` |
```

with:

```
| SPEC-001-R5 | Commit messages are conventional; on a story branch (`type/THL-<n>-slug`) the subject carries that THL key, and a message without it fails | `scripts/dev/test_check_commits.py` |
```

Replace:

```
job summary. Its test runs it on the real repo and on broken fixtures in `scripts/dev/fixtures/specs/`.
```

with:

```
job summary. Its test runs it on the real repo and on small broken trees it builds in a temporary
directory.
```

- [ ] **Step 6: Run it on the real repo** (some failures are expected at this point)

Run: `uv run python scripts/dev/spec_coverage.py; echo "exit $?"`
Expected: a 13-row table, all `Approved`, and `exit 1` with `proof ... does not exist` for `.github/workflows/ci.yml`, `codeql.yml`, `dependabot.yml`, `scripts/dev/check_sandboxes.py` and `docs/labs/00-foundations.md`. Tasks 5, 7 and 8 create those files. Any other problem is a bug to fix now.

- [ ] **Step 7: Commit**

```bash
git add scripts/dev/spec_coverage.py scripts/dev/test_spec_coverage.py docs/specs/SPEC-001-phase-0-foundations.md
git commit -m "feat: THL-1 requirement-to-test check (spec coverage)"
```

---

### Task 5: The sandbox check (SPEC-001-R10 to R13, code half)

**Files:**
- Create: `scripts/dev/test_check_sandboxes.py`
- Create: `scripts/dev/check_sandboxes.py`
- Modify: `.env.example` (the "Read-only accounts" block and a new Anthropic line)

- [ ] **Step 1: Write the failing tests** at `scripts/dev/test_check_sandboxes.py`

```python
"""Tests for the sandbox access check (SPEC-001-R10 to R13). No network: a fake answers."""
# covers: SPEC-001-R10, SPEC-001-R11, SPEC-001-R12, SPEC-001-R13

from __future__ import annotations

import urllib.error
from collections.abc import Mapping
from pathlib import Path

from check_sandboxes import Result, load_env, render, run_all

# xxxx- values: gitleaks' allowlist clears them, and none is a real credential.
ENV = {
    "JIRA_SANDBOX_CLOUD_ID": "cloud-1234",
    "JIRA_SANDBOX_EMAIL": "bot@example.com",
    "JIRA_READ_TOKEN": "xxxx-jira-token",
    "SERVICENOW_BASE_URL": "https://pdi.example.test",
    "SERVICENOW_READ_USER": "thalam.read",
    "SERVICENOW_READ_PASSWORD": "xxxx-sn-password",
    "SLACK_BOT_TOKEN": "xxxx-slack-token",
    "ANTHROPIC_API_KEY": "xxxx-anthropic-key",
}

Answer = tuple[int, object] | Exception
READ_ONLY: dict[tuple[str, str], Answer] = {
    ("GET", "/project/search"): (200, {"values": []}),
    ("POST", "/rest/api/3/issue"): (401, {"message": "Unauthorized; scope does not match"}),
    ("GET", "/api/now/table/change_request?"): (
        200,
        {"result": [{"sys_id": "abc", "short_description": "Demo change"}]},
    ),
    ("PATCH", "/api/now/table/change_request/abc"): (403, {"error": {"message": "denied"}}),
    ("POST", "slack.com/api/auth.test"): (200, {"ok": True}),
    ("GET", "slack.com/api/users.conversations"): (
        200,
        {"ok": True, "channels": [{"name": "thalam"}]},
    ),
    ("GET", "api.anthropic.com/v1/models"): (200, {"data": []}),
}


class FakeHttp:
    def __init__(self, overrides: dict[tuple[str, str], Answer] | None = None) -> None:
        self.routes = {**READ_ONLY, **(overrides or {})}
        self.calls: list[tuple[str, str]] = []

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, object]:
        self.calls.append((method, url))
        for (verb, fragment), answer in self.routes.items():
            if verb == method and fragment in url:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        raise AssertionError(f"unexpected call {method} {url}")


def _one(results: list[Result], *words: str) -> Result:
    matches = [r for r in results if all(w in r.name for w in words)]
    assert len(matches) == 1, [r.name for r in results]
    return matches[0]


def test_every_check_passes_against_read_only_sandboxes() -> None:
    results = run_all(ENV, FakeHttp())
    assert len(results) == 7
    assert all(r.ok for r in results), render(results)


def test_a_jira_token_that_can_write_fails() -> None:
    results = run_all(ENV, FakeHttp({("POST", "/rest/api/3/issue"): (400, {"errors": {}})}))
    write = _one(results, "jira", "refused")
    assert not write.ok
    assert "CAN write" in write.detail


def test_a_servicenow_user_that_can_write_fails() -> None:
    results = run_all(
        ENV, FakeHttp({("PATCH", "/api/now/table/change_request/abc"): (200, {"result": {}})})
    )
    write = _one(results, "servicenow", "refused")
    assert not write.ok
    assert "CAN write" in write.detail


def test_servicenow_with_no_change_rows_cannot_prove_refusal() -> None:
    fake = FakeHttp({("GET", "/api/now/table/change_request?"): (200, {"result": []})})
    results = run_all(ENV, fake)
    assert not _one(results, "servicenow", "read change_request").ok
    assert not _one(results, "servicenow", "refused").ok
    assert not any(method == "PATCH" for method, _ in fake.calls)


def test_servicenow_address_must_be_https() -> None:
    results = run_all({**ENV, "SERVICENOW_BASE_URL": "http://pdi.example.test"}, FakeHttp())
    assert any("must start with https://" in r.detail for r in results if "servicenow" in r.name)


def test_a_slack_app_in_other_channels_fails() -> None:
    channels = {"ok": True, "channels": [{"name": "thalam"}, {"name": "general"}]}
    route = ("GET", "slack.com/api/users.conversations")
    results = run_all(ENV, FakeHttp({route: (200, channels)}))
    member = _one(results, "slack", "#thalam only")
    assert not member.ok
    assert member.detail == "channels: general, thalam"


def test_a_missing_or_placeholder_setting_fails_its_group_without_calling_it() -> None:
    env = {k: v for k, v in ENV.items() if k != "SLACK_BOT_TOKEN"}
    env["ANTHROPIC_API_KEY"] = "placeholder"
    fake = FakeHttp()
    results = run_all(env, fake)
    slack = _one(results, "R12")
    assert not slack.ok and slack.detail == "not set in .env: SLACK_BOT_TOKEN"
    assert not _one(results, "R13").ok
    assert not any("slack.com" in url or "anthropic.com" in url for _, url in fake.calls)


def test_an_unreachable_sandbox_fails_alone() -> None:
    results = run_all(
        ENV, FakeHttp({("GET", "/project/search"): urllib.error.URLError("down")})
    )
    jira = _one(results, "R10")
    assert not jira.ok and jira.detail == "unreachable (URLError)"
    assert all(r.ok for r in results if not r.name.startswith("R10"))


def test_the_output_never_contains_a_secret_or_an_address() -> None:
    results = run_all(
        ENV,
        FakeHttp({
            ("POST", "/rest/api/3/issue"): (400, {"errors": {}}),
            ("POST", "slack.com/api/auth.test"): (200, {"ok": False, "error": "invalid_auth"}),
        }),
    )
    text = "\n".join(render(results))
    for value in ENV.values():
        assert value not in text


def test_load_env_reads_values_and_skips_comments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('# a comment\n\nA=1\nB = "two"\nnot a setting\n', encoding="utf-8")
    assert load_env(env_file) == {"A": "1", "B": "two"}
    assert load_env(tmp_path / "missing.env") == {}
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest scripts/dev/test_check_sandboxes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_sandboxes'`

- [ ] **Step 3: Write `scripts/dev/check_sandboxes.py`**

```python
#!/usr/bin/env python3
"""Read-only access to every sandbox, proved (SPEC-001-R10 to R13).

    uv run python scripts/dev/check_sandboxes.py      # reads .env at the repository root

One line per check, PASS or FAIL. It never prints a token, a password or a site address. A
sandbox that is down fails its own lines while the others still run. Exit 1 if anything failed.

The refused-write probes are shaped so that even a credential that CAN write changes nothing:
  Jira        POST an issue with no fields: a writer gets 400 (validation), read-only 401 or 403
  ServiceNow  PATCH the first change with its own short description: a writer gets 200 (a no-op
              update), read-only gets 403
Stdlib only.
"""
# covers: SPEC-001-R10, SPEC-001-R11, SPEC-001-R12, SPEC-001-R13

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
Http = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, object]]
REFUSED = (401, 403)


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool
    detail: str


def load_env(path: Path) -> dict[str, str]:
    """KEY=value lines from a .env file; blank lines, comments and other lines skipped."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _is_set(value: str | None) -> bool:
    if not value:
        return False
    return "placeholder" not in value.lower() and "<" not in value


def _basic(user: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


def urllib_http(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None
) -> tuple[int, object]:
    """The real transport: (status, parsed JSON or None). HTTP errors are answers, not raises."""
    if not url.startswith("https://"):
        raise ValueError("only https:// addresses are called")
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        payload: object = json.loads(raw) if raw else None
    except ValueError:
        payload = None
    return status, payload


def check_jira(env: Mapping[str, str], http: Http) -> list[Result]:
    # Scoped API tokens are called through api.atlassian.com with the site's cloud ID.
    base = f"https://api.atlassian.com/ex/jira/{env['JIRA_SANDBOX_CLOUD_ID']}/rest/api/3"
    headers = {
        "Authorization": _basic(env["JIRA_SANDBOX_EMAIL"], env["JIRA_READ_TOKEN"]),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    status, _ = http("GET", f"{base}/project/search?maxResults=1", headers, None)
    read = Result("R10 jira sandbox: read with the read token", status == 200, f"HTTP {status}")
    status, _ = http("POST", f"{base}/issue", headers, b'{"fields": {}}')
    hint = "" if status in REFUSED else " (400 means this token CAN write)"
    write = Result(
        "R10 jira sandbox: a write with the read token is refused",
        status in REFUSED,
        f"HTTP {status}{hint}",
    )
    return [read, write]


def check_servicenow(env: Mapping[str, str], http: Http) -> list[Result]:
    base = env["SERVICENOW_BASE_URL"].rstrip("/")
    read_name = "R11 servicenow: read change_request with the read user"
    write_name = "R11 servicenow: a write with the read user is refused"
    if not base.startswith("https://"):
        detail = "SERVICENOW_BASE_URL must start with https://"
        return [Result(read_name, False, detail), Result(write_name, False, detail)]
    headers = {
        "Authorization": _basic(env["SERVICENOW_READ_USER"], env["SERVICENOW_READ_PASSWORD"]),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    query = "sysparm_limit=1&sysparm_fields=sys_id,short_description"
    status, payload = http("GET", f"{base}/api/now/table/change_request?{query}", headers, None)
    rows = payload.get("result") if isinstance(payload, dict) else None
    first = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
    if first is None:
        why = f"HTTP {status}" + (", but no change_request row to probe" if status == 200 else "")
        return [Result(read_name, False, why), Result(write_name, False, "skipped: " + why)]
    read = Result(read_name, status == 200, f"HTTP {status}")
    body = json.dumps({"short_description": first.get("short_description", "")}).encode()
    sys_id = first.get("sys_id", "")
    status, _ = http("PATCH", f"{base}/api/now/table/change_request/{sys_id}", headers, body)
    hint = "" if status in REFUSED else " (200 means this user CAN write)"
    return [read, Result(write_name, status in REFUSED, f"HTTP {status}{hint}")]


def _slack_error(payload: object) -> str:
    if isinstance(payload, dict) and payload.get("ok") is not True:
        return f", error {payload.get('error', '?')}"
    return ""


def check_slack(env: Mapping[str, str], http: Http) -> list[Result]:
    headers = {"Authorization": f"Bearer {env['SLACK_BOT_TOKEN']}"}
    status, payload = http("POST", "https://slack.com/api/auth.test", headers, b"")
    ok = status == 200 and isinstance(payload, dict) and payload.get("ok") is True
    auth = Result(
        "R12 slack: the bot token passes auth.test", ok, f"HTTP {status}" + _slack_error(payload)
    )
    url = (
        "https://slack.com/api/users.conversations"
        "?types=public_channel,private_channel&exclude_archived=true&limit=200"
    )
    status, payload = http("GET", url, headers, None)
    name = "R12 slack: the app is in #thalam only"
    channels = payload.get("channels") if isinstance(payload, dict) and payload.get("ok") else None
    if not isinstance(channels, list):
        return [auth, Result(name, False, f"HTTP {status}" + _slack_error(payload))]
    names = sorted(str(c.get("name", "?")) for c in channels if isinstance(c, dict))
    return [auth, Result(name, names == ["thalam"], "channels: " + (", ".join(names) or "none"))]


def check_anthropic(env: Mapping[str, str], http: Http) -> list[Result]:
    headers = {"x-api-key": env["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}
    status, _ = http("GET", "https://api.anthropic.com/v1/models?limit=1", headers, None)
    name = "R13 anthropic: the key lists models (a free call)"
    return [Result(name, status == 200, f"HTTP {status}")]


Check = Callable[[Mapping[str, str], Http], list[Result]]
JIRA_KEYS = ("JIRA_SANDBOX_CLOUD_ID", "JIRA_SANDBOX_EMAIL", "JIRA_READ_TOKEN")
SERVICENOW_KEYS = ("SERVICENOW_BASE_URL", "SERVICENOW_READ_USER", "SERVICENOW_READ_PASSWORD")
GROUPS: tuple[tuple[str, tuple[str, ...], Check], ...] = (
    ("R10 jira sandbox", JIRA_KEYS, check_jira),
    ("R11 servicenow", SERVICENOW_KEYS, check_servicenow),
    ("R12 slack", ("SLACK_BOT_TOKEN",), check_slack),
    ("R13 anthropic", ("ANTHROPIC_API_KEY",), check_anthropic),
)
KEYS = {key for _, keys, _ in GROUPS for key in keys}


def run_all(env: Mapping[str, str], http: Http) -> list[Result]:
    results: list[Result] = []
    for name, keys, check in GROUPS:
        missing = [key for key in keys if not _is_set(env.get(key))]
        if missing:
            results.append(Result(name, False, "not set in .env: " + ", ".join(missing)))
            continue
        try:
            results.extend(check(env, http))
        except (OSError, ValueError) as err:  # URLError and timeouts are OSErrors
            results.append(Result(name, False, f"unreachable ({type(err).__name__})"))
    return results


def render(results: list[Result]) -> list[str]:
    return [f"{'PASS' if r.ok else 'FAIL'}  {r.name}  ({r.detail})" for r in results]


def main() -> int:
    env = load_env(ROOT / ".env")
    env.update({key: value for key, value in os.environ.items() if key in KEYS})
    results = run_all(env, urllib_http)
    print("\n".join(render(results)))
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest scripts/dev/test_check_sandboxes.py -v`
Expected: all 10 PASS.

- [ ] **Step 5: Update `.env.example`**

Replace this block:

```
# Read-only accounts (agent) — sandboxes only
JIRA_BASE_URL=https://<your-site>.atlassian.net
JIRA_READ_TOKEN=placeholder
SERVICENOW_BASE_URL=https://<your-pdi>.service-now.com
SERVICENOW_READ_USER=placeholder
SERVICENOW_READ_PASSWORD=placeholder
```

with:

```
# Read-only accounts (agent) — sandboxes only. Checked by `make sandboxes` (SPEC-001-R10..R13).
# Jira: the SANDBOX site, never the planning site (ADR-0011). Scoped token, read scopes only.
JIRA_SANDBOX_CLOUD_ID=<cloud-id>          # from https://<your-sandbox>.atlassian.net/_edge/tenant_info
JIRA_SANDBOX_EMAIL=<bot-account-email>
JIRA_READ_TOKEN=placeholder
SERVICENOW_BASE_URL=https://<your-pdi>.service-now.com
SERVICENOW_READ_USER=placeholder           # has snc_read_only
SERVICENOW_READ_PASSWORD=placeholder
```

And under `# Slack`, after `SLACK_APP_TOKEN=xapp-placeholder`, add:

```

# Hosted model (ADR-0006). The console spend limit is <= $20/month (ADR-0008).
ANTHROPIC_API_KEY=placeholder
```

- [ ] **Step 6: Run it with no `.env`** (every group should fail cleanly and nothing should be called)

Run: `uv run python scripts/dev/check_sandboxes.py; echo "exit $?"`
Expected: four `FAIL ... (not set in .env: ...)` lines and `exit 1`.

- [ ] **Step 7: Commit**

```bash
git add scripts/dev/check_sandboxes.py scripts/dev/test_check_sandboxes.py .env.example
git commit -m "feat: THL-1 sandbox check proving read-only access"
```

---

### Task 6: Makefile and a clean lint (SPEC-001-R4, locally)

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Write `Makefile`** (recipe lines start with a TAB)

```make
SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nThalam — make targets\n\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: sync
sync: ## Install exactly what uv.lock says into .venv (what CI uses)
	uv sync --locked --all-extras

.PHONY: lint
lint: ## ruff + mypy --strict (SPEC-001-R4)
	ruff check services scripts
	mypy services scripts/dev

.PHONY: test
test: ## pytest, then the spec coverage table (SPEC-001-R8)
	pytest -q
	python scripts/dev/spec_coverage.py

.PHONY: hooks
hooks: ## Install the pre-commit and commit-msg hooks
	bash scripts/dev/install-hooks.sh

.PHONY: secrets-scan
secrets-scan: ## gitleaks over the whole history
	gitleaks git --config .gitleaks.toml --redact --no-banner .

.PHONY: sandboxes
sandboxes: ## Prove read-only access to every sandbox (reads .env; SPEC-001-R10..R13)
	python scripts/dev/check_sandboxes.py
```

- [ ] **Step 2: Run the lint**

Run: `uv run make lint`
Expected: `All checks passed!` from ruff and `Success: no issues found in 8 source files` from mypy. If ruff reports import order (`I001`), run `uv run ruff check --fix services scripts`, re-run, and check that the diff only moves imports. Fix any mypy error at its source, never with `# type: ignore`.

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -q`
Expected: `47 passed` (1 + 21 + 15 + 10).

- [ ] **Step 4: Commit**

```bash
git add Makefile
git add -u   # any import-order fixes from step 2
git commit -m "chore: THL-1 Makefile with lint, test, hooks and sandbox targets"
```

---

### Task 7: The lab doc skeleton (`docs/labs/00-foundations.md`)

**Files:**
- Create: `docs/labs/00-foundations.md`

- [ ] **Step 1: Write the lab.** Evidence lines say `_not run yet_` until each step runs. The spec moves to Built only after every Evidence line is filled.

````markdown
# Lab 00 — Foundations: a public repo, CI, and read-only sandboxes

Proves SPEC-001's live requirements ([spec](../specs/SPEC-001-phase-0-foundations.md)). Written so
a stranger can repeat it from zero. **Never write a real site address, tenant ID or token here**
(CLAUDE.md rule 6). Use the placeholders shown, and keep real values in `.env`.

**You need:** Git, uv, gitleaks 8.30.1, the GitHub CLI (logged in), a browser. **Cost:** $0.

## 1. Jira planning project — SPEC-001-R9

1. On your existing Jira site: sidebar → Spaces → **Create space** → Kanban → team-managed, name
   **Thalam**, key **THL** (`THLM` if taken, ADR-0009). Type the key; the wizard may suggest
   another.
2. Create one epic per roadmap phase, Phase 0 first, so the Phase 0 epic is `THL-1`.
3. Settings → User management: confirm no bot account exists on this site. Bots live only on
   the sandbox site (section 2, ADR-0011).

**Evidence:** _not run yet_ (date, epic keys, "no bot users").

## 2. Sandbox Jira site and its read-only token — SPEC-001-R10

1. Create a **new** free Jira site, `<your-sandbox>.atlassian.net`, separate from the planning
   site. Create one project in it (any name; Phase 1 adds the fixture company).
2. Invite a bot account (for example a `+thalam-bot` alias of your email), accept, sign in as it.
3. As the bot, at id.atlassian.com → Security → API tokens → **Create API token with scopes**:
   app **Jira**, scopes **read only** (`read:jira-work`, plus `read:jira-user` if required).
   Choose the longest expiry and write the date in the table at the end.
   If scoped tokens are not offered, stop: the fallback is an OAuth app with read scopes, which
   needs a change to `check_sandboxes.py`.
4. Cloud ID: open `https://<your-sandbox>.atlassian.net/_edge/tenant_info` and copy `cloudId`.
5. In `.env`: `JIRA_SANDBOX_CLOUD_ID`, `JIRA_SANDBOX_EMAIL`, `JIRA_READ_TOKEN`.

## 3. ServiceNow developer instance and its read-only user — SPEC-001-R11

1. developer.servicenow.com → sign in → **Request instance**. Write down the current rules for
   sleeping and reclaiming idle instances, as the page states them on the day: _not run yet_.
2. As admin: User Administration → Users → New. User ID `thalam.read`, set a password, tick
   **Web service access only**. Roles: `itil` (to read `change_request`) and **`snc_read_only`**
   (blocks every write, whatever other roles allow).
3. In `.env`: `SERVICENOW_BASE_URL=https://<your-pdi>.service-now.com`,
   `SERVICENOW_READ_USER`, `SERVICENOW_READ_PASSWORD`.

## 4. Slack app — SPEC-001-R12

1. api.slack.com/apps → Create New App → From scratch → name **Thalam** → your workspace.
2. OAuth & Permissions → Bot Token Scopes: `channels:read` and `groups:read` only (so it can list
   its own channels). Posting comes in Phase 3.
3. Install to Workspace, then copy the Bot User OAuth Token to `.env` as `SLACK_BOT_TOKEN`.
4. Create `#thalam` and run `/invite @Thalam` in it. Invite it nowhere else.

## 5. Anthropic key with a spend limit — SPEC-001-R13

1. console.anthropic.com → Settings → Limits: set a **monthly spend limit of $20 or less**
   (ADR-0008) and an email notification below it.
2. API keys → Create key `thalam-dev`, then copy it to `.env` as `ANTHROPIC_API_KEY`.

**Evidence:** _not run yet_ (the limit, the notification amount, the date; never the key).

## 6. Repository and ruleset — SPEC-001-R1, SPEC-001-R2

Done in plan Task 9. Commands and outputs go here.

**Evidence R1:** _not run yet_ (`gh repo view roshanoommenreji/thalam --json visibility,defaultBranchRef`)

**Evidence R2:** _not run yet_ (ruleset id and rules from `gh api`, plus the refused direct push)

## 7. A planted fake secret is blocked — SPEC-001-R6

The pre-commit hook was given a random, never-issued GitHub-shaped token (plan Task 3, step 7).

**Evidence:** _not run yet_ (date and the redacted gitleaks finding line)

## 8. Run the sandbox check — SPEC-001-R10 to R13

```bash
uv run python scripts/dev/check_sandboxes.py
```

Expected: seven `PASS` lines. The output never contains a token or an address, by design, so it
can be pasted here.

**Evidence:** _not run yet_

## Credentials and their expiry

| Credential | Where | Expires | Rotate by |
|---|---|---|---|
| Jira sandbox read token | bot account, id.atlassian.com | _not run yet_ | |
| ServiceNow `thalam.read` | the instance | password policy of the instance | |
| Slack bot token | api.slack.com/apps | does not expire; revoke by uninstalling | |
| Anthropic `thalam-dev` | console.anthropic.com | no expiry; revoke in the console | |

## If a sandbox is down or reclaimed

`check_sandboxes.py` fails only that sandbox's lines. A sleeping ServiceNow instance wakes from
the developer portal; a reclaimed one is re-requested, and sections 3 and 8 are repeated.
````

- [ ] **Step 2: Check the lab passes the scanner**

Run: `gitleaks dir --config .gitleaks.toml --no-banner --redact docs/labs`
Expected: `no leaks found` (the placeholders are not real addresses).

- [ ] **Step 3: Commit**

```bash
git add docs/labs/00-foundations.md
git commit -m "docs: THL-1 Lab 00 skeleton for SPEC-001's live proofs"
```

---

### Task 8: CI, CodeQL, Dependabot and the ruleset file (SPEC-001-R4, R6, R7, R8)

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/codeql.yml`, `.github/dependabot.yml`
- Create: `.github/rulesets/main.json`
- Modify: `scripts/dev/test_spec_coverage.py` (the import line, plus one test at the end)

- [ ] **Step 1: Add the real-repository test** (it fails until this task's files exist)

In `scripts/dev/test_spec_coverage.py`, replace `from spec_coverage import check, main` with
`from spec_coverage import ROOT, check, main`, and append:

```python


def test_the_real_repository_passes() -> None:
    assert check(ROOT)[2] == []
```

Run: `uv run pytest scripts/dev/test_spec_coverage.py::test_the_real_repository_passes -v`
Expected: FAIL, listing `.github/workflows/ci.yml`, `codeql.yml` and `dependabot.yml` as missing proofs.

- [ ] **Step 2: Write `.github/workflows/ci.yml`**

```yaml
# CI: every pull request, and main after each merge (SPEC-001; copied from Kaval's ci.yml).
# covers: SPEC-001-R4, SPEC-001-R6
#
# Supply-chain hygiene, as in Kaval: every third-party action is pinned to a full commit SHA (the
# tag is a comment), the gitleaks binary is checked against the sha256 below, the token is
# read-only, and no job reads a secret. Job names are short on purpose: the ruleset on main
# requires `lint`, `test` and `secrets` by name (.github/rulesets/main.json).

name: ci

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: "3.11"
  GITLEAKS_VERSION: "8.30.1"
  GITLEAKS_SHA256: "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb" # linux_x64

jobs:
  lint:
    name: lint
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 0 # the commit check sees every commit the PR adds
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          enable-cache: true
      - run: uv sync --locked --all-extras
      - run: uv run make lint
      # Values go through env, never straight into the script: a branch name is user input.
      - name: commit messages
        if: github.event_name == 'pull_request'
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          HEAD_REF: ${{ github.head_ref }}
        run: uv run python scripts/dev/check_commits.py --range "$BASE_SHA..$HEAD_SHA" --branch "$HEAD_REF"

  test:
    name: test
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          enable-cache: true
      - run: uv sync --locked --all-extras
      - run: uv run pytest -ra
      - name: spec coverage (job summary, SPEC-001-R8)
        run: uv run python scripts/dev/spec_coverage.py

  secrets:
    name: secrets
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0 # the whole history: the repo is public, so history must be clean
          persist-credentials: false
      - name: install gitleaks (checksum-verified)
        run: |
          curl -fsSL --retry 5 --retry-all-errors -o gitleaks.tgz \
            "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
          echo "${GITLEAKS_SHA256}  gitleaks.tgz" | sha256sum --check --strict
          tar -xzf gitleaks.tgz gitleaks && rm gitleaks.tgz
      - run: ./gitleaks git --config .gitleaks.toml --redact --no-banner .
```

- [ ] **Step 3: Write `.github/workflows/codeql.yml`**

```yaml
# CodeQL: GitHub's own code scanner on every PR, on main after each merge, and weekly
# (SPEC-001-R7; copied from Kaval's codeql.yml). Free because the repository is public (ADR-0011).
# covers: SPEC-001-R7
#
# Two jobs: python (the code) and actions (the workflow files: CI is code, and it holds a token).
# Neither needs a build. Both are required on main by name: "codeql (python)", "codeql (actions)".

name: codeql

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "41 4 * * 1" # Mondays, 04:41 UTC
  workflow_dispatch:

permissions: {}

concurrency:
  group: codeql-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  analyze:
    name: codeql (${{ matrix.language }})
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    permissions:
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        include:
          - language: python
            build-mode: none
          - language: actions
            build-mode: none
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: github/codeql-action/init@33d7b85da1a04171e211befe2c739303b9a4c066 # v4.39.3
        with:
          languages: ${{ matrix.language }}
          build-mode: ${{ matrix.build-mode }}
      - uses: github/codeql-action/analyze@33d7b85da1a04171e211befe2c739303b9a4c066 # v4.39.3
        with:
          category: "/language:${{ matrix.language }}"
```

- [ ] **Step 4: Write `.github/dependabot.yml`**

```yaml
# Dependabot opens weekly, grouped pull requests for outdated dependencies (SPEC-001-R7; copied
# from Kaval). Each one goes through ci.yml and merges only when green. Not covered: the gitleaks
# binary in ci.yml, whose version and sha256 are bumped together by hand.
# covers: SPEC-001-R7

version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly, day: saturday }
    groups:
      actions: { patterns: ["*"] }
    commit-message: { prefix: chore }

  - package-ecosystem: uv # reads pyproject.toml and updates uv.lock
    directory: /
    schedule: { interval: weekly, day: saturday }
    groups:
      python: { patterns: ["*"] }
    commit-message: { prefix: chore }
```

- [ ] **Step 5: Write `.github/rulesets/main.json`** (applied in Task 9; kept here so the rules are reviewable and repeatable)

```json
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "bypass_actors": [],
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["squash"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          { "context": "lint" },
          { "context": "test" },
          { "context": "secrets" },
          { "context": "codeql (python)" },
          { "context": "codeql (actions)" }
        ]
      }
    }
  ]
}
```

- [ ] **Step 6: Run everything locally**

```bash
uv run pytest -q
uv run make lint
uv run python scripts/dev/spec_coverage.py; echo "exit $?"
```

Expected: `48 passed`, lint clean, a 13-row table, `exit 0`.

- [ ] **Step 7: Commit**

```bash
git add .github scripts/dev/test_spec_coverage.py
git commit -m "feat: THL-1 CI (lint, test, secrets), CodeQL, Dependabot and the main ruleset"
```

---

### Task 9: Publish the repo and protect `main` (STOP — Roshan's go: it creates a public repo and pushes)

*Amended 2026-11-18 after the pre-publication review:* ADR-0011 is written before the push (four
committed files cite it), the scan adds a default-rules cross-check, both workflows must be green
before the ruleset goes on, and squash merges keep the no-reply email. Story key: `THL-19`.

**Files:**
- Create: `docs/adr/0011-phase-0-shape.md` (step 1, before anything is public)
- Modify: `docs/adr/0009-name-and-jira-key.md` (its folder note points at ADR-0011)
- Modify: `docs/labs/00-foundations.md` (section 6 evidence; section 7 was filled in Task 3)

- [ ] **Step 0 (Roshan): GitHub email privacy.** github.com → Settings → Emails: tick **Keep my
  email addresses private** and **Block command line pushes that expose my email**. Without it, a
  squash merge made on GitHub can carry the primary email. The merges below also pass
  `--author-email` with the no-reply address, so both guards hold.

- [ ] **Step 1: ADR-0011, committed on `main` before the push.** The decision to go public comes
  before going public. Text: `docs/adr/0011-phase-0-shape.md` (written 2026-11-18).

- [ ] **Step 2: Full-history scan, last check before going public**

```bash
make secrets-scan
printf '[extend]\nuseDefault = true\n' > /tmp/gitleaks-default.toml
gitleaks git --config /tmp/gitleaks-default.toml --no-banner --redact .
git log --all --format='%ae%n%ce' | sort -u
```

Expected: `no leaks found` twice (the repo's rules, then gitleaks' defaults alone, so the
allowlist hides nothing), and only the `…@users.noreply.github.com` address.

- [ ] **Step 3: Create the public repo and push** (after Roshan's go)

```bash
gh repo create roshanoommenreji/thalam --public --source . --remote origin \
  --description "Release-coordination agent with human-in-the-loop approval (Kaval's sibling)"
git push -u origin main
gh repo edit roshanoommenreji/thalam --enable-squash-merge --enable-merge-commit=false \
  --enable-rebase-merge=false --delete-branch-on-merge
```

- [ ] **Step 4: Wait for both workflows on `main` to go green**

```bash
gh run list --repo roshanoommenreji/thalam --branch main --limit 5
for wf in ci.yml codeql.yml; do
  gh run watch --repo roshanoommenreji/thalam --exit-status \
    "$(gh run list --repo roshanoommenreji/thalam --workflow "$wf" --branch main --limit 1 --json databaseId -q '.[0].databaseId')"
done
```

Expected: `ci` and `codeql` both succeed (if the list is empty, the runs have not registered yet;
re-run it after a few seconds). A failure is fixed before the ruleset goes on: the ruleset
requires the codeql checks, so a red codeql would block every PR. While `main` is still
unprotected, the fix may be pushed directly, but only this once.

- [ ] **Step 5: Apply the ruleset**

```bash
gh api -X POST repos/roshanoommenreji/thalam/rulesets --input .github/rulesets/main.json -q '.id, .enforcement'
gh api repos/roshanoommenreji/thalam/rules/branches/main -q '.[].type'
```

Expected: an id and `active`, then `deletion`, `non_fast_forward`, `required_linear_history`, `pull_request`, `required_status_checks`.

- [ ] **Step 6: Prove a direct push to `main` is refused** (the negative case for R2)

```bash
git commit --allow-empty -m "chore: THL-19 ruleset probe"
git push origin main; echo "exit $?"
git reset --soft HEAD~1
```

Expected: `GH013: Repository rule violations found for refs/heads/main` and a non-zero exit. The reset removes only the empty probe commit.

- [ ] **Step 7: Record evidence in Lab 00 section 6, on a branch, through a PR** (this is also the first proof that the PR flow works)

```bash
git switch -c docs/THL-19-lab-00-repo-evidence
gh repo view roshanoommenreji/thalam --json visibility,defaultBranchRef
```

Replace the `_not run yet_` lines under R1 and R2 with the date, the commands and their outputs: visibility `PUBLIC`, default branch `main`, the ruleset rule types and the GH013 line. Then:

```bash
git add docs/labs/00-foundations.md
git commit -m "docs: THL-19 Lab 00 evidence for the repo and the ruleset"
git push -u origin docs/THL-19-lab-00-repo-evidence
gh pr create --base main --title "docs: THL-19 Lab 00 evidence for the repo and the ruleset" \
  --body "Evidence for SPEC-001-R1 and R2 in Lab 00 section 6."
gh pr checks --watch
gh pr merge --squash --delete-branch \
  --author-email 37763145+roshanoommenreji@users.noreply.github.com
git switch main && git pull --ff-only
```

Give every PR an explicit conventional `--title`: with more than one commit, GitHub uses the title
as the squash subject on `main`, and `--fill` would use the branch name instead.

Expected: all five required checks pass, and the squash merge succeeds. Its author is the no-reply
address; its committer is `noreply@github.com`, which is GitHub's own.

---

### Task 10: Sign-ups and the live sandbox check (STOP — Roshan: lab sections 2–5)

Story key: `THL-20`.

**Files:**
- Modify: `docs/labs/00-foundations.md` (sections 5 and 8 evidence, and the expiry table; sections 1 and 3 were filled in Tasks 0 and 7)

- [ ] **Step 1:** Roshan follows lab sections 2–5 and fills in `.env` (copied from `.env.example`). Section 1 was Task 0.
- [ ] **Step 2: Run the check**

Run: `make sandboxes`
Expected: seven `PASS` lines and exit 0. What a failure usually means:
- R10 read `HTTP 401`: the email or token is wrong, or the token was made on the planning site's account.
- R10 write `HTTP 400 (... CAN write)`: the token has write scopes. Recreate it with read scopes only.
- R11 write `HTTP 200 (... CAN write)`: `snc_read_only` is missing from `thalam.read`. If the
  Roles tab does list it, the role is not blocking REST writes on this release: stop and record
  it. (Not confirmed beforehand whether the refusal is a 403; either way the check fails closed.)
- R12 `channels: general, thalam`: remove the app from `#general`.

- [ ] **Step 3: Fill in Lab 00's evidence** for sections 5 and 8 (paste the check output), plus the expiry table. Do it on branch `docs/THL-20-lab-00-sandbox-evidence`, commit `docs: THL-20 Lab 00 evidence for the sandboxes`, through a PR as in Task 9 step 7 (explicit title, `--author-email`).

---

### Task 11: Close the phase — docs that follow, spec to Built

Story key: `THL-21`.

**Files:**
- Modify: `ROADMAP.md`, `README.md`, `docs/journal/<date>.md`, `docs/specs/SPEC-001-phase-0-foundations.md`, and `docs/adr/0011-phase-0-shape.md` only if it no longer matches what was built
- Outside the repo: `vault/projects/thalam.md`, `vault/daily/<date>.md` (use the `obsidian` skill)

- [ ] **Step 1: Branch**

Run: `git switch -c docs/THL-21-phase-0-close`

- [ ] **Step 2: Check ADR-0011 against what was built.** It was written in Task 9 step 1, before
  the push (*amended 2026-11-18*; the draft text that stood here is now the file itself). Amend it
  only if Tasks 9–10 changed a fact in it.

<!-- First draft of ADR-0011, kept only as the plan's record; the file in docs/adr/ is authoritative.

```markdown
# ADR-0011 — Phase 0 shape: public repo, two Jira sites, AWS guard moves to Phase 7

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan (SPEC-001, questions 1–3)

## Context

Writing SPEC-001 turned up three facts that changed Phase 0:

1. On GitHub Free, branch protection, rulesets and free CodeQL scanning work only on public
   repositories.
2. Jira Free cannot restrict project access: everyone with product access is effectively a
   project admin. So a bot account on a site can read and change every project there.
3. Thalam spends nothing on AWS before Phase 7. Phases 1–6 run locally, and the hosted model is
   the Anthropic API directly (ADR-0006).

## Decision

1. **The repository is public from its first push**, like Kaval. CLAUDE.md already assumes it
   (rule 6, gitleaks). Phase 8's "repo public" becomes a final access review.
2. **Two Jira sites.** Planning (`THL`) lives on the existing site, next to Kaval's, with no bot
   accounts. The sandbox is a separate free site that holds only fixture data and the bots.
   Read-only is enforced by the token's scopes, since Jira Free cannot enforce it by permission.
3. **AWS budget alarms and the hard stop move to the start of Phase 7**, before the first AWS
   resource and together with the account choice (Kaval's or a new one). Until then the only paid
   meter is the Anthropic key, capped at $20 or less a month in its console (ADR-0008).
4. **The local folder stays `Release Agent`**; the repository is `thalam`. This replaces
   ADR-0009's note that the folder would be renamed at `git init`.

## Alternatives rejected

- A private repo on Free (no enforced protection, no CodeQL), or GitHub Pro (~$4/month, still no
  free CodeQL on private repos).
- One new Jira site for both planning and sandbox, or everything on the existing site: either
  way the bots become admins of the planning board, and in the second case of Kaval's too.
- Building AWS guards now, in Kaval's account (its account-wide budget would count Thalam) or in
  a new account (one more account to secure, months before it holds anything).

## Consequences

Everything in the repo is public from day one, so rule 6 is enforced by two gitleaks rules
(real Atlassian and ServiceNow addresses), not by care alone. Two Jira logins. Cost guarding before
Phase 7 depends on the Anthropic console limit.
**Revisit if:** the repo must hold something that cannot be public, or Thalam needs AWS before
Phase 7.
```
-->

- [ ] **Step 3: Update `ROADMAP.md`**

First, the planning-board line near the top links a claude.ai artifact that public readers cannot
open: apply Roshan's call on it (keep, mark as private, or remove).

Replace this block of Phase 0 lines (keep the lines above it unchanged):

```
- [ ] Requirement-to-test check in CI: a requirement ID with no citing test fails (KAV-120 Stage 2)
- [ ] SPEC-001 for Phase 0 and SPEC-002 for Phase 1 drafted and approved before building
- [ ] Sign up: Jira Cloud free site (project `THL`), ServiceNow developer program + PDI, Slack
      workspace app, Anthropic API key with a spend limit set in its console
- [ ] Git repo `thalam`, GitHub, branch protection, CI skeleton (ruff, mypy, pytest, gitleaks, CodeQL)
- [ ] Jira project + epics mirroring this roadmap
- [ ] AWS budget alarms and the hard stop, **before** any compute (Kaval Lab 01)
```

with:

```
- [x] [SPEC-001](docs/specs/SPEC-001-phase-0-foundations.md) approved and built; plan in
      [docs/specs/plans/](docs/specs/plans/SPEC-001-plan.md); proofs in [Lab 00](docs/labs/00-foundations.md)
- [x] Requirement-to-test check in CI (`scripts/dev/spec_coverage.py`, KAV-120 Stage 2)
- [x] Public repo `thalam`, ruleset on `main`, CI (ruff, mypy, pytest, gitleaks, CodeQL, Dependabot)
      ([ADR-0011](docs/adr/0011-phase-0-shape.md))
- [x] Jira: `THL` planning project + epics on the existing site; a separate sandbox site with a
      read-only scoped token; ServiceNow PDI with an `snc_read_only` user; Slack app in `#thalam`;
      Anthropic key with a console spend limit of $20 or less
- [-] AWS budget alarms and the hard stop: moved to the start of Phase 7 (ADR-0011)
- [ ] SPEC-002 (Phase 1) drafted and approved before any Phase 1 code
```

Then change `## Phase 0 — Foundations · \`[~]\`` to `## Phase 0 — Foundations · \`[x]\``.

In Phase 7, replace:

```
Kaval's path, reused: k3d → k3s on Graviton, Helm, Flux, staging on demand, signed images,
promotion by digest, restore drills.
```

with:

```
- [ ] **First, before any AWS resource:** choose the account (Kaval's or a new one), then budget
      alarms at $70 / $85 and the hard stop at $95 (ADR-0008, ADR-0011, Kaval Lab 01)

Kaval's path, reused: k3d → k3s on Graviton, Helm, Flux, staging on demand, signed images,
promotion by digest, restore drills.
```

In Phase 8, replace `access review,\nrepo public.` with `access review (the repo has been public
since Phase 0, ADR-0011).`

- [ ] **Step 4: Update `README.md`'s status table**

Replace `| **Phase** | 0 — Foundations, started 2026-11-18 |` with
`| **Phase** | 0 — Foundations done (exit gate passed <the date Task 10 passed>); next: Phase 1 via SPEC-002 |`,
writing the real date.

- [ ] **Step 5: Set SPEC-001 to Built and fill in Measured**

In `docs/specs/SPEC-001-phase-0-foundations.md`, change `- **Status:** Approved` to
`- **Status:** Built`. Replace the `## Measured` body with the real numbers: hours, pages reviewed
(spec plus plan), defects found after merge, tokens used (from the session's usage view), and the
three issues the spec caught.

Run: `uv run python scripts/dev/spec_coverage.py; echo "exit $?"`
Expected: 13 rows, each with a "Cited by" or a "Live proof", and `exit 0`. If a row shows `—` in
both, its proof is missing: fix that, not the check.

The check counts a lab that names a requirement as its live proof, whether or not the evidence is
filled in, so it passes today already. This gate is the one that can fail:

Run: `grep -c '_not run yet_' docs/labs/00-foundations.md`
Expected: `0`. Any other number means a live proof has no evidence yet, so SPEC-001 is not Built.

- [ ] **Step 6: Journal entry** in `docs/journal/<today>.md` (append if the file exists): what was built, the three spec catches, the measurements, and next (SPEC-002).

- [ ] **Step 7: Commit, PR, merge**

```bash
git add docs ROADMAP.md README.md
git commit -m "docs: THL-21 close Phase 0 (ROADMAP, README, SPEC-001 Built)"
git push -u origin docs/THL-21-phase-0-close
gh pr create --base main --title "docs: THL-21 close Phase 0 (ROADMAP, README, SPEC-001 Built)" \
  --body "Phase 0 exit gate passed; SPEC-001 set to Built with its measurements."
gh pr checks --watch
gh pr merge --squash --delete-branch \
  --author-email 37763145+roshanoommenreji@users.noreply.github.com
git switch main && git pull --ff-only
```

Expected: all required checks pass. The `test` job's summary shows the coverage table, and Built
is now enforced.

- [ ] **Step 8: Vault** (invoke the `obsidian` skill). Update `vault/projects/thalam.md` (status: Phase 0 done, the repo URL, next SPEC-002, bump `updated:`), append to `vault/daily/<today>.md`, and add ADR-0011's three calls to `vault/decisions/README.md`. Move story `THL-21`, then the Phase 0 epic `THL-1`, to Done in Jira.

---

## Self-review (done while writing)

- **Spec coverage:** R1 → T9 · R2 → T8 s5, T9 s4–5 · R3 → T2 · R4 → T6, T8 · R5 → T3 · R6 → T1 s4–6, T3 s7, T8 · R7 → T8 · R8 → T4, T8 s1 · R9 → T0 · R10–R13 → T5, T10 · Docs-that-follow → T11. Out-of-scope items (AWS, compose, write credentials) have no task, as intended.
- **Placeholders:** none in code. `_not run yet_` lines in Lab 00 are filled with real evidence in T9–T10, before Built.
- **Names checked across tasks:** `problems`, `check`, `main`, `ROOT`, `run_all`, `render`, `load_env`, `Result`, the job names `lint`/`test`/`secrets`/`codeql (python)`/`codeql (actions)` (ci.yml, codeql.yml, ruleset), and the env keys (`.env.example`, `check_sandboxes.py`, Lab 00).
- **Test counts:** bootstrap 1, commits 21 (8 + 1 + 11 + 1), coverage 15 (+1 in T8), sandboxes 10. That is 47 after T6 and 48 after T8.

## As built (2026-11-18, after Tasks 0–8 and the pre-publication review)

The code blocks above are the first drafts. Per-task spec and quality reviews changed the code, so
**the repository is authoritative** where they differ. The changes, in short:

- 126 tests, not 48: commits 29, coverage 71 (one runs the check on the real repo), sandboxes 25,
  bootstrap 1.
- Makefile recipes run through `uv run`, and `secrets-scan` fails clearly if gitleaks is missing.
- The ruleset pins each required check to the GitHub Actions app (`integration_id` 15368).
- `check_commits.py` requires the story branch's **own** key (SPEC-001-R5's "that THL key"), not
  any THL key.
- The coverage check fails closed on more cases (malformed rows, empty specs folder, weak or
  unsafe proof paths, tags that are not line-start comments).
- The sandbox check never follows redirects and reads a `.env` with a BOM, `export` and inline
  comments.
- gitleaks' Atlassian rule catches a site name with or without `.net` and with an escaped dot.
  The review found the planning site's name in Task 1 step 7's `grep` command, in that form; the
  history was rewritten before the first push.
