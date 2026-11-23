# SPEC-002 — Phase 1 the release graph: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Approved:** Roshan, 2026-11-23. Execution: subagent-driven
(`superpowers:subagent-driven-development`), one fresh agent per task, each followed by a spec
review and a code review.

**Goal:** answer "what must ship before `cart-api 2.3`?" from Postgres, with no model, by building
[SPEC-002](../SPEC-002-phase-1-release-graph.md)'s requirements R1–R15.

**Architecture:**
- **The database:** Postgres runs alone in `compose.yaml`. Alembic creates seven tables. Two roles
  enforce the rules as grants: `thalam_reader` can only read, and `thalam_loader` can never change
  history.
- **The loader:** `thalam_collector` reads the fixture company's files (a Backstage catalog,
  release manifests, Jira-shaped JSON and a calendar). It checks everything, and only then writes,
  in one transaction.
- **The queries:** `thalam_shared.graph` is a pure Python core over one snapshot.
  `thalam_shared.graph_read` builds that snapshot from Postgres, and `thalam_shared.ask` prints the
  answer.

**Tech stack:** Python 3.11, SQLAlchemy 2.1.9, Alembic 1.20.1, psycopg 3.3.9, Pydantic 2.14.4,
PyYAML 6.0.4, packaging 26.3 (all checked on PyPI on 2026-11-23); Postgres 16 in
`pgvector/pgvector:0.8.7-pg16-bookworm`. That image's digest was checked on 2026-11-23 and is the
same one Kaval pins. The graph walk uses stdlib `graphlib`.

**Dry run, 2026-11-23, before this plan was reviewed:**
- **What ran:**
  - Every Python file, test and fixture file below was extracted into a scratch tree outside
    the repo, with the pinned versions.
  - Run against a throwaway Postgres container from the same image, removed afterwards.
- **What passed:**
  - **93 tests.** `THALAM_REQUIRE_DB=1` meant no skips; deprecations counted as errors; the
    database already held the fixture.
  - **`alembic check`** found no drift. `mypy --strict` and ruff are clean.
  - **The real `load` and `ask`** print exactly what Lab 01 expects.
- **What it found and fixed (6):**
  1. YAML read an unquoted `1.1` as a number, so the X.Y.Z check never ran.
  2. A variable changed type between two loops, which strict mypy refuses.
  3. A message was trimmed as if it were a `KeyError`'s quoted text.
  4. Tests failed after a real `make load`. Each test now starts from empty tables.
  5. Output was cp1252 in Git Bash, so `·` printed as a replacement character.
  6. SQLAlchemy 2.1 deprecated `Result.tuples()`.
- **Not run yet:** the Makefile, `compose.yaml` and `ci.yml` changes, `test_compose.py`, and Lab
  01 on Roshan's laptop. Construction proves them.

---

## Before you start (read once)

- **Rules:**
  - `CLAUDE.md` wins over this plan.
  - Never read `.env`. Code may read it at run time, through `thalam_shared.env`, and only for the
    names it asks for.
  - Never print a password or a database URL.
  - No real hosts in any file: the fixture uses `xxxx`.
- **Line endings:** `.gitattributes` says `eol=lf`. The Write tool can produce CRLF, so after
  writing a file, run
  `uv run python -c "from pathlib import Path; p=Path('<file>'); p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))"`.
- **Python 3.11:** no f-string may nest the quote character it is written in.
- **Commits:**
  - `type: THL-<n> what changed`, with types `feat`, `fix`, `docs`, `infra` and `chore`. The subject
    is at most 100 characters, and the hook checks it.
  - Write the message to a file, then `git commit -F <file>`.
  - End it with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Branches and PRs:**
  - One short-lived branch per task: `feat/THL-<n>-<slug>`, cut from `main`.
  - Each PR body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
  - Merge with
    `gh pr merge <N> --squash --delete-branch --author-email <Roshan's GitHub no-reply address>`
    once `lint`, `test`, `secrets`, `codeql (python)` and `codeql (actions)` are green.
  - **Roshan's approval of this plan is the go for each task's push, PR and merge.** Lab 01's live
    run (Task 12) is his.
- **Tests:**
  - Each test file starts with `# covers: SPEC-002-Rn` for the requirements it proves.
  - A database test asks for the `db` or `as_role` fixture (Task 3 and Task 4). It skips locally
    without Postgres and fails in CI (`THALAM_REQUIRE_DB=1`).
  - To run database tests locally: `make db-up`, `make migrate` and `make db-roles` (needs the
    Task 2 to 4 values in `.env`).
- **Test file names:** keep them unique across the repo. pytest's importlib mode allows duplicates,
  but mypy still maps each test file to a top-level module name.
- **Ruff's import order:** if ruff reports it (I001), run `uv run ruff check --fix <file>`. Don't
  reorder imports by hand.
- **Missing `.env` values:** if a step needs a value `.env` doesn't have (a `MissingSetting` or
  `set X in .env` message), stop and ask Roshan to add it. Never write `.env` yourself.

**Story close-out (the last step of every task):**
1. Run `make lint`, `uv run pytest -q`, `uv run python scripts/dev/spec_coverage.py` (exit 0) and
   `make secrets-scan`.
2. Commit, push, open the PR and wait for the five checks: `gh pr checks <N> --watch`.
3. Squash-merge, then `git switch main && git pull --ff-only`.
4. Move the story to Done with the scratchpad's `thl_backlog.move("THL-<n>", "Done")`, using
   Roshan's own token. Refresh the saved Jira copy with `thl_jira_cache.py <repo>`.
5. `make dashboard`, then republish `docs/dashboard.html` to the dashboard artifact (its link is in
   the session memory, never in the repo).
6. Append to `docs/journal/YYYY-MM-DD.md`: what was built, what broke, hours, defects and tests.

## File map

| Path | Task | Responsibility |
|---|---|---|
| `pyproject.toml`, `uv.lock` | 1 | dependencies, packages, pytest importlib mode |
| `services/shared/thalam_shared/env.py` | 1 | a setting by name: environment first, then `.env` |
| `services/collector/thalam_collector/__init__.py` | 1 | the collector package |
| `compose.yaml` | 2 | Postgres only (R1) |
| `.env.example`, `Makefile` | 2, 3, 4, 8, 11 | placeholders; `db-up`, `db-down`, `migrate`, `db-roles`, `load`, `ask` |
| `.github/workflows/ci.yml` | 2, 3, 4 | Postgres service, migration steps, roles step |
| `services/shared/thalam_shared/lifecycle.py` | 3 | states, allowed moves, `Event`, current state and window |
| `services/shared/thalam_shared/db.py` | 3 | one engine per role |
| `services/shared/thalam_shared/models.py` | 3 | the seven tables |
| `alembic.ini`, `migrations/` | 3 | the schema (R2) |
| `services/conftest.py` | 3, 4, 7 | `migrated_engine`, `db`, `as_role`, `company_tree` |
| `scripts/ops/db-roles.sql`, `scripts/ops/db_roles.py` | 4 | the two roles and their grants (R3) |
| `services/shared/thalam_shared/graph.py` | 5 | the pure queries (R9–R11) |
| `services/collector/thalam_collector/problems.py` | 6 | `Problem`, `LoadError` |
| `services/collector/thalam_collector/catalog.py` | 6 | Backstage files to components (R4) |
| `services/collector/thalam_collector/company.py` | 7 | manifests, Jira files, calendar, checks, `to_graph` (R5, R6) |
| `services/collector/thalam_collector/load.py`, `__main__.py` | 8 | records to Postgres (R4, R6, R7) |
| `evals/company/` | 9 | the fixture company (R13) |
| `services/shared/thalam_shared/graph_read.py` | 10 | Postgres to `Graph` (R8) |
| `services/shared/thalam_shared/ask.py` | 11 | the CLI (R12) |
| `docs/labs/01-release-graph.md` and docs | 12 | Lab 01 (R15), ADR-0015, ROADMAP, overview, architecture, README |

---

### Task 0: Jira stories

**Files:** none in the repo; the scratchpad's `thl_jira.py` and `thl_backlog.py` (Roshan's own
token, never printed).

- [x] **Step 1: Create one story per task under THL-2, in task order.** Use labels `phase-1` and
      the area (`tooling`, `data`, `graph` or `docs`), and give each a "What" and a "Done when"
      taken from its task below:

| Task | Summary |
|---|---|
| 1 | Phase 1 packages: dependencies, the collector package, settings by name |
| 2 | Postgres in compose, the same image in CI (SPEC-002-R1) |
| 3 | The release-graph schema and the database test guard (SPEC-002-R2, R14) |
| 4 | Two database roles: a reader and a loader that cannot change history (SPEC-002-R3) |
| 5 | The graph queries: upstream, downstream, prod version, what must ship first, order (SPEC-002-R9..R11) |
| 6 | The Backstage catalog reader (SPEC-002-R4) |
| 7 | Release manifests, Jira files and the calendar (SPEC-002-R5, R6) |
| 8 | The loader: mirrors follow the files, history is written once (SPEC-002-R4, R6, R7) |
| 9 | The fixture company (SPEC-002-R13) |
| 10 | Read the graph from Postgres as the reader (SPEC-002-R8) |
| 11 | make ask: the release graph from the command line (SPEC-002-R12) |
| 12 | Lab 01 and the Phase 1 docs (SPEC-002-R15, ADR-0015) |

- [x] **Step 2: Record the keys** in this plan's task headings (`Task 1 · THL-<n>`), in a docs
      commit on the Task 1 branch.

---

### Task 1 · THL-28: Phase 1 packages, the collector package, settings by name

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `Makefile` (the `lint` target), `ROADMAP.md` (Phase 1)
- Create: `services/collector/thalam_collector/__init__.py`,
  `services/collector/thalam_collector/py.typed`, `services/shared/thalam_shared/env.py`
- Test: `services/shared/tests/test_env.py`

- [ ] **Step 1: Write the failing test** `services/shared/tests/test_env.py`:

```python
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
```

- [ ] **Step 2: Run it.** `uv run pytest services/shared/tests/test_env.py -q`. Expected: it fails
      with `ModuleNotFoundError: No module named 'thalam_shared.env'`.

- [ ] **Step 3: Write `services/shared/thalam_shared/env.py`:**

```python
"""Settings by name: the environment first, then .env, for that one name only (SPEC-002).

Thalam's Makefile never sources .env (scripts/ops/tf.py's rule): exporting all of it would hand
every Jira, ServiceNow and Foundry secret to every command. A caller asks for the names it needs.
Values are returned to the caller, never printed here.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class MissingSetting(KeyError):
    """The setting is in neither the environment nor .env; args[0] is its name."""


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


def setting(name: str, env_file: Path = ENV_FILE) -> str:
    if name in os.environ:
        return os.environ[name]
    try:
        values = _parse(env_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        values = {}
    if name in values:
        return values[name]
    raise MissingSetting(name)
```

- [ ] **Step 4: Change `pyproject.toml`.** Replace `dependencies = []` with:

```toml
dependencies = [
    "sqlalchemy>=2.1.9",
    "alembic>=1.20.1",
    "psycopg[binary]>=3.3.9",
    "pydantic>=2.14.4",
    "pyyaml>=6.0.4",
    "packaging>=26.3",
]
```

  Add `"types-pyyaml>=6.0.12.20261122",` to the `dev` extra. Set
  `packages = ["services/shared/thalam_shared", "services/collector/thalam_collector"]` under
  `[tool.hatch.build.targets.wheel]`. Add `plugins = ["pydantic.mypy"]` under `[tool.mypy]`. Under
  `[tool.pytest.ini_options]`, add:

```toml
# importlib: test files in different services may share a name (SPEC-002-R14). It no longer puts
# each test's folder on sys.path, so the script folders whose tests import their module by its
# bare name are listed here.
addopts = "--import-mode=importlib"
pythonpath = ["scripts/dev", "scripts/ops", "scripts/tracking"]
```

- [ ] **Step 5: Create the collector package.**
      `services/collector/thalam_collector/__init__.py` holds
      `"""Reads the release graph's sources into Postgres (SPEC-002-R4..R7)."""`, and `py.typed` is
      empty. In the Makefile's `lint` target, change the ruff line to
      `uv run ruff check services scripts infra migrations`. The `migrations/` folder exists but is
      empty, and ruff accepts that.

- [ ] **Step 6: Lock and sync.** Run `uv lock` and then `uv sync --all-extras`. Expected: the lock
      resolves the versions in the tech stack above or newer, and nothing older.

- [ ] **Step 7: Run everything.** `uv run pytest -q`. Expected: every test passes (296: the earlier
      292 plus 4). `make lint` is clean.

- [ ] **Step 8: ROADMAP's Phase 1.** Set its marker to `[~]` and replace its list with:

```markdown
[SPEC-002](docs/specs/SPEC-002-phase-1-release-graph.md) (THL-27); its shape is ADR-0015.

- [ ] Data model: `component`, `dependency`, `release`, `release_need`, `release_event`,
      `release_item`, `calendar_window`. Releases, needs and events are written once, and the
      database's grants enforce it
- [ ] Components and dependencies loaded from Backstage `catalog-info.yaml` files
- [ ] **A fixture company**: 8 services across 4 teams with a real dependency web
      (`web-shop → cart-api → pricing-svc → ledger-svc`), synthetic Jira data (`evals/company/`)
- [ ] Compose stack: Postgres + pgvector only. Ollama and Langfuse move to Phase 2, their first user
- [ ] Dependency queries: upstream / downstream / release order / what must ship first, and `make ask`
```

  In Phase 2, add these items:
  - "Compose gains Ollama and Langfuse (moved from Phase 1, ADR-0015)";
  - "`audit_event` table".

  In Phase 3, add "`proposal` → `decision` → `execution` → `outcome` tables". In Phase 4, add
  "`check`, `check_result` tables".

- [ ] **Step 9: Story close-out** (see "Before you start"). Commit subject:
      `feat: THL-<n> Phase 1 packages, the collector package and settings by name`.

---

### Task 2 · THL-29: Postgres in compose, the same image in CI (SPEC-002-R1)

**Files:**
- Create: `compose.yaml`, `scripts/dev/test_compose.py`
- Modify: `.github/workflows/ci.yml` (the `test` job), `.env.example`, `Makefile`

- [ ] **Step 1: Write the failing test** `scripts/dev/test_compose.py`:

```python
"""compose.yaml runs Postgres only: pinned, local-only, nothing built (SPEC-002-R1)."""
# covers: SPEC-002-R1

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PINNED = re.compile(r"^pgvector/pgvector:[\w.-]+@sha256:[0-9a-f]{64}$")


def _yaml(path: str) -> dict[str, Any]:
    data = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


COMPOSE = _yaml("compose.yaml")
POSTGRES = COMPOSE["services"]["postgres"]


def test_postgres_is_the_only_service() -> None:
    assert list(COMPOSE["services"]) == ["postgres"]


def test_the_image_is_pinned_by_digest() -> None:
    assert PINNED.match(POSTGRES["image"])


def test_nothing_is_built() -> None:
    assert all("build" not in service for service in COMPOSE["services"].values())


def test_the_port_listens_on_localhost_only() -> None:
    assert POSTGRES["ports"] == ["127.0.0.1:5432:5432"]


def test_every_credential_must_be_set() -> None:
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        assert POSTGRES["environment"][name].startswith("${" + name + ":?")


def test_ci_runs_the_same_image() -> None:
    ci = _yaml(".github/workflows/ci.yml")
    assert ci["jobs"]["test"]["services"]["postgres"]["image"] == POSTGRES["image"]
```

- [ ] **Step 2: Run it.** `uv run pytest scripts/dev/test_compose.py -q`. Expected: collection
      fails with `FileNotFoundError` for `compose.yaml`.

- [ ] **Step 3: Write `compose.yaml`:**

```yaml
# Thalam's Phase 1 stack: Postgres only (SPEC-002-R1, proved by scripts/dev/test_compose.py).
#
# Ollama and Langfuse join in Phase 2, their first user (ADR-0015). Nothing is built here, so
# CLAUDE.md rule 2 (arm64 images) is not touched: the image is a multi-arch index pinned by digest,
# the one Kaval runs and the one CI's test job uses. Compose reads .env itself for the ${...}
# values; `:?` refuses to start while one is unset. The port listens on 127.0.0.1 only.

name: thalam

services:
  postgres:
    image: pgvector/pgvector:0.8.7-pg16-bookworm@sha256:484e838076e04939d27d3e176e91c86eea96236126023be8d3059761122e579f
    environment:
      POSTGRES_DB: ${POSTGRES_DB:?set POSTGRES_DB in .env}
      POSTGRES_USER: ${POSTGRES_USER:?set POSTGRES_USER in .env}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 12
    stop_grace_period: 60s # time for a clean shutdown checkpoint
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Step 4: Give CI's `test` job the same Postgres.** In `.github/workflows/ci.yml`, insert
      this under `test:` after `timeout-minutes: 10`:

```yaml
    services:
      postgres:
        image: pgvector/pgvector:0.8.7-pg16-bookworm@sha256:484e838076e04939d27d3e176e91c86eea96236126023be8d3059761122e579f # the image compose.yaml runs (SPEC-002-R1)
        env:
          POSTGRES_DB: thalam
          POSTGRES_USER: thalam
          POSTGRES_PASSWORD: ci-only-not-a-secret
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U thalam -d thalam"
          --health-interval 5s --health-timeout 5s --health-retries 10
```

- [ ] **Step 5: `.env.example` and the Makefile.** In `.env.example`, set `POSTGRES_DB=thalam`
      and `POSTGRES_USER=thalam`, and keep `POSTGRES_PASSWORD=change-me`. Add to the Makefile:

```makefile
.PHONY: db-up
db-up: ## Start Postgres in Docker on 127.0.0.1 (SPEC-002-R1; compose reads .env)
	docker compose up -d --wait postgres

.PHONY: db-down
db-down: ## Stop Postgres; its data volume stays (docker compose down -v would drop it)
	docker compose down
```

- [ ] **Step 6: Run it.** `uv run pytest scripts/dev/test_compose.py -q`. Expected: 6 passed.
      Then `docker compose config --quiet`, which needs `.env` and prints nothing when the file is
      valid. Expected: exit 0.

- [ ] **Step 7: Story close-out.** Commit subject:
      `infra: THL-<n> Postgres in compose and the same image in CI (SPEC-002-R1)`.

---

### Task 3 · THL-30: The release-graph schema and the database test guard (SPEC-002-R2, R14)

**Files:**
- Create:
  - `services/shared/thalam_shared/lifecycle.py`, `db.py` and `models.py`;
  - `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako` and
    `migrations/versions/0001_release_graph.py`;
  - `services/conftest.py`.
- Test: `services/shared/tests/test_migrations.py`, `services/shared/tests/test_db_guard.py`
- Modify: `.github/workflows/ci.yml`, `.env.example`, `Makefile`

- [ ] **Step 1: Write `services/shared/thalam_shared/lifecycle.py`.** It is pure: the models
      import its state list, and Tasks 5, 7 and 10 use the rest.

```python
"""A release's life cycle (SPEC-002, "The life cycle"; docs/architecture/overview.md).

planned → scoped → ready → change_approved → deploying → verifying → released, one step at a
time; `cancelled` can follow planned, scoped, ready or change_approved; `rolled_back` can follow
deploying, verifying or released. A release's first event is `planned`, carrying its window; a
`replan` event moves the window. The current state and window are the latest of each.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

STATES = (
    "planned", "scoped", "ready", "change_approved", "deploying", "verifying", "released",
    "rolled_back", "cancelled",
)
_NEXT = dict(zip(STATES[:6], STATES[1:7], strict=True))  # planned→scoped … verifying→released
_CANCEL_FROM = frozenset({"planned", "scoped", "ready", "change_approved"})
_ROLL_BACK_FROM = frozenset({"deploying", "verifying", "released"})
NOT_IN_FLIGHT = frozenset({"released", "rolled_back", "cancelled"})


def allowed(previous: str | None, new: str) -> bool:
    """Whether a release in state `previous` (None: no event yet) may move to `new`."""
    if previous is None:
        return new == "planned"
    if new == "cancelled":
        return previous in _CANCEL_FROM
    if new == "rolled_back":
        return previous in _ROLL_BACK_FROM
    return _NEXT.get(previous) == new


@dataclass(frozen=True)
class Event:
    kind: str  # "state" or "replan"
    at: datetime  # timezone-aware
    state: str | None = None  # set when kind is "state"
    window: tuple[date, date] | None = None  # set on "planned" and on every "replan"


def current(events: Iterable[Event]) -> tuple[str, tuple[date, date]]:
    """The latest state and the latest window, whatever order the events arrive in."""
    state: str | None = None
    window: tuple[date, date] | None = None
    for event in sorted(events, key=lambda e: e.at):
        if event.kind == "state":
            state = event.state
        if event.window is not None:
            window = event.window
    if state is None or window is None:
        raise ValueError("a release needs a planned event with its window")
    return state, window
```

- [ ] **Step 2: Write `services/shared/thalam_shared/db.py`:**

```python
"""Connections to Thalam's Postgres, one engine per role (SPEC-002-R3).

owner   POSTGRES_USER: the migrations and scripts/ops/db-roles.sql.
loader  thalam_loader: `make load`.
reader  thalam_reader: `make ask`, and Phase 2's agent (CLAUDE.md rule 3).

SQLAlchemy's URL.create builds the address, so a password holding @ or / needs no escaping. The
URL is never printed: callers report "unreachable" in their own words.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from sqlalchemy import URL, Engine, create_engine

from thalam_shared.env import setting

Role = Literal["owner", "loader", "reader"]
_APP_ROLES = {
    "loader": ("thalam_loader", "THALAM_LOADER_PASSWORD"),
    "reader": ("thalam_reader", "THALAM_READER_PASSWORD"),
}


def database_url(role: Role) -> URL:
    if role == "owner":
        user, password = setting("POSTGRES_USER"), setting("POSTGRES_PASSWORD")
    else:
        user, key = _APP_ROLES[role]
        password = setting(key)
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=setting("POSTGRES_HOST"),
        port=int(setting("POSTGRES_PORT")),
        database=setting("POSTGRES_DB"),
    )


@lru_cache
def engine(role: Role) -> Engine:
    # A bounded connect_timeout: without one, a Postgres that is down hangs for minutes (Kaval).
    return create_engine(
        database_url(role), pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )
```

- [ ] **Step 3: Write `services/shared/thalam_shared/models.py`:**

```python
"""The release graph's seven tables (SPEC-002-R2).

Two kinds, and scripts/ops/db-roles.sql holds each to its kind with grants (R3):
- mirrors of a source file: component, dependency, release_item, calendar_window. The loader
  makes them match the files on every load; a component that leaves the catalog is retired, never
  deleted, so its old releases keep their link.
- written once: release, release_need, release_event. Nothing UPDATEs or DELETEs them; a state
  change or a re-plan is a new release_event row (Kaval's append-only spine, ADR-0002).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    MetaData,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from thalam_shared.lifecycle import STATES, Event

STATE_LIST = ", ".join(f"'{s}'" for s in STATES)
NAMES = {
    "pk": "pk_%(table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMES)


class Component(Base):
    __tablename__ = "component"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    owner: Mapped[str] = mapped_column(Text)  # a Backstage Group's name
    type: Mapped[str] = mapped_column(Text)
    lifecycle: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)  # untrusted text, capped; never printed
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dependency(Base):
    __tablename__ = "dependency"
    __table_args__ = (CheckConstraint("src_id <> dst_id", name="not_self"),)
    src_id: Mapped[int] = mapped_column(ForeignKey("component.id"), primary_key=True)
    dst_id: Mapped[int] = mapped_column(ForeignKey("component.id"), primary_key=True)


class Release(Base):
    __tablename__ = "release"
    __table_args__ = (
        UniqueConstraint("component_id", "version"),
        CheckConstraint(r"version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'", name="version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("component.id"))
    version: Mapped[str] = mapped_column(Text)
    jira_version_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReleaseNeed(Base):
    __tablename__ = "release_need"
    __table_args__ = (UniqueConstraint("release_id", "component_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("release.id"))
    component_id: Mapped[int] = mapped_column(ForeignKey("component.id"))
    spec: Mapped[str] = mapped_column(Text)  # a version range such as ">=1.8.0,<2"


class ReleaseEvent(Base):
    __tablename__ = "release_event"
    __table_args__ = (
        UniqueConstraint("release_id", "kind", "at"),
        CheckConstraint("kind IN ('state', 'replan')", name="kind"),
        CheckConstraint(f"state IS NULL OR state IN ({STATE_LIST})", name="state"),
        CheckConstraint(
            "(kind = 'state' AND state IS NOT NULL"
            " AND (state = 'planned') = (window_start IS NOT NULL))"
            " OR (kind = 'replan' AND state IS NULL AND window_start IS NOT NULL)",
            name="shape",
        ),
        CheckConstraint(
            "(window_start IS NULL) = (window_end IS NULL)"
            " AND (window_end IS NULL OR window_end >= window_start)",
            name="window",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("release.id"))
    kind: Mapped[str] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def as_event(self) -> Event:
        window = None
        if self.window_start is not None and self.window_end is not None:
            window = (self.window_start, self.window_end)
        return Event(self.kind, self.at, self.state, window)

    @classmethod
    def from_event(cls, release_id: int, event: Event) -> ReleaseEvent:
        start, end = event.window if event.window is not None else (None, None)
        return cls(release_id=release_id, kind=event.kind, state=event.state,
                   window_start=start, window_end=end, at=event.at)


class ReleaseItem(Base):
    __tablename__ = "release_item"
    __table_args__ = (UniqueConstraint("release_id", "jira_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("release.id"))
    jira_key: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)  # untrusted text, capped at 255; never printed
    status: Mapped[str] = mapped_column(Text)


class CalendarWindow(Base):
    __tablename__ = "calendar_window"
    __table_args__ = (
        CheckConstraint("kind IN ('freeze', 'blackout')", name="kind"),
        CheckConstraint("ends >= starts", name="order"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    starts: Mapped[date] = mapped_column(Date)
    ends: Mapped[date] = mapped_column(Date)
```

- [ ] **Step 4: Write `alembic.ini`.** It sits at the top level because Alembic looks for it
      there.

```ini
# Alembic (SPEC-002-R2). The database address is not here: migrations/env.py builds it from
# POSTGRES_* (the environment, then .env) as the owner role.
[alembic]
script_location = %(here)s/migrations
prepend_sys_path = .
path_separator = os
```

- [ ] **Step 5: Write `migrations/env.py`:**

```python
"""Alembic's entry point (SPEC-002-R2): online only, as the owner role."""

from __future__ import annotations

import logging

from alembic import context
from thalam_shared.db import engine
from thalam_shared.models import Base

logging.basicConfig(format="%(levelname)-5.5s [%(name)s] %(message)s", level=logging.WARNING)
logging.getLogger("alembic").setLevel(logging.INFO)

if context.is_offline_mode():
    raise SystemExit("offline (--sql) migrations are not used; run them against a database")

with engine("owner").connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
```

  Also write `migrations/script.py.mako` (used only by `alembic revision`):

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Write `migrations/versions/0001_release_graph.py`:**

```python
"""The release graph: seven tables (SPEC-002-R2).

Revision ID: 0001
Revises: none
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATES = (
    "'planned', 'scoped', 'ready', 'change_approved', 'deploying', 'verifying', 'released', "
    "'rolled_back', 'cancelled'"
)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "component",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("lifecycle", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("retired_at", TZ, nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component")),
        sa.UniqueConstraint("name", name=op.f("uq_component_name")),
    )
    op.create_table(
        "dependency",
        sa.Column("src_id", sa.Integer(), nullable=False),
        sa.Column("dst_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("src_id <> dst_id", name=op.f("ck_dependency_not_self")),
        sa.ForeignKeyConstraint(["src_id"], ["component.id"],
                                name=op.f("fk_dependency_src_id_component")),
        sa.ForeignKeyConstraint(["dst_id"], ["component.id"],
                                name=op.f("fk_dependency_dst_id_component")),
        sa.PrimaryKeyConstraint("src_id", "dst_id", name=op.f("pk_dependency")),
    )
    op.create_table(
        "release",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("jira_version_id", sa.Text(), nullable=True),
        sa.Column("created_at", TZ, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(r"version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'",
                           name=op.f("ck_release_version")),
        sa.ForeignKeyConstraint(["component_id"], ["component.id"],
                                name=op.f("fk_release_component_id_component")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release")),
        sa.UniqueConstraint("component_id", "version",
                            name=op.f("uq_release_component_id_version")),
    )
    op.create_table(
        "release_need",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("spec", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["release.id"],
                                name=op.f("fk_release_need_release_id_release")),
        sa.ForeignKeyConstraint(["component_id"], ["component.id"],
                                name=op.f("fk_release_need_component_id_component")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_need")),
        sa.UniqueConstraint("release_id", "component_id",
                            name=op.f("uq_release_need_release_id_component_id")),
    )
    op.create_table(
        "release_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("at", TZ, nullable=False),
        sa.CheckConstraint("kind IN ('state', 'replan')", name=op.f("ck_release_event_kind")),
        sa.CheckConstraint(f"state IS NULL OR state IN ({STATES})",
                           name=op.f("ck_release_event_state")),
        sa.CheckConstraint(
            "(kind = 'state' AND state IS NOT NULL"
            " AND (state = 'planned') = (window_start IS NOT NULL))"
            " OR (kind = 'replan' AND state IS NULL AND window_start IS NOT NULL)",
            name=op.f("ck_release_event_shape"),
        ),
        sa.CheckConstraint(
            "(window_start IS NULL) = (window_end IS NULL)"
            " AND (window_end IS NULL OR window_end >= window_start)",
            name=op.f("ck_release_event_window"),
        ),
        sa.ForeignKeyConstraint(["release_id"], ["release.id"],
                                name=op.f("fk_release_event_release_id_release")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_event")),
        sa.UniqueConstraint("release_id", "kind", "at",
                            name=op.f("uq_release_event_release_id_kind_at")),
    )
    op.create_table(
        "release_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("jira_key", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["release.id"],
                                name=op.f("fk_release_item_release_id_release")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_item")),
        sa.UniqueConstraint("release_id", "jira_key",
                            name=op.f("uq_release_item_release_id_jira_key")),
    )
    op.create_table(
        "calendar_window",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("starts", sa.Date(), nullable=False),
        sa.Column("ends", sa.Date(), nullable=False),
        sa.CheckConstraint("kind IN ('freeze', 'blackout')",
                           name=op.f("ck_calendar_window_kind")),
        sa.CheckConstraint("ends >= starts", name=op.f("ck_calendar_window_order")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_window")),
        sa.UniqueConstraint("name", name=op.f("uq_calendar_window_name")),
    )


def downgrade() -> None:
    for table in ("calendar_window", "release_item", "release_event", "release_need",
                  "release", "dependency", "component"):
        op.drop_table(table)
```

- [ ] **Step 7: Write `services/conftest.py`.** This is the only `conftest.py` in the repo.

```python
"""Fixtures for every service's tests (SPEC-002-R14). Copied from Kaval's services/conftest.py.

A test that needs Postgres asks for `db`: the owner role, inside one transaction that is rolled
back at the end, so nothing persists. Without a reachable, migrated database the test skips and
says why; CI sets THALAM_REQUIRE_DB=1, which turns that skip into a failure, so a database test can
never vanish from a green run (Kaval KAV-24).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import NoReturn

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from thalam_shared.db import engine
from thalam_shared.env import MissingSetting
from thalam_shared.models import Base

REQUIRE = "THALAM_REQUIRE_DB"


def no_database(reason: str) -> NoReturn:
    if os.environ.get(REQUIRE) == "1":
        pytest.fail(f"{reason} ({REQUIRE}=1, so this fails rather than skips)", pytrace=False)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def migrated_engine() -> Engine:
    """Probed once per run: with nothing listening, Windows takes ~10 s to refuse `localhost`."""
    try:
        owner = engine("owner")
        with owner.connect() as probe:
            probe.execute(text("SELECT version_num FROM alembic_version"))
    except (DBAPIError, MissingSetting) as exc:
        no_database(f"no reachable, migrated Postgres: {type(exc).__name__}")
    return owner


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Session]:
    """One test, one outer transaction, rolled back at teardown. The code under test's own
    commits become SAVEPOINTs (`join_transaction_mode`), so nothing persists either way.

    Every test starts from empty tables: the TRUNCATE runs inside the same transaction and is
    rolled back with it. A database that holds Lab 01's data still passes and keeps that data
    (the plan's dry run found tests failing after a real `make load`)."""
    connection = migrated_engine.connect()
    transaction = connection.begin()
    try:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
    finally:
        transaction.rollback()
        connection.close()
```

- [ ] **Step 8: Write the failing tests.** First `services/shared/tests/test_migrations.py`:

```python
"""The migrations create the release graph and match the models (SPEC-002-R2).

CI also runs upgrade → `alembic check` → downgrade → upgrade as steps of its own, outside pytest,
so a downgrade never pulls the schema out from under another test (Kaval found that collision).
"""
# covers: SPEC-002-R2

from __future__ import annotations

import re
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect
from thalam_shared.models import Base

ROOT = Path(__file__).resolve().parents[3]
TABLES = {"component", "dependency", "release", "release_need", "release_event", "release_item",
          "calendar_window"}


def test_the_seven_tables_and_nothing_else(migrated_engine: Engine) -> None:
    assert set(inspect(migrated_engine).get_table_names()) == TABLES | {"alembic_version"}


def test_the_models_and_the_migrations_agree(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_every_migration_can_be_reversed() -> None:
    for path in sorted((ROOT / "migrations" / "versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert re.search(r"def downgrade\(\) -> None:\n(?!\s+pass\b)", text), path.name
```

  Then `services/shared/tests/test_db_guard.py`:

```python
"""A database test never vanishes from CI (SPEC-002-R14).

Runs a real database test in a child pytest pointed at a closed port: without THALAM_REQUIRE_DB
it skips and says why; with THALAM_REQUIRE_DB=1 (as in CI) it fails.
"""
# covers: SPEC-002-R14

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = "services/shared/tests/test_migrations.py::test_the_seven_tables_and_nothing_else"


def _run(require: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "9", "POSTGRES_DB": "x",
           "POSTGRES_USER": "x", "POSTGRES_PASSWORD": "x", "THALAM_REQUIRE_DB": require}
    return subprocess.run(
        [sys.executable, "-m", "pytest", TARGET, "-q", "-p", "no:cacheprovider", "-rs"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
    )


def test_without_the_flag_a_database_test_skips_and_says_why() -> None:
    result = _run("0")
    assert result.returncode == 0, result.stdout
    assert "no reachable, migrated Postgres" in result.stdout


def test_with_the_flag_a_database_test_fails() -> None:
    result = _run("1")
    assert result.returncode == 1, result.stdout
    assert "THALAM_REQUIRE_DB=1, so this fails rather than skips" in result.stdout
```

- [ ] **Step 9: Run them with no database.** Stop Postgres with `make db-down` if it is running,
      then `uv run pytest services/shared/tests -q -rs`. Expected: the 3 migration tests are
      skipped with "no reachable, migrated Postgres", and the 2 guard tests pass.

- [ ] **Step 10: Run them on a real database.** Run `make db-up` and then
      `uv run alembic upgrade head`. Expected: `Running upgrade  -> 0001`. Then run
      `uv run alembic check` (expected: `No new upgrade operations detected.`) and
      `uv run alembic downgrade base && uv run alembic upgrade head`. Then
      `uv run pytest services/shared/tests -q`. Expected: everything passes.

- [ ] **Step 11: CI runs the migrations and refuses skips.** In `.github/workflows/ci.yml`:
  - Add `# covers: SPEC-002-R2, SPEC-002-R14` to the header, under the existing tag line.
  - Under the `test` job's `services:` block, add:

```yaml
    env:
      POSTGRES_HOST: localhost
      POSTGRES_PORT: "5432"
      POSTGRES_DB: thalam
      POSTGRES_USER: thalam
      POSTGRES_PASSWORD: ci-only-not-a-secret
      THALAM_REQUIRE_DB: "1" # a database test that cannot connect fails here, never skips (SPEC-002-R14)
```

  - Between `uv sync --locked --all-extras` and `uv run pytest -ra`, add:

```yaml
      - name: migrations apply from empty
        run: uv run alembic upgrade head
      - name: models and migrations agree (no drift)
        run: uv run alembic check
      - name: migrations reverse cleanly, then re-apply
        run: uv run alembic downgrade base && uv run alembic upgrade head
```

- [ ] **Step 12: The Makefile target:**

```makefile
.PHONY: migrate
migrate: ## Apply the migrations as the owner, then run `make db-roles` (SPEC-002-R2)
	uv run alembic upgrade head
```

- [ ] **Step 13: Story close-out.** Commit subject:
      `feat: THL-<n> the release-graph schema and the database test guard (SPEC-002-R2, R14)`.

---

### Task 4 · THL-31: Two database roles (SPEC-002-R3)

**Files:**
- Create: `scripts/ops/db-roles.sql`, `scripts/ops/db_roles.py`
- Modify: `services/conftest.py` (adds `as_role`), `.github/workflows/ci.yml`, `.env.example`,
  `Makefile`
- Test: `services/shared/tests/test_db_roles.py`

- [ ] **Step 1: Write `scripts/ops/db-roles.sql`:**

```sql
-- Thalam's two application roles (SPEC-002-R3): Kaval's split, one layer down (CLAUDE.md rule 3).
-- covers: SPEC-002-R3
--
-- thalam_reader  SELECT only. `make ask` uses it, and Phase 2's agent inherits it.
-- thalam_loader  writes the mirror tables, and may only INSERT into the written-once ones, so the
--                code that loads history cannot change it (thalam_shared/models.py: two kinds).
--
-- Plain SQL, run as the owner by scripts/ops/db_roles.py after every `make migrate` (a GRANT on
-- ALL TABLES reaches only the tables that exist). The passwords arrive as transaction settings the
-- runner sets with bound parameters, and nothing here prints them. Kaval learned both halves:
-- psql's :'var' does not reach inside DO $$ (KAV-56), and a bare SELECT of a password prints it
-- (KAV-125). Safe to repeat: passwords and grants are set again.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thalam_loader') THEN
    EXECUTE format('CREATE ROLE thalam_loader LOGIN PASSWORD %L',
                   current_setting('thalam.loader_password'));
  ELSE
    EXECUTE format('ALTER ROLE thalam_loader LOGIN PASSWORD %L',
                   current_setting('thalam.loader_password'));
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thalam_reader') THEN
    EXECUTE format('CREATE ROLE thalam_reader LOGIN PASSWORD %L',
                   current_setting('thalam.reader_password'));
  ELSE
    EXECUTE format('ALTER ROLE thalam_reader LOGIN PASSWORD %L',
                   current_setting('thalam.reader_password'));
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO thalam_loader, thalam_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM thalam_loader, thalam_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO thalam_reader;

-- Mirrors: made to match the files. A component is retired, never deleted, so no DELETE on it.
GRANT SELECT, INSERT, UPDATE ON component TO thalam_loader;
GRANT SELECT, INSERT, DELETE ON dependency TO thalam_loader;
GRANT SELECT, INSERT, UPDATE, DELETE ON release_item, calendar_window TO thalam_loader;
-- Written once: INSERT, never UPDATE or DELETE.
GRANT SELECT, INSERT ON release, release_need, release_event TO thalam_loader;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO thalam_loader;
```

- [ ] **Step 2: Write `scripts/ops/db_roles.py`:**

```python
#!/usr/bin/env python3
"""Create or update thalam_loader and thalam_reader (SPEC-002-R3): `make db-roles`.

Runs scripts/ops/db-roles.sql as the owner. THALAM_LOADER_PASSWORD and THALAM_READER_PASSWORD
come from the environment, then .env; they are passed as bound parameters and never printed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import Connection, text
from sqlalchemy.exc import OperationalError
from thalam_shared.db import engine
from thalam_shared.env import MissingSetting, setting

SQL = Path(__file__).with_name("db-roles.sql")


def apply(connection: Connection, loader_password: str, reader_password: str) -> None:
    """Run the roles script inside the caller's transaction (tests roll it back)."""
    for name, value in (("loader", loader_password), ("reader", reader_password)):
        # is_local=true: the setting lasts for this transaction only.
        connection.execute(text(f"SELECT set_config('thalam.{name}_password', :v, true)"),
                           {"v": value})
    raw = connection.connection.driver_connection
    assert raw is not None
    # No parameters, so psycopg sends the script as is: several statements, % signs untouched.
    raw.cursor().execute(SQL.read_text(encoding="utf-8"))


def main() -> int:
    try:
        loader = setting("THALAM_LOADER_PASSWORD")
        reader = setting("THALAM_READER_PASSWORD")
        owner = engine("owner")
        with owner.begin() as connection:
            apply(connection, loader, reader)
    except MissingSetting as exc:
        print(f"set {exc.args[0]} in .env (see .env.example)", file=sys.stderr)
        return 2
    except OperationalError:
        print("Postgres is not reachable: run `make db-up`, then `make migrate`", file=sys.stderr)
        return 1
    print("roles ready: thalam_loader, thalam_reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Add `as_role` to `services/conftest.py`.** Add `import db_roles` to its imports
      (it is on pytest's `pythonpath` and in mypy's run, both through `scripts/ops`), then append:

```python
ROLES = ("thalam_loader", "thalam_reader")


@pytest.fixture
def as_role(db: Session) -> Callable[[str | None], Session]:
    """The real roles script, applied inside the test's transaction (rolled back with it); then
    `as_role("thalam_reader")` acts as that role until `as_role(None)` returns to the owner."""
    db_roles.apply(db.connection(), "test-loader", "test-reader")

    def switch(role: str | None) -> Session:
        assert role is None or role in ROLES
        db.execute(text("RESET ROLE" if role is None else f"SET LOCAL ROLE {role}"))
        return db

    return switch
```

  Also add `from collections.abc import Callable, Iterator` to the conftest's imports.

- [ ] **Step 4: Write the failing test** `services/shared/tests/test_db_roles.py`:

```python
"""What thalam_loader and thalam_reader may and may not do (SPEC-002-R3).

Runs the real scripts/ops/db-roles.sql inside the test's rolled-back transaction, then acts as each
role. Kaval's lesson (KAV-82): a role that cannot do what its code does is found only by running
the real script.
"""
# covers: SPEC-002-R3

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import db_roles
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from thalam_shared import models

Switch = Callable[[str | None], Session]
COLUMN = {"component": "name", "dependency": "src_id", "release": "version",
          "release_need": "spec", "release_event": "kind", "release_item": "summary",
          "calendar_window": "name"}
WRITTEN_ONCE = ("release", "release_need", "release_event")


def _seed(db: Session) -> int:
    a = models.Component(name="a", owner="t", type="service", lifecycle="production",
                         description="")
    b = models.Component(name="b", owner="t", type="service", lifecycle="production",
                         description="")
    db.add_all([a, b])
    db.flush()
    db.add(models.Dependency(src_id=a.id, dst_id=b.id))
    release = models.Release(component_id=a.id, version="1.0.0")
    db.add(release)
    db.flush()
    db.add_all([
        models.ReleaseNeed(release_id=release.id, component_id=b.id, spec=">=1.0.0"),
        models.ReleaseEvent(release_id=release.id, kind="state", state="planned",
                            window_start=date(2026, 12, 1), window_end=date(2026, 12, 1),
                            at=datetime(2026, 11, 1, tzinfo=UTC)),
        models.ReleaseItem(release_id=release.id, jira_key="A-1", summary="s", status="To Do"),
        models.CalendarWindow(name="w", kind="freeze", starts=date(2026, 12, 19),
                              ends=date(2027, 1, 4)),
    ])
    db.flush()
    return release.id


def _may(db: Session, as_role: Switch, role: str, sql: str) -> bool:
    try:
        with db.begin_nested():
            as_role(role)
            db.execute(text(sql))
        return True
    except ProgrammingError as exc:
        assert getattr(exc.orig, "sqlstate", None) == "42501", exc  # insufficient_privilege
        return False
    finally:
        as_role(None)


def _statements(table: str) -> dict[str, str]:
    column = COLUMN[table]
    return {"insert": f"INSERT INTO {table} DEFAULT VALUES",
            "update": f"UPDATE {table} SET {column} = {column}",
            "delete": f"DELETE FROM {table}"}


@pytest.mark.parametrize("table", sorted(COLUMN))
def test_the_reader_reads_every_table_and_writes_none(as_role: Switch, table: str) -> None:
    db = as_role(None)
    _seed(db)
    assert _may(db, as_role, "thalam_reader", f"SELECT count(*) FROM {table}")
    for kind, sql in _statements(table).items():
        assert not _may(db, as_role, "thalam_reader", sql), (table, kind)


@pytest.mark.parametrize("table", WRITTEN_ONCE)
def test_the_loader_cannot_change_history(as_role: Switch, table: str) -> None:
    db = as_role(None)
    _seed(db)
    statements = _statements(table)
    assert not _may(db, as_role, "thalam_loader", statements["update"]), table
    assert not _may(db, as_role, "thalam_loader", statements["delete"]), table


def test_the_loader_appends_an_event(as_role: Switch) -> None:
    db = as_role(None)
    release_id = _seed(db)
    sql = ("INSERT INTO release_event (release_id, kind, state, at) "
           f"VALUES ({release_id}, 'state', 'scoped', '2026-11-02T00:00:00Z')")
    assert _may(db, as_role, "thalam_loader", sql)


def test_the_loader_keeps_the_mirrors_but_never_deletes_a_component(as_role: Switch) -> None:
    db = as_role(None)
    _seed(db)
    for sql in ("UPDATE component SET retired_at = now()", "DELETE FROM dependency",
                "UPDATE release_item SET status = 'Done'", "DELETE FROM release_item",
                "DELETE FROM calendar_window"):
        assert _may(db, as_role, "thalam_loader", sql), sql
    assert not _may(db, as_role, "thalam_loader", "DELETE FROM component")


def test_the_script_can_run_twice(as_role: Switch) -> None:
    db = as_role(None)
    db_roles.apply(db.connection(), "again-loader", "again-reader")
```

- [ ] **Step 5: Run it.** `uv run pytest services/shared/tests/test_db_roles.py -q`, with the
      database from Task 3 up. Expected: before Step 1 exists, it fails with `FileNotFoundError`.
      With Steps 1 to 3 in place, 13 pass: 7 reader tables, 3 written-once tables and 3 single
      tests.

- [ ] **Step 6: Wire it up.**
  - **`.env.example`:** under the `POSTGRES_*` lines, add:

```
THALAM_LOADER_PASSWORD=change-me   # thalam_loader: `make load` (SPEC-002-R3)
THALAM_READER_PASSWORD=change-me   # thalam_reader: `make ask`, and Phase 2's agent
```

  - **Makefile:**

```makefile
.PHONY: db-roles
db-roles: ## Create or update thalam_loader and thalam_reader, after every migrate (SPEC-002-R3)
	uv run python scripts/ops/db_roles.py
```

  - **CI's `test` job:** add `THALAM_LOADER_PASSWORD: ci-only-loader` and
    `THALAM_READER_PASSWORD: ci-only-reader` to its `env`. After the migration steps, add:

```yaml
      - name: database roles (SPEC-002-R3)
        run: uv run python scripts/ops/db_roles.py
```

- [ ] **Step 7: Live check.** Run `make db-roles`. Expected: `roles ready: thalam_loader,
      thalam_reader`, with no password in the output.

- [ ] **Step 8: Story close-out.** Commit subject:
      `feat: THL-<n> a reader and a loader that cannot change history (SPEC-002-R3)`.

---

### Task 5 · THL-32: The graph queries (SPEC-002-R9, R10, R11)

**Files:**
- Create: `services/shared/thalam_shared/graph.py`
- Test: `services/shared/tests/test_graph.py`

- [ ] **Step 1: Write the failing test** `services/shared/tests/test_graph.py`:

```python
"""The release graph's queries, on graphs built by hand (SPEC-002-R9, R10, R11). No database."""
# covers: SPEC-002-R9, SPEC-002-R10, SPEC-002-R11

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pytest
from thalam_shared.graph import (
    Component,
    Graph,
    GraphError,
    Need,
    Release,
    Step,
    UnknownName,
    downstream,
    make_graph,
    must_ship_before,
    parse_range,
    parse_version,
    prod_version,
    release_order,
    upstream,
)

DAY = (date(2026, 12, 1), date(2026, 12, 1))


def rel(component: str, version: str, state: str = "planned",
        needs: Iterable[tuple[str, str]] = ()) -> Release:
    return Release(component, version, state, DAY, tuple(Need(c, s) for c, s in needs))


def graph_of(edges: Iterable[tuple[str, str]], releases: Iterable[Release],
             retired: Iterable[str] = ()) -> Graph:
    edges, releases, gone = list(edges), list(releases), set(retired)
    names = {n for edge in edges for n in edge} | {r.component for r in releases}
    return make_graph([Component(n, "team", n in gone) for n in names], edges, releases)


# The gate (SPEC-002-R13's first scenario), in miniature.
GATE = graph_of(
    [("cart-api", "pricing-svc"), ("cart-api", "catalog-svc"), ("pricing-svc", "ledger-svc")],
    [
        rel("catalog-svc", "2.5.0", "released"),
        rel("ledger-svc", "4.2.0", "released"),
        rel("ledger-svc", "4.3.0"),
        rel("pricing-svc", "1.7.0", "released"),
        rel("pricing-svc", "1.8.0", "scoped", [("ledger-svc", ">=4.1.0")]),
        rel("cart-api", "2.3.0", needs=[("pricing-svc", ">=1.8.0"), ("catalog-svc", ">=2.5.0")]),
    ],
)


def labels(steps: Iterable[Step]) -> list[str]:
    return [step.release.label for step in steps]


def test_upstream_and_downstream_are_transitive() -> None:
    assert upstream(GATE, "cart-api") == ["catalog-svc", "ledger-svc", "pricing-svc"]
    assert downstream(GATE, "ledger-svc") == ["cart-api", "pricing-svc"]
    assert upstream(GATE, "ledger-svc") == []


def test_an_unknown_component_is_named() -> None:
    with pytest.raises(UnknownName, match="no component named 'nope'"):
        upstream(GATE, "nope")


def test_prod_version_is_the_highest_released() -> None:
    g = graph_of([], [rel("a", "1.0.0", "released"), rel("a", "1.2.0", "released"),
                      rel("a", "1.3.0", "rolled_back"), rel("a", "1.4.0", "cancelled"),
                      rel("a", "1.5.0", "deploying"), rel("b", "1.0.0")])
    assert prod_version(g, "a") == "1.2.0"
    assert prod_version(g, "b") is None


def test_the_gate() -> None:
    answer = must_ship_before(GATE, "cart-api", "2.3")
    assert labels(answer.steps) == ["pricing-svc 1.8.0"]
    assert answer.steps[0].prod == "1.7.0"
    assert answer.steps[0].needed_by == "cart-api 2.3.0"
    assert [(s.need.component, s.prod) for s in answer.satisfied] == [
        ("catalog-svc", "2.5.0"), ("ledger-svc", "4.2.0")]
    assert answer.blockers == ()


def test_a_chain_comes_upstream_first_with_ties_in_name_order() -> None:
    g = graph_of([], [
        rel("pricing-svc", "1.8.0"),
        rel("payments-gw", "3.2.1"),
        rel("cart-api", "2.3.0", needs=[("pricing-svc", ">=1.8.0")]),
        rel("checkout-svc", "3.0.0", needs=[("cart-api", ">=2.3.0"), ("payments-gw", ">=3.2.0")]),
    ])
    answer = must_ship_before(g, "checkout-svc", "3.0.0")
    assert labels(answer.steps) == ["payments-gw 3.2.1", "pricing-svc 1.8.0", "cart-api 2.3.0"]


def test_the_lowest_satisfying_release_in_flight_is_chosen() -> None:
    g = graph_of([], [rel("b", "1.9.0"), rel("b", "1.8.0"), rel("b", "2.0.0", "cancelled"),
                      rel("a", "1.0.0", needs=[("b", ">=1.8.0")])])
    assert labels(must_ship_before(g, "a", "1.0.0").steps) == ["b 1.8.0"]


def test_a_need_nothing_meets_is_a_blocker() -> None:
    g = graph_of([], [rel("b", "2.0.0", "released"), rel("b", "3.0.0", "rolled_back"),
                      rel("a", "1.0.0", needs=[("b", ">=3.0.0")])])
    answer = must_ship_before(g, "a", "1.0.0")
    assert answer.steps == ()
    assert [(b.need.component, b.reason) for b in answer.blockers] == [
        ("b", "no release satisfies it")]


def test_a_need_on_a_retired_component_is_a_blocker() -> None:
    g = graph_of([], [rel("b", "2.0.0", "released"), rel("a", "1.0.0", needs=[("b", ">=1.0.0")])],
                 retired=["b"])
    assert [b.reason for b in must_ship_before(g, "a", "1.0.0").blockers] == ["b is retired"]


def test_a_loop_is_an_error_that_names_every_release_in_it() -> None:
    g = graph_of([], [rel("a", "1.0.0", needs=[("b", ">=1.0.0")]),
                      rel("b", "1.0.0", needs=[("a", ">=1.0.0")])])
    with pytest.raises(GraphError) as caught:
        must_ship_before(g, "a", "1.0.0")
    assert "a 1.0.0" in str(caught.value) and "b 1.0.0" in str(caught.value)


def test_release_order_puts_every_release_after_what_it_needs() -> None:
    order = [r.label for r in release_order(GATE)]
    assert order == ["ledger-svc 4.3.0", "pricing-svc 1.8.0", "cart-api 2.3.0"]


def test_release_order_refuses_a_loop() -> None:
    g = graph_of([], [rel("a", "1.0.0", needs=[("b", ">=1.0.0")]),
                      rel("b", "1.0.0", needs=[("a", ">=1.0.0")])])
    with pytest.raises(GraphError):
        release_order(g)


def test_versions_and_ranges() -> None:
    assert parse_version("2.3") == "2.3.0"
    assert parse_version("2.3.1") == "2.3.1"
    for bad in ("v2", "2", "2.3.1.4", ""):
        with pytest.raises(ValueError):
            parse_version(bad)
    assert parse_range(">=1.8.0,<2")
    for bad in ("~=1.0", "==1.*", "===1.0", "", "soon"):
        with pytest.raises(ValueError):
            parse_range(bad)
```

- [ ] **Step 2: Run it.** `uv run pytest services/shared/tests/test_graph.py -q`. Expected: it
      fails with `ModuleNotFoundError: No module named 'thalam_shared.graph'`.

- [ ] **Step 3: Write `services/shared/thalam_shared/graph.py`:**

```python
"""The release graph's queries (SPEC-002-R9, R10, R11): pure functions over one snapshot.

Nothing here touches a database or a model. thalam_shared.graph_read builds a Graph from Postgres
and thalam_collector.company builds one from the fixture files; the same functions answer both, so
the logic is proved without Postgres and the read is proved on its own (R8).

A Graph holds no free text (no description, no summary), so nothing printed from it can carry a
planted terminal escape.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from graphlib import CycleError, TopologicalSorter

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from thalam_shared.lifecycle import NOT_IN_FLIGHT

VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")
OPERATORS = frozenset({"==", "!=", "<=", ">=", "<", ">"})


class GraphError(Exception):
    """The needs form a loop, so no order exists."""


class UnknownName(LookupError):
    """A component or a release the graph does not hold."""


def parse_version(text: str) -> str:
    """'2.3' or '2.3.0' -> '2.3.0'. Anything else is a ValueError."""
    match = VERSION.match(text.strip())
    if not match:
        raise ValueError(f"not a version: {text!r} (expected X.Y.Z)")
    return f"{int(match[1])}.{int(match[2])}.{int(match[3] or 0)}"


def parse_range(text: str) -> SpecifierSet:
    """'>=1.8.0,<2', comparison operators only: no '~=', no '===', no wildcards."""
    try:
        spec = SpecifierSet(text)
    except InvalidSpecifier:
        raise ValueError(f"not a version range: {text!r}") from None
    if not text.strip() or any(s.operator not in OPERATORS or "*" in s.version for s in spec):
        raise ValueError(f"not a version range: {text!r} (use >=, >, <=, <, == or !=)")
    return spec


@dataclass(frozen=True)
class Component:
    name: str
    owner: str
    retired: bool = False


@dataclass(frozen=True)
class Need:
    component: str
    spec: str  # a version range


@dataclass(frozen=True)
class Release:
    component: str
    version: str  # X.Y.Z
    state: str  # the current state (thalam_shared.lifecycle)
    window: tuple[date, date]  # the current window
    needs: tuple[Need, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.component} {self.version}"

    @property
    def in_flight(self) -> bool:
        return self.state not in NOT_IN_FLIGHT


@dataclass(frozen=True)
class Window:
    name: str
    kind: str  # freeze | blackout
    starts: date
    ends: date


@dataclass(frozen=True)
class Graph:
    components: Mapping[str, Component]
    depends_on: Mapping[str, frozenset[str]]
    releases: tuple[Release, ...]
    windows: tuple[Window, ...] = ()


def make_graph(components: Iterable[Component], edges: Iterable[tuple[str, str]],
               releases: Iterable[Release], windows: Iterable[Window] = ()) -> Graph:
    """A Graph in one canonical order, so two built from the same facts compare equal."""
    comps = {c.name: c for c in sorted(components, key=lambda c: c.name)}
    deps: dict[str, set[str]] = {name: set() for name in comps}
    for src, dst in edges:
        deps[src].add(dst)
    rels = sorted(
        (replace(r, needs=tuple(sorted(r.needs, key=lambda n: n.component))) for r in releases),
        key=lambda r: (r.component, Version(r.version)),
    )
    return Graph(comps, {k: frozenset(v) for k, v in deps.items()}, tuple(rels),
                 tuple(sorted(windows, key=lambda w: w.name)))


def _component(g: Graph, name: str) -> Component:
    try:
        return g.components[name]
    except KeyError:
        raise UnknownName(f"no component named {name!r}") from None


def _walk(start: str, next_of: Mapping[str, Iterable[str]]) -> list[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        for name in next_of.get(stack.pop(), ()):
            if name not in seen:
                seen.add(name)
                stack.append(name)
    seen.discard(start)
    return sorted(seen)


def upstream(g: Graph, name: str) -> list[str]:
    """Every component `name` depends on, directly or not."""
    _component(g, name)
    return _walk(name, g.depends_on)


def downstream(g: Graph, name: str) -> list[str]:
    """Every component that depends on `name`, directly or not: its blast radius."""
    _component(g, name)
    users: dict[str, set[str]] = {}
    for src, dsts in g.depends_on.items():
        for dst in dsts:
            users.setdefault(dst, set()).add(src)
    return _walk(name, users)


def _releases_of(g: Graph, name: str) -> list[Release]:
    return [r for r in g.releases if r.component == name]


def prod_version(g: Graph, name: str) -> str | None:
    """The highest version whose current state is `released`; None: not in prod."""
    _component(g, name)
    released = [Version(r.version) for r in _releases_of(g, name) if r.state == "released"]
    return str(max(released)) if released else None


def release(g: Graph, name: str, version: str) -> Release:
    _component(g, name)
    wanted = parse_version(version)
    for r in _releases_of(g, name):
        if r.version == wanted:
            return r
    raise UnknownName(f"no release {name} {wanted}")


@dataclass(frozen=True)
class Step:
    release: Release  # to ship first
    needed_by: str  # the label of the release whose need it meets
    need: Need
    prod: str | None  # what prod runs today


@dataclass(frozen=True)
class Satisfied:
    need: Need
    needed_by: str
    prod: str


@dataclass(frozen=True)
class Blocker:
    need: Need
    needed_by: str
    reason: str


@dataclass(frozen=True)
class Answer:
    target: Release
    steps: tuple[Step, ...]  # upstream first
    satisfied: tuple[Satisfied, ...]
    blockers: tuple[Blocker, ...]


def _resolve(g: Graph, needer: Release, need: Need) -> Satisfied | Blocker | Release:
    """Prod already meets it, nothing can, or this in-flight release (the lowest that does)."""
    if _component(g, need.component).retired:
        return Blocker(need, needer.label, f"{need.component} is retired")
    spec = parse_range(need.spec)
    prod = prod_version(g, need.component)
    if prod is not None and Version(prod) in spec:
        return Satisfied(need, needer.label, prod)
    candidates = [r for r in _releases_of(g, need.component)
                  if r.in_flight and Version(r.version) in spec]
    if not candidates:
        return Blocker(need, needer.label, "no release satisfies it")
    return min(candidates, key=lambda r: Version(r.version))


def _ordered(edges: Mapping[str, set[str]], nodes: Iterable[str]) -> list[str]:
    """Every node after the nodes it needs; ties in name order, so the answer is stable."""
    sorter = TopologicalSorter({n: edges.get(n, set()) for n in sorted(nodes)})
    try:
        sorter.prepare()
    except CycleError as exc:
        raise GraphError("the needs form a loop: " + " → ".join(exc.args[1])) from None
    order: list[str] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        order += ready
        sorter.done(*ready)
    return order


def must_ship_before(g: Graph, name: str, version: str) -> Answer:
    """What has to ship before `name version`, upstream first, and what nothing can satisfy."""
    target = release(g, name, version)
    steps: dict[str, Step] = {}
    satisfied: list[Satisfied] = []
    blockers: list[Blocker] = []
    edges: dict[str, set[str]] = {}
    seen = {target.label}
    queue = [target]
    while queue:
        needer = queue.pop(0)
        for need in needer.needs:
            found = _resolve(g, needer, need)
            if isinstance(found, Satisfied):
                satisfied.append(found)
            elif isinstance(found, Blocker):
                blockers.append(found)
            else:
                edges.setdefault(needer.label, set()).add(found.label)
                if found.label not in seen:
                    seen.add(found.label)
                    steps[found.label] = Step(found, needer.label, need,
                                              prod_version(g, need.component))
                    queue.append(found)
    order = _ordered(edges, seen)
    return Answer(target, tuple(steps[label] for label in order if label in steps),
                  tuple(satisfied), tuple(blockers))


def release_order(g: Graph) -> list[Release]:
    """Every release in flight, each after the releases it needs."""
    flying = {r.label: r for r in g.releases if r.in_flight}
    edges: dict[str, set[str]] = {}
    for r in flying.values():
        for need in r.needs:
            found = _resolve(g, r, need)
            if isinstance(found, Release):
                edges.setdefault(r.label, set()).add(found.label)
    return [flying[label] for label in _ordered(edges, flying)]
```

- [ ] **Step 4: Run it.** `uv run pytest services/shared/tests/test_graph.py -q`. Expected: 12
      passed. `make lint` is clean.

- [ ] **Step 5: Story close-out.** Commit subject:
      `feat: THL-<n> the graph queries (SPEC-002-R9..R11)`.

---

### Task 6 · THL-33: The Backstage catalog reader (SPEC-002-R4)

**Files:**
- Create: `services/collector/thalam_collector/problems.py`,
  `services/collector/thalam_collector/catalog.py`
- Test: `services/collector/tests/test_catalog.py`. Task 8 adds its database half.

- [ ] **Step 1: Write the failing test** `services/collector/tests/test_catalog.py`:

```python
"""Backstage catalog files -> components (SPEC-002-R4). Task 8 adds the mirror's database half."""
# covers: SPEC-002-R4

from __future__ import annotations

from pathlib import Path

from thalam_collector.catalog import DESCRIPTION_CAP, read_catalog

GROUP = """\
apiVersion: backstage.io/v1alpha1
kind: Group
metadata: {name: team-a}
spec: {type: team}
"""


def _component(name: str, *, owner: str = "group:team-a", depends: str = "[]",
               description: str = "A service.") -> str:
    return f"""\
apiVersion: backstage.io/v1alpha1
kind: Component
metadata: {{name: {name}, description: {description}}}
spec: {{type: service, lifecycle: production, owner: {owner}, dependsOn: {depends}}}
"""


def _write(tmp_path: Path, *docs: str) -> Path:
    folder = tmp_path / "catalog"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "team.yaml").write_text("---\n".join(docs), encoding="utf-8")
    return tmp_path


def test_several_documents_in_one_file(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", depends='["component:db-svc"]'),
                  _component("db-svc", owner="team-a"))
    catalog, problems = read_catalog(root)
    assert problems == []
    assert catalog.groups == frozenset({"team-a"})
    api = next(c for c in catalog.components if c.name == "api")
    assert (api.owner, api.depends_on, api.file) == ("team-a", ("db-svc",), "catalog/team.yaml")


def test_other_kinds_are_skipped(tmp_path: Path) -> None:
    api_doc = "apiVersion: backstage.io/v1alpha1\nkind: API\nmetadata: {name: x}\nspec: {}\n"
    catalog, problems = read_catalog(_write(tmp_path, GROUP, api_doc))
    assert problems == [] and catalog.components == ()


def test_yaml_tags_are_never_run(tmp_path: Path) -> None:
    planted = "!!python/object/apply:os.system ['echo planted']\n"
    _, problems = read_catalog(_write(tmp_path, planted))
    assert [p.field for p in problems] == ["(file)"]
    assert "not valid YAML" in problems[0].message


def test_names_follow_backstage(tmp_path: Path) -> None:
    _, problems = read_catalog(_write(tmp_path, GROUP, _component("Not A Name")))
    assert any(p.field == "documents[1].metadata.name" for p in problems)


def test_the_owner_must_be_a_group_in_the_catalog(tmp_path: Path) -> None:
    _, problems = read_catalog(_write(tmp_path, GROUP, _component("api", owner="group:nobody")))
    assert [(p.field, p.message) for p in problems] == [
        ("documents[1].spec.owner", "no Group named 'nobody' in the catalog")]


def test_every_dependency_must_be_a_component_in_the_catalog(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP,
                  _component("api", depends='["component:ghost", "db-svc", "resource:db"]'))
    _, problems = read_catalog(root)
    assert [p.field for p in problems] == [
        "documents[1].spec.dependsOn[0]", "documents[1].spec.dependsOn[1]",
        "documents[1].spec.dependsOn[2]"]


def test_a_component_cannot_depend_on_itself_or_appear_twice(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", depends='["component:api"]'),
                  _component("api"))
    messages = [p.message for p in read_catalog(root)[1]]
    assert "a component cannot depend on itself" in messages
    assert "'api' is defined twice" in messages


def test_descriptions_are_capped(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", description="x" * 5000))
    catalog, _ = read_catalog(root)
    assert len(catalog.components[0].description) == DESCRIPTION_CAP


def test_no_catalog_files_is_a_problem(tmp_path: Path) -> None:
    _, problems = read_catalog(tmp_path)
    assert [p.file for p in problems] == ["catalog/"]
```

- [ ] **Step 2: Run it.** `uv run pytest services/collector/tests/test_catalog.py -q`. Expected:
      it fails with `ModuleNotFoundError: No module named 'thalam_collector.catalog'`.

- [ ] **Step 3: Write `services/collector/thalam_collector/problems.py`:**

```python
"""What a load found wrong: each problem names its file and field (SPEC-002-R6)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    file: str  # relative to the company folder, with forward slashes
    field: str  # where in the file, such as "releases[1].events[2]"
    message: str  # file-provided values appear through repr(), so no control character prints

    def __str__(self) -> str:
        return f"{self.file}: {self.field}: {self.message}"


class LoadError(Exception):
    """One or more problems; a load that raises this has written nothing."""

    def __init__(self, problems: list[Problem]) -> None:
        super().__init__(f"{len(problems)} problem(s)")
        self.problems = problems
```

- [ ] **Step 4: Write `services/collector/thalam_collector/catalog.py`:**

```python
"""Backstage catalog files -> components and groups (SPEC-002-R4).

Reads every *.yaml under <company>/catalog/ with yaml.safe_load_all: never yaml.load, which can
build arbitrary Python objects from a planted tag. Documents of kind Group and Component are read;
other kinds (API, System, Resource) are skipped. Only `component:` dependencies are read in Phase 1,
and each must name a Component in the catalog: a dropped edge would make "must ship before"
silently wrong, so an unknown one fails the load rather than being skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from thalam_collector.problems import Problem

NAME = r"^[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*$"  # Backstage's rule, at most 63 characters
REF = re.compile(  # "component:name", "component:default/name" or "name"
    r"^(?:(?P<kind>[A-Za-z]+):)?(?:default/)?"
    r"(?P<name>[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*)$"
)
DESCRIPTION_CAP = 1000


class _Metadata(BaseModel):
    model_config = ConfigDict(extra="ignore")  # real catalogs carry annotations, tags, links
    name: str = Field(pattern=NAME, max_length=63)
    description: str = ""


class _ComponentSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str = Field(pattern=NAME)
    lifecycle: str = Field(pattern=NAME)
    owner: str
    dependsOn: list[str] = Field(default_factory=list)


class _Group(BaseModel):
    model_config = ConfigDict(extra="ignore")
    apiVersion: Literal["backstage.io/v1alpha1"]
    kind: Literal["Group"]
    metadata: _Metadata


class _Component(BaseModel):
    model_config = ConfigDict(extra="ignore")
    apiVersion: Literal["backstage.io/v1alpha1"]
    kind: Literal["Component"]
    metadata: _Metadata
    spec: _ComponentSpec


@dataclass(frozen=True)
class CatalogComponent:
    name: str
    owner: str  # the Group's name, without "group:"
    type: str
    lifecycle: str
    description: str  # untrusted text, capped; stored, never printed
    depends_on: tuple[str, ...]
    file: str
    where: str  # "documents[n]"


@dataclass(frozen=True)
class Catalog:
    components: tuple[CatalogComponent, ...]
    groups: frozenset[str]


def pydantic_problems(file: str, prefix: str, exc: ValidationError) -> list[Problem]:
    """One Problem per Pydantic error, located as "prefix.field[i]"."""
    out = []
    for error in exc.errors():
        loc = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error["loc"])
        out.append(Problem(file, (prefix + loc).lstrip("."), error["msg"]))
    return out


def _docs(path: Path, rel: str) -> tuple[list[Any], list[Problem]]:
    try:
        return list(yaml.safe_load_all(path.read_text(encoding="utf-8"))), []
    except yaml.YAMLError as exc:
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return [], [Problem(rel, "(file)", f"not valid YAML: {first!r}")]


def read_catalog(root: Path) -> tuple[Catalog, list[Problem]]:
    """Every component and group under root/catalog/, and every problem found on the way."""
    problems: list[Problem] = []
    groups: set[str] = set()
    raw: list[tuple[CatalogComponent, list[tuple[int, str, str]]]] = []
    files = sorted((root / "catalog").glob("*.yaml"))
    if not files:
        return Catalog((), frozenset()), [Problem("catalog/", "(folder)", "no catalog files")]
    for path in files:
        rel = path.relative_to(root).as_posix()
        docs, found = _docs(path, rel)
        problems += found
        for i, doc in enumerate(docs):
            where = f"documents[{i}]"
            kind = doc.get("kind") if isinstance(doc, dict) else None
            try:
                if kind == "Group":
                    groups.add(_Group.model_validate(doc).metadata.name)
                elif kind == "Component":
                    parsed = _Component.model_validate(doc)
                    refs = [(j, f"{where}.spec.dependsOn[{j}]", ref)
                            for j, ref in enumerate(parsed.spec.dependsOn)]
                    raw.append((CatalogComponent(
                        parsed.metadata.name, parsed.spec.owner, parsed.spec.type,
                        parsed.spec.lifecycle, parsed.metadata.description[:DESCRIPTION_CAP], (),
                        rel, where), refs))
                elif not isinstance(doc, dict):
                    problems.append(Problem(rel, where, "a catalog document must be a mapping"))
            except ValidationError as exc:
                problems += pydantic_problems(rel, where, exc)
    names = [c.name for c, _ in raw]
    components: list[CatalogComponent] = []
    for c, refs in raw:
        if names.count(c.name) > 1 and c.name not in {x.name for x in components}:
            problems.append(Problem(c.file, f"{c.where}.metadata.name",
                                    f"{c.name!r} is defined twice"))
        owner = REF.match(c.owner)
        is_group = owner is not None and (owner["kind"] or "group").lower() == "group"
        owner_name = owner["name"] if owner is not None and is_group else None
        if owner_name not in groups:
            shown = owner_name if owner_name is not None else c.owner
            problems.append(Problem(c.file, f"{c.where}.spec.owner",
                                    f"no Group named {shown!r} in the catalog"))
        depends: list[str] = []
        for _, field, ref in refs:
            m = REF.match(ref)
            if not m or not m["kind"] or m["kind"].lower() != "component":
                problems.append(Problem(c.file, field, f"{ref!r} is not component:<name>"))
            elif m["name"] == c.name:
                problems.append(Problem(c.file, field, "a component cannot depend on itself"))
            elif m["name"] not in names:
                problems.append(Problem(c.file, field,
                                        f"no Component named {m['name']!r} in the catalog"))
            else:
                depends.append(m["name"])
        components.append(CatalogComponent(c.name, owner_name or c.owner, c.type, c.lifecycle,
                                           c.description, tuple(sorted(set(depends))), c.file,
                                           c.where))
    return Catalog(tuple(components), frozenset(groups)), problems
```

  If ruff reports a line over 100 characters, wrap it. If it reports import order, run
  `uv run ruff check --fix <file>`.

- [ ] **Step 5: Run it.** `uv run pytest services/collector/tests/test_catalog.py -q`. Expected:
      9 passed.

- [ ] **Step 6: Story close-out.** Commit subject:
      `feat: THL-<n> the Backstage catalog reader (SPEC-002-R4)`.

---

### Task 7 · THL-34: Release manifests, Jira files and the calendar (SPEC-002-R5, R6)

**Files:**
- Create: `services/collector/thalam_collector/company.py`
- Modify: `services/conftest.py` (adds `company_tree`)
- Test: `services/collector/tests/test_releases.py`

- [ ] **Step 1: Add the `company_tree` fixture to `services/conftest.py`.** It builds a minimal,
      valid company in a temporary folder, and tests edit it to break one thing at a time:

```python
MINIMAL = {
    "catalog/team.yaml": """\
apiVersion: backstage.io/v1alpha1
kind: Group
metadata: {name: team-a}
spec: {type: team}
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata: {name: api, description: The API.}
spec: {type: service, lifecycle: production, owner: group:team-a, dependsOn: ["component:db-svc"]}
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata: {name: db-svc}
spec: {type: service, lifecycle: production, owner: team-a}
""",
    "releases/api.yaml": """\
component: api
releases:
  - version: 1.0.0
    window: [2026-10-01, 2026-10-01]
    events:
      - planned 2026-09-01T10:00:00+05:30
      - scoped 2026-09-02T10:00:00+05:30
      - ready 2026-09-03T10:00:00+05:30
      - change_approved 2026-09-04T10:00:00+05:30
      - deploying 2026-10-01T09:00:00+05:30
      - verifying 2026-10-01T09:30:00+05:30
      - released 2026-10-01T11:00:00+05:30
  - version: 1.1.0
    window: [2026-12-01, 2026-12-01]
    needs: {db-svc: ">=2.0.0"}
    events:
      - planned 2026-11-10T10:00:00+05:30
""",
    "releases/db-svc.yaml": """\
component: db-svc
releases:
  - version: 2.0.0
    window: [2026-11-20, 2026-11-20]
    events:
      - planned 2026-11-01T10:00:00+05:30
      - scoped 2026-11-02T10:00:00+05:30
""",
    "jira/versions.json": (
        '[{"self": "https://xxxx.atlassian.net/rest/api/3/version/1", "id": "1",'
        ' "name": "api 1.0.0", "released": true},\n'
        ' {"id": "2", "name": "api 1.1.0", "released": false},\n'
        ' {"id": "3", "name": "db-svc 2.0.0", "released": false}]\n'
    ),
    "jira/search.json": (
        '{"issues": [{"key": "API-1", "fields": {"summary": "Call the new db endpoint",'
        ' "status": {"name": "In Progress"},'
        ' "fixVersions": [{"id": "2", "name": "api 1.1.0"}]}}]}\n'
    ),
    "calendar.yaml": (
        "windows:\n"
        "  - {name: year-end freeze, kind: freeze, starts: 2026-12-19, ends: 2027-01-04}\n"
    ),
}


@pytest.fixture
def company_tree(tmp_path: Path) -> Callable[..., Path]:
    """make(replace={file: (old, new)}, files={file: text or None}) -> a fresh company folder."""
    count = 0

    def make(replace: dict[str, tuple[str, str]] | None = None,
             files: dict[str, str | None] | None = None) -> Path:
        nonlocal count
        count += 1
        root = tmp_path / f"company{count}"
        contents: dict[str, str | None] = dict(MINIMAL)
        for name, (old, new) in (replace or {}).items():
            text = contents[name]
            assert text is not None and old in text, (name, old)
            contents[name] = text.replace(old, new, 1)
        contents.update(files or {})
        for name, text in contents.items():
            if text is not None:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
        return root

    return make
```

  Add `from pathlib import Path` to the conftest's imports. Wrap any line ruff finds over 100
  characters by splitting the string.

- [ ] **Step 2: Write the failing test** `services/collector/tests/test_releases.py`:

```python
"""Release manifests, Jira-shaped files and the calendar (SPEC-002-R5)."""
# covers: SPEC-002-R5

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from thalam_collector.company import SUMMARY_CAP, read_company
from thalam_collector.problems import LoadError

Make = Callable[..., Path]


def test_a_valid_company(company_tree: Make) -> None:
    company = read_company(company_tree())
    by_label = {f"{r.component} {r.version}": r for r in company.releases}
    assert sorted(by_label) == ["api 1.0.0", "api 1.1.0", "db-svc 2.0.0"]
    assert by_label["api 1.1.0"].needs == (("db-svc", ">=2.0.0"),)
    assert by_label["api 1.1.0"].jira_version_id == "2"
    assert [e.state for e in by_label["api 1.0.0"].events][-1] == "released"
    assert by_label["api 1.0.0"].events[0].window == (date(2026, 10, 1), date(2026, 10, 1))
    assert [(i.jira_key, i.component, i.version, i.status) for i in company.items] == [
        ("API-1", "api", "1.1.0", "In Progress")]
    assert [(w.name, w.kind) for w in company.windows] == [("year-end freeze", "freeze")]
    assert company.warnings == ()


def test_a_replan_moves_the_window(company_tree: Make) -> None:
    root = company_tree(replace={"releases/db-svc.yaml": (
        "      - scoped 2026-11-02T10:00:00+05:30\n",
        "      - scoped 2026-11-02T10:00:00+05:30\n"
        "      - replan 2026-11-05T10:00:00+05:30 2026-11-24 2026-11-25\n")})
    db_svc = next(r for r in read_company(root).releases if r.component == "db-svc")
    assert db_svc.events[-1].kind == "replan"
    assert db_svc.events[-1].window == (date(2026, 11, 24), date(2026, 11, 25))


def test_a_manifest_refuses_unknown_fields(company_tree: Make) -> None:
    root = company_tree(replace={"releases/api.yaml": ("component: api\n",
                                                       "component: api\ncolour: blue\n")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    # The manifest is then skipped, so the Jira files' api versions name no release too.
    assert ("releases/api.yaml", "colour") in [(p.file, p.field) for p in caught.value.problems]


@pytest.mark.parametrize("bad", ["~=2.0", "==2.*", "soon"])
def test_ranges_use_comparison_operators_only(company_tree: Make, bad: str) -> None:
    root = company_tree(replace={"releases/api.yaml": ('">=2.0.0"', f'"{bad}"')})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert caught.value.problems[0].field == "releases[1].needs.db-svc"


def test_jira_extra_fields_are_ignored_and_summaries_capped(company_tree: Make) -> None:
    root = company_tree(replace={"jira/search.json": (
        '"Call the new db endpoint"', '"' + "s" * 400 + '", "priority": {"name": "High"}')})
    item = read_company(root).items[0]
    assert len(item.summary) == SUMMARY_CAP == 255


def test_a_need_outside_the_catalog_edge_loads_with_a_warning(company_tree: Make) -> None:
    root = company_tree(replace={"catalog/team.yaml": (', dependsOn: ["component:db-svc"]', "")})
    assert read_company(root).warnings == (
        "api 1.1.0 needs db-svc, but api's catalog entry does not depend on it",)
```

- [ ] **Step 3: Run it.** `uv run pytest services/collector/tests/test_releases.py -q`. Expected:
      it fails with `ModuleNotFoundError: No module named 'thalam_collector.company'`.

- [ ] **Step 4: Write `services/collector/thalam_collector/company.py`:**

```python
"""The fixture company's files -> checked records (SPEC-002-R4, R5, R6, R13).

    <company>/catalog/*.yaml      Backstage Components and Groups (thalam_collector.catalog)
    <company>/releases/*.yaml     one manifest per component: versions, needs, events
    <company>/jira/versions.json  Jira's project-versions response shape
    <company>/jira/search.json    Jira's issue-search response shape
    <company>/calendar.yaml       freeze and blackout windows

read_company() collects every problem, each with its file and field, and raises LoadError when
there is any, so a load writes nothing (R6). Our own files are strict (unknown fields refused);
Jira's shapes keep only the fields Thalam reads, as the real API sends many more.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from thalam_shared import graph
from thalam_shared.lifecycle import NOT_IN_FLIGHT, STATES, Event, allowed, current

from thalam_collector.catalog import Catalog, pydantic_problems, read_catalog
from thalam_collector.problems import LoadError, Problem

SUMMARY_CAP = 255
STATUS_CAP = 64
EVENT = re.compile(r"^(?P<state>[a-z_]+) (?P<at>\S+)(?: (?P<start>\S+) (?P<end>\S+))?$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Release(_Strict):
    version: str
    window: tuple[date, date]
    needs: dict[str, str] = Field(default_factory=dict)
    events: list[str]

    @field_validator("version", mode="before")
    @classmethod
    def _yaml_number(cls, value: object) -> object:
        # YAML reads an unquoted 1.1 as a number. Turn it back into text, so the X.Y.Z check
        # can say what is wrong with it (found by the plan's dry run).
        if isinstance(value, int | float) and not isinstance(value, bool):
            return str(value)
        return value


class _Manifest(_Strict):
    component: str
    releases: list[_Release]


class _Window(_Strict):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["freeze", "blackout"]
    starts: date
    ends: date


class _Calendar(_Strict):
    windows: list[_Window]


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _JiraVersion(_Loose):
    id: str
    name: str


class _JiraStatus(_Loose):
    name: str


class _JiraFixVersion(_Loose):
    id: str


class _JiraFields(_Loose):
    summary: str
    status: _JiraStatus
    fixVersions: list[_JiraFixVersion] = Field(default_factory=list)


class _JiraIssue(_Loose):
    key: str = Field(pattern=r"^[A-Z][A-Z0-9]+-[0-9]+$")
    fields: _JiraFields


class _JiraSearch(_Loose):
    issues: list[_JiraIssue]


@dataclass(frozen=True)
class ReleaseRecord:
    component: str
    version: str
    needs: tuple[tuple[str, str], ...]  # (component, range), sorted by component
    events: tuple[Event, ...]
    file: str
    jira_version_id: str | None = None


@dataclass(frozen=True)
class ItemRecord:
    component: str
    version: str
    jira_key: str
    summary: str  # untrusted text, capped; stored, never printed
    status: str


@dataclass(frozen=True)
class WindowRecord:
    name: str
    kind: str
    starts: date
    ends: date


@dataclass(frozen=True)
class Company:
    catalog: Catalog
    releases: tuple[ReleaseRecord, ...]
    items: tuple[ItemRecord, ...]
    windows: tuple[WindowRecord, ...]
    warnings: tuple[str, ...]


def _read(root: Path, rel: str, problems: list[Problem]) -> Any:
    path = root / rel
    if not path.is_file():
        problems.append(Problem(rel, "(file)", "the file is missing"))
        return None
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text) if rel.endswith(".json") else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        kind = rel.rsplit(".", 1)[1].upper()
        problems.append(Problem(rel, "(file)", f"not valid {kind}: {first!r}"))
        return None


def _event(line: str, window: tuple[date, date]) -> Event:
    match = EVENT.match(line)
    if not match:
        raise ValueError("expected '<state> <time>' or 'replan <time> <start> <end>'")
    at = datetime.fromisoformat(match["at"])
    if at.tzinfo is None:
        raise ValueError("the time needs its UTC offset, such as +05:30")
    if match["state"] == "replan":
        if not match["start"]:
            raise ValueError("a replan names its new window: replan <time> <start> <end>")
        new = (date.fromisoformat(match["start"]), date.fromisoformat(match["end"]))
        if new[1] < new[0]:
            raise ValueError("the window ends before it starts")
        return Event("replan", at, None, new)
    if match["start"]:
        raise ValueError("only a replan names a window")
    if match["state"] not in STATES:
        raise ValueError(f"unknown state {match['state']!r}")
    return Event("state", at, match["state"], window if match["state"] == "planned" else None)


def _release(rel: str, where: str, component: str, doc: _Release, known: set[str],
             problems: list[Problem]) -> ReleaseRecord:
    try:
        if graph.parse_version(doc.version) != doc.version:
            raise ValueError
    except ValueError:
        problems.append(Problem(rel, f"{where}.version", f"{doc.version!r} is not X.Y.Z"))
    if doc.window[1] < doc.window[0]:
        problems.append(Problem(rel, f"{where}.window", "the window ends before it starts"))
    needs = []
    for name, spec in sorted(doc.needs.items()):
        field = f"{where}.needs.{name}"
        if name == component:
            problems.append(Problem(rel, field, "a release cannot need its own component"))
        elif name not in known:
            problems.append(Problem(rel, field, f"no component named {name!r} in the catalog"))
        try:
            graph.parse_range(spec)
        except ValueError as exc:
            problems.append(Problem(rel, field, str(exc)))
        needs.append((name, spec))
    events: list[Event] = []
    state: str | None = None
    for j, line in enumerate(doc.events):
        field = f"{where}.events[{j}]"
        try:
            event = _event(line, doc.window)
        except ValueError as exc:
            problems.append(Problem(rel, field, str(exc)))
            continue
        if events and event.at <= events[-1].at:
            problems.append(Problem(rel, field, "is not later than the event before it"))
        if event.kind == "replan" and (state is None or state in NOT_IN_FLIGHT):
            problems.append(Problem(rel, field, "a replan needs a release in flight"))
        if event.kind == "state":
            assert event.state is not None
            if not allowed(state, event.state):
                problems.append(Problem(rel, field,
                                        f"{state or 'nothing'} cannot move to {event.state}"))
            state = event.state
        events.append(event)
    if not doc.events:
        problems.append(Problem(rel, f"{where}.events", "a release starts with a planned event"))
    return ReleaseRecord(component, doc.version, tuple(needs), tuple(events), rel)


def _releases(root: Path, catalog: Catalog, problems: list[Problem]) -> list[ReleaseRecord]:
    known = {c.name for c in catalog.components}
    records: list[ReleaseRecord] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted((root / "releases").glob("*.yaml")):
        rel = path.relative_to(root).as_posix()
        data = _read(root, rel, problems)
        if data is None:
            continue
        try:
            manifest = _Manifest.model_validate(data)
        except ValidationError as exc:
            problems += pydantic_problems(rel, "", exc)
            continue
        if manifest.component not in known:
            problems.append(Problem(rel, "component",
                                    f"no component named {manifest.component!r} in the catalog"))
            continue
        for i, doc in enumerate(manifest.releases):
            where = f"releases[{i}]"
            key = (manifest.component, doc.version)
            if key in seen:
                problems.append(Problem(rel, f"{where}.version",
                                        f"{manifest.component} {doc.version} is defined twice"))
                continue
            seen.add(key)
            records.append(_release(rel, where, manifest.component, doc, known, problems))
    return records


def _jira(root: Path, records: list[ReleaseRecord], problems: list[Problem]
          ) -> tuple[list[ReleaseRecord], list[ItemRecord]]:
    by_label = {f"{r.component} {r.version}": r for r in records}
    ids: dict[str, ReleaseRecord] = {}
    data = _read(root, "jira/versions.json", problems)
    if isinstance(data, list):
        for i, raw in enumerate(data):
            try:
                version = _JiraVersion.model_validate(raw)
            except ValidationError as exc:
                problems += pydantic_problems("jira/versions.json", f"[{i}]", exc)
                continue
            record = by_label.get(version.name)
            if record is None:
                problems.append(Problem("jira/versions.json", f"[{i}].name",
                                        f"{version.name!r} names no release in the manifests"))
            elif version.id in ids or record.jira_version_id is not None:
                problems.append(Problem("jira/versions.json", f"[{i}]",
                                        "a Jira version is listed twice"))
            else:
                updated = replace(record, jira_version_id=version.id)
                by_label[version.name] = ids[version.id] = updated
    elif data is not None:
        problems.append(Problem("jira/versions.json", "(file)", "expected a list of versions"))
    items: list[ItemRecord] = []
    data = _read(root, "jira/search.json", problems)
    if data is not None:
        try:
            search = _JiraSearch.model_validate(data)
        except ValidationError as exc:
            problems += pydantic_problems("jira/search.json", "", exc)
        else:
            for i, issue in enumerate(search.issues):
                for j, fix in enumerate(issue.fields.fixVersions):
                    owner = ids.get(fix.id)
                    if owner is None:
                        problems.append(Problem("jira/search.json",
                                                f"issues[{i}].fields.fixVersions[{j}]",
                                                f"no Jira version with id {fix.id!r}"))
                        continue
                    items.append(ItemRecord(owner.component, owner.version, issue.key,
                                            issue.fields.summary[:SUMMARY_CAP],
                                            issue.fields.status.name[:STATUS_CAP]))
    return list(by_label.values()), items


def _windows(root: Path, problems: list[Problem]) -> list[WindowRecord]:
    data = _read(root, "calendar.yaml", problems)
    if data is None:
        return []
    try:
        calendar = _Calendar.model_validate(data)
    except ValidationError as exc:
        problems += pydantic_problems("calendar.yaml", "", exc)
        return []
    out: list[WindowRecord] = []
    for i, w in enumerate(calendar.windows):
        if w.ends < w.starts:
            problems.append(Problem("calendar.yaml", f"windows[{i}]",
                                    "the window ends before it starts"))
        elif w.name in {x.name for x in out}:
            problems.append(Problem("calendar.yaml", f"windows[{i}].name",
                                    f"{w.name!r} is defined twice"))
        else:
            out.append(WindowRecord(w.name, w.kind, w.starts, w.ends))
    return out


def read_company(root: Path) -> Company:
    """Every record under root, checked across files; LoadError lists every problem at once."""
    catalog, problems = read_catalog(root)
    records = _releases(root, catalog, problems)
    records, items = _jira(root, records, problems)
    windows = _windows(root, problems)
    if problems:
        raise LoadError(problems)
    depends = {c.name: set(c.depends_on) for c in catalog.components}
    warnings = tuple(
        f"{r.component} {r.version} needs {name}, but {r.component}'s catalog entry does not "
        "depend on it"
        for r in records for name, _ in r.needs if name not in depends[r.component]
    )
    return Company(catalog, tuple(records), tuple(items), tuple(windows), warnings)


def to_graph(company: Company) -> graph.Graph:
    """The Graph these files describe: what Postgres must give back after a load (R8)."""
    releases = []
    for r in company.releases:
        state, window = current(r.events)
        releases.append(graph.Release(r.component, r.version, state, window,
                                      tuple(graph.Need(c, s) for c, s in r.needs)))
    return graph.make_graph(
        [graph.Component(c.name, c.owner) for c in company.catalog.components],
        [(c.name, d) for c in company.catalog.components for d in c.depends_on],
        releases,
        [graph.Window(w.name, w.kind, w.starts, w.ends) for w in company.windows],
    )
```

- [ ] **Step 5: Run it.** `uv run pytest services/collector/tests -q`. Expected: everything
      passes (9 catalog tests and 8 release tests, counting the parametrized range test 3 times).

- [ ] **Step 6: Story close-out.** Commit subject:
      `feat: THL-<n> release manifests, Jira files and the calendar (SPEC-002-R5)`.

---

### Task 8 · THL-35: The loader: mirrors follow the files, history is written once (SPEC-002-R4, R6, R7)

**Files:**
- Create: `services/collector/thalam_collector/load.py`,
  `services/collector/thalam_collector/__main__.py`, `services/shared/thalam_shared/console.py`
- Modify: `services/collector/tests/test_catalog.py` (the database half), `Makefile`
- Test: `services/collector/tests/test_load.py`

- [ ] **Step 1: Write the failing test** `services/collector/tests/test_load.py`:

```python
"""A load writes nothing on any problem, adds only what is new, never changes history
(SPEC-002-R6, R7). The database tests run as thalam_loader, so the grants are proved enough."""
# covers: SPEC-002-R6, SPEC-002-R7

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from thalam_collector.company import read_company
from thalam_collector.load import TABLES, load
from thalam_collector.problems import LoadError
from thalam_shared import models

Make = Callable[..., Path]
Switch = Callable[[str | None], Session]
NOW = datetime(2026, 11, 23, tzinfo=UTC)
CASES = [  # (file, old, new, expected file, expected text in the problem)
    ("catalog/team.yaml", "metadata: {name: db-svc}", "metadata: {name: [", "catalog/team.yaml",
     "not valid YAML"),
    ("releases/api.yaml", "component: api\n", "component: api\ncolour: blue\n",
     "releases/api.yaml", "colour"),
    ("catalog/team.yaml", "owner: team-a", "owner: group:nobody", "catalog/team.yaml",
     "spec.owner"),
    ("catalog/team.yaml", "component:db-svc", "component:nothing", "catalog/team.yaml",
     "spec.dependsOn[0]"),
    ("releases/api.yaml", "{db-svc:", "{ghost:", "releases/api.yaml", "needs.ghost"),
    ("releases/api.yaml", "{db-svc:", "{api:", "releases/api.yaml", "its own component"),
    ("releases/db-svc.yaml", "releases:\n", "releases:\n  - version: 2.0.0\n"
     "    window: [2026-11-20, 2026-11-20]\n    events:\n"
     "      - planned 2026-11-01T10:00:00+05:30\n",
     "releases/db-svc.yaml", "defined twice"),
    ("releases/api.yaml", "version: 1.1.0", "version: 1.1", "releases/api.yaml", "is not X.Y.Z"),
    ("releases/api.yaml", '">=2.0.0"', '"~=2.0"', "releases/api.yaml", "not a version range"),
    ("calendar.yaml", "starts: 2026-12-19", "starts: 2027-02-01", "calendar.yaml",
     "ends before it starts"),
    ("releases/db-svc.yaml", "scoped 2026-11-02", "released 2026-11-02", "releases/db-svc.yaml",
     "planned cannot move to released"),
    ("releases/db-svc.yaml", "scoped 2026-11-02", "scoped 2026-10-02", "releases/db-svc.yaml",
     "is not later than"),
    ("jira/versions.json", '"name": "db-svc 2.0.0"', '"name": "db-svc 9.9.9"',
     "jira/versions.json", "names no release"),
]


def _counts(db: Session) -> dict[str, int]:
    return {name: db.scalar(select(func.count()).select_from(model)) or 0
            for name, model in TABLES.items()}


@pytest.mark.parametrize(("file", "old", "new", "where", "text"), CASES)
def test_a_bad_file_fails_the_load_and_names_itself(company_tree: Make, file: str, old: str,
                                                     new: str, where: str, text: str) -> None:
    with pytest.raises(LoadError) as caught:
        read_company(company_tree(replace={file: (old, new)}))
    assert any(p.file == where and text in str(p) for p in caught.value.problems), [
        str(p) for p in caught.value.problems]


def test_loading_twice_adds_nothing(as_role: Switch, company_tree: Make) -> None:
    db = as_role("thalam_loader")
    company = read_company(company_tree())
    first = load(db, company, now=NOW)
    assert first.added == {"component": 2, "dependency": 1, "release": 3, "release_need": 1,
                           "release_event": 10, "release_item": 1, "calendar_window": 1}
    before = _counts(db)
    assert load(db, company, now=NOW).added == {}
    assert _counts(db) == before


def test_new_events_are_appended_and_old_rows_never_change(as_role: Switch,
                                                           company_tree: Make) -> None:
    db = as_role("thalam_loader")
    load(db, read_company(company_tree()), now=NOW)
    old = sorted((e.id, e.kind, e.state, e.at) for e in db.scalars(select(models.ReleaseEvent)))
    later = company_tree(replace={"releases/db-svc.yaml": (
        "      - scoped 2026-11-02T10:00:00+05:30\n",
        "      - scoped 2026-11-02T10:00:00+05:30\n      - ready 2026-11-05T10:00:00+05:30\n")})
    assert load(db, read_company(later), now=NOW).added == {"release_event": 1}
    now_rows = sorted((e.id, e.kind, e.state, e.at)
                      for e in db.scalars(select(models.ReleaseEvent)))
    assert now_rows[: len(old)] == old and len(now_rows) == len(old) + 1


def test_a_rewritten_history_fails_and_writes_nothing(as_role: Switch, company_tree: Make) -> None:
    db = as_role("thalam_loader")
    load(db, read_company(company_tree()), now=NOW)
    before = _counts(db)
    rewritten = company_tree(replace={
        "releases/db-svc.yaml": ("      - scoped 2026-11-02T10:00:00+05:30\n", ""),
        "catalog/team.yaml": ("description: The API.", "description: Changed."),
    })
    with pytest.raises(LoadError) as caught:
        load(db, read_company(rewritten), now=NOW)
    assert "missing from the files" in str(caught.value.problems[0])
    assert _counts(db) == before
    api = db.scalars(select(models.Component).where(models.Component.name == "api")).one()
    assert api.description == "The API."


def test_a_vanished_release_fails(as_role: Switch, company_tree: Make) -> None:
    db = as_role("thalam_loader")
    load(db, read_company(company_tree()), now=NOW)
    gone = company_tree(
        replace={"releases/api.yaml": ("  - version: 1.1.0\n    window: [2026-12-01, 2026-12-01]\n"
                                       '    needs: {db-svc: ">=2.0.0"}\n    events:\n'
                                       "      - planned 2026-11-10T10:00:00+05:30\n", "")},
        files={"jira/versions.json": '[{"id": "1", "name": "api 1.0.0"},'
                                     ' {"id": "3", "name": "db-svc 2.0.0"}]\n',
               "jira/search.json": '{"issues": []}\n'},
    )
    with pytest.raises(LoadError) as caught:
        load(db, read_company(gone), now=NOW)
    assert "no longer" in str(caught.value.problems[0])


def test_a_warning_still_loads(as_role: Switch, company_tree: Make) -> None:
    db = as_role("thalam_loader")
    root = company_tree(replace={"catalog/team.yaml": (', dependsOn: ["component:db-svc"]', "")})
    report = load(db, read_company(root), now=NOW)
    assert report.warnings == (
        "api 1.1.0 needs db-svc, but api's catalog entry does not depend on it",)
    assert report.added["release_need"] == 1
```

- [ ] **Step 2: Append the database half to `services/collector/tests/test_catalog.py`.** First
      add `from collections.abc import Callable`, `from datetime import UTC, datetime`,
      `from sqlalchemy import select`, `from sqlalchemy.orm import Session`,
      `from thalam_collector.company import read_company`,
      `from thalam_collector.load import load` and `from thalam_shared import models` to its
      imports. Then append:

```python
NOW = datetime(2026, 11, 23, tzinfo=UTC)
OLD = """\
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata: {name: old-svc}
spec: {type: service, lifecycle: deprecated, owner: team-a, dependsOn: ["component:db-svc"]}
"""


def _components(db: Session) -> list[tuple[str, str, str | None]]:
    return sorted((c.name, c.description, None if c.retired_at is None else "retired")
                  for c in db.scalars(select(models.Component)))


def _edges(db: Session) -> set[tuple[int, int]]:
    rows = db.execute(select(models.Dependency.src_id, models.Dependency.dst_id))
    return {(src, dst) for src, dst in rows}


def test_the_mirror_follows_the_catalog(as_role: Callable[[str | None], Session],
                                        company_tree: Callable[..., Path]) -> None:
    db = as_role("thalam_loader")
    first = company_tree(replace={"catalog/team.yaml": ("owner: team-a}\n",
                                                        "owner: team-a}\n" + OLD)})
    load(db, read_company(first), now=NOW)
    once = (_components(db), _edges(db))
    load(db, read_company(first), now=NOW)
    assert (_components(db), _edges(db)) == once  # the same files twice change nothing
    later = company_tree(replace={"catalog/team.yaml": (', dependsOn: ["component:db-svc"]', "")})
    report = load(db, read_company(later), now=NOW)
    assert report.retired == ("old-svc",)
    assert ("old-svc", "", "retired") in _components(db)  # retired, never deleted
    assert _edges(db) == set()  # the edge set is replaced
```

- [ ] **Step 3: Run them.** `uv run pytest services/collector/tests -q` with the database up.
      Expected: the import of `thalam_collector.load` fails.

- [ ] **Step 4: Write `services/collector/thalam_collector/load.py`:**

```python
"""Records -> Postgres, in the caller's one transaction, as thalam_loader (SPEC-002-R4, R6, R7).

Two kinds of table (thalam_shared.models):
- mirrors (component, dependency, release_item, calendar_window) are made to match the files; a
  component that leaves the catalog is retired, never deleted;
- written once (release, release_need, release_event) only gain rows. If the database holds a
  release, need, Jira version or event the files no longer do, the load raises LoadError before
  writing anything: history is written once.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from thalam_shared import models
from thalam_shared.lifecycle import Event

from thalam_collector.company import Company
from thalam_collector.problems import LoadError, Problem

TABLES: dict[str, type[models.Base]] = {
    "component": models.Component, "dependency": models.Dependency,
    "release": models.Release, "release_need": models.ReleaseNeed,
    "release_event": models.ReleaseEvent, "release_item": models.ReleaseItem,
    "calendar_window": models.CalendarWindow,
}


@dataclass(frozen=True)
class Report:
    added: dict[str, int]  # rows added per table, in TABLES order; empty when nothing was new
    retired: tuple[str, ...]
    warnings: tuple[str, ...]


def _key(event: Event) -> tuple[Any, ...]:
    return (event.kind, event.state, event.window, event.at)


def _existing_releases(session: Session) -> dict[tuple[str, str], models.Release]:
    rows = session.execute(
        select(models.Release, models.Component.name)
        .join(models.Component, models.Release.component_id == models.Component.id))
    # A Row unpacks like a tuple; Result.tuples() is deprecated since SQLAlchemy 2.1.
    return {(name, release.version): release for release, name in rows}


def _history_problems(session: Session, company: Company) -> list[Problem]:
    files = {(r.component, r.version): r for r in company.releases}
    names = {c.id: c.name for c in session.scalars(select(models.Component))}
    needs: dict[int, set[tuple[str, str]]] = {}
    for n in session.scalars(select(models.ReleaseNeed)):
        needs.setdefault(n.release_id, set()).add((names[n.component_id], n.spec))
    events: dict[int, set[tuple[Any, ...]]] = {}
    for e in session.scalars(select(models.ReleaseEvent)):
        events.setdefault(e.release_id, set()).add(_key(e.as_event()))
    problems: list[Problem] = []
    for (component, version), row in sorted(_existing_releases(session).items()):
        label = f"{component} {version}"
        record = files.get((component, version))
        if record is None:
            problems.append(Problem("releases/", label, "the database holds this release but the "
                                    "files no longer do; history is written once"))
            continue
        if needs.get(row.id, set()) != set(record.needs):
            problems.append(Problem(record.file, label, "its needs differ from the ones already "
                                    "loaded; a release's needs are written once"))
        if row.jira_version_id != record.jira_version_id:
            problems.append(Problem(record.file, label, "its Jira version differs from the one "
                                    "already loaded; it is written once"))
        missing = events.get(row.id, set()) - {_key(e) for e in record.events}
        if missing:
            problems.append(Problem(record.file, label, f"{len(missing)} event(s) in the database "
                                    "are missing from the files; history is written once"))
    return problems


def load(session: Session, company: Company, *, now: datetime) -> Report:
    problems = _history_problems(session, company)
    if problems:
        raise LoadError(problems)
    added: Counter[str] = Counter()

    # Components: a mirror; one that leaves the catalog is retired, never deleted.
    rows = {c.name: c for c in session.scalars(select(models.Component))}
    wanted = {c.name: c for c in company.catalog.components}
    for name, c in wanted.items():
        row = rows.get(name)
        if row is None:
            row = models.Component(name=name, owner=c.owner, type=c.type, lifecycle=c.lifecycle,
                                   description=c.description)
            session.add(row)
            rows[name] = row
            added["component"] += 1
        else:
            row.owner, row.type, row.lifecycle = c.owner, c.type, c.lifecycle
            row.description, row.retired_at = c.description, None
    retired = []
    for name, row in sorted(rows.items()):
        if name not in wanted and row.retired_at is None:
            row.retired_at = now
            retired.append(name)
    session.flush()
    ids = {name: row.id for name, row in rows.items()}

    # Dependencies: a mirror; the edge set is replaced.
    want_edges = {(ids[c.name], ids[d]) for c in company.catalog.components for d in c.depends_on}
    have_edges = {(src, dst) for src, dst in session.execute(
        select(models.Dependency.src_id, models.Dependency.dst_id))}
    for src, dst in sorted(have_edges - want_edges):
        session.execute(delete(models.Dependency).where(models.Dependency.src_id == src,
                                                        models.Dependency.dst_id == dst))
    for src, dst in sorted(want_edges - have_edges):
        session.add(models.Dependency(src_id=src, dst_id=dst))
        added["dependency"] += 1

    # Releases, needs, events: written once, so only additions.
    have = _existing_releases(session)
    have_events = {(e.release_id, _key(e.as_event()))
                   for e in session.scalars(select(models.ReleaseEvent))}
    release_ids: dict[tuple[str, str], int] = {}
    for record in company.releases:
        release = have.get((record.component, record.version))
        if release is None:
            release = models.Release(component_id=ids[record.component], version=record.version,
                                     jira_version_id=record.jira_version_id)
            session.add(release)
            session.flush()
            added["release"] += 1
            for component, spec in record.needs:
                session.add(models.ReleaseNeed(release_id=release.id,
                                               component_id=ids[component], spec=spec))
                added["release_need"] += 1
        release_ids[(record.component, record.version)] = release.id
        for event in record.events:
            if (release.id, _key(event)) not in have_events:
                session.add(models.ReleaseEvent.from_event(release.id, event))
                added["release_event"] += 1

    # Release items: a mirror of the Jira files.
    items = {(i.release_id, i.jira_key): i for i in session.scalars(select(models.ReleaseItem))}
    wanted_items = set()
    for item in company.items:
        key = (release_ids[(item.component, item.version)], item.jira_key)
        wanted_items.add(key)
        existing = items.get(key)
        if existing is None:
            session.add(models.ReleaseItem(release_id=key[0], jira_key=item.jira_key,
                                           summary=item.summary, status=item.status))
            added["release_item"] += 1
        else:
            existing.summary, existing.status = item.summary, item.status
    for key, existing in items.items():
        if key not in wanted_items:
            session.delete(existing)

    # Calendar windows: a mirror of calendar.yaml.
    windows = {w.name: w for w in session.scalars(select(models.CalendarWindow))}
    for w in company.windows:
        row_w = windows.get(w.name)
        if row_w is None:
            session.add(models.CalendarWindow(name=w.name, kind=w.kind, starts=w.starts,
                                              ends=w.ends))
            added["calendar_window"] += 1
        else:
            row_w.kind, row_w.starts, row_w.ends = w.kind, w.starts, w.ends
    for name, row_w in windows.items():
        if name not in {w.name for w in company.windows}:
            session.delete(row_w)

    session.flush()
    in_order = {t: added[t] for t in TABLES if added[t]}
    return Report(in_order, tuple(retired), company.warnings)
```

- [ ] **Step 5: Write `services/shared/thalam_shared/console.py`.** Both commands use it: this
      one, and `make ask` in Task 11.

```python
"""Terminal output for Thalam's commands."""

from __future__ import annotations

import io
import sys


def utf8_output() -> None:
    """Write UTF-8 whatever the terminal. Git Bash's terminal is not a Windows console, so Python
    would write cp1252 and every · would print as a replacement character (found by the plan's
    dry run; scripts/dev/spec_coverage.py does the same)."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
```

  Then write `services/collector/thalam_collector/__main__.py`:

```python
"""python -m thalam_collector load <company folder>: `make load` (SPEC-002-R4..R7).

Checks every file first; on any problem it prints them all (file, field, message) and writes
nothing. Then it loads as thalam_loader, in one transaction.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from thalam_shared.console import utf8_output
from thalam_shared.db import engine
from thalam_shared.env import MissingSetting

from thalam_collector.company import read_company
from thalam_collector.load import load
from thalam_collector.problems import LoadError


def main(argv: list[str] | None = None) -> int:
    utf8_output()  # a problem can quote a file's non-ASCII text
    parser = argparse.ArgumentParser(prog="thalam_collector")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("load", help="load a company folder").add_argument("folder", type=Path)
    args = parser.parse_args(argv)
    try:
        company = read_company(args.folder)
        with Session(engine("loader")) as session, session.begin():
            report = load(session, company, now=datetime.now(UTC))
    except LoadError as exc:
        for problem in exc.problems:
            print(f"problem: {problem}", file=sys.stderr)
        print("nothing was written", file=sys.stderr)
        return 1
    except MissingSetting as exc:
        print(f"set {exc.args[0]} in .env (see .env.example)", file=sys.stderr)
        return 2
    except OperationalError:
        print("Postgres is not reachable as thalam_loader: run `make db-up`, `make migrate` and "
              "`make db-roles`", file=sys.stderr)
        return 1
    for warning in report.warnings:
        print(f"warning: {warning}")
    added = ", ".join(f"{n} {table}" for table, n in report.added.items()) or "nothing new"
    retired = f"; retired: {', '.join(report.retired)}" if report.retired else ""
    print(f"loaded: {added}{retired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: The Makefile target:**

```makefile
.PHONY: load
load: ## Load the fixture company as thalam_loader; writes nothing on any problem (SPEC-002-R4..R7)
	uv run python -m thalam_collector load evals/company
```

- [ ] **Step 7: Run them.** `uv run pytest services/collector/tests -q`. Expected: everything
      passes: 13 parametrized cases, 5 database tests in `test_load.py`, and the catalog's
      mirror test. If the first-load count in `test_loading_twice_adds_nothing` differs, recount
      by hand from `MINIMAL`: 2 components, 1 dependency, 3 releases, 1 need, 10 events (7 + 1 + 2),
      1 item and 1 window. Fix whichever side is wrong; never weaken the test to pass.

- [ ] **Step 8: Story close-out.** Commit subject:
      `feat: THL-<n> the loader: mirrors follow the files, history is written once (SPEC-002-R6, R7)`.

---

### Task 9 · THL-36: The fixture company (SPEC-002-R13)

**Files:**
- Create:
  - `evals/company/catalog/storefront.yaml`, `checkout.yaml`, `pricing.yaml` and `finance.yaml`;
  - `evals/company/releases/<component>.yaml`, one for each of the 8 components;
  - `evals/company/jira/versions.json`, `evals/company/jira/search.json` and
    `evals/company/calendar.yaml`.
- Test: `services/collector/tests/test_fixture_company.py`

**The company (SPEC-002-R13):**
- **Four teams:**
  - storefront: `web-shop`, `catalog-svc`
  - checkout: `cart-api`, `checkout-svc`
  - pricing: `pricing-svc`, `promo-svc`
  - finance: `ledger-svc`, `payments-gw`
- **Size:** 11 dependencies, 17 releases, 81 events, 9 needs, 14 Jira issues and 2 windows.
- **The scenarios, built in on purpose:**
  - **The gate:** `cart-api 2.3.0` needs `pricing-svc 1.8.0` first; `ledger-svc` is satisfied by
    prod's 4.2.0, even though 4.3.0 is in flight.
  - **A two-step chain:** `checkout-svc 3.0.0`.
  - **A blocker:** `web-shop 5.1.0` needs a `catalog-svc` 3.x that nothing plans.
  - **A cancelled release:** `promo-svc 1.3.0`.
  - **A rolled-back release:** `payments-gw 3.2.0`, so prod stays on 3.1.0.
  - **A slipped release:** `pricing-svc 1.8.0` is re-planned from 1 to 3 December.
  - **The year-end freeze.**

- [ ] **Step 1: Write the failing test** `services/collector/tests/test_fixture_company.py`:

```python
"""The fixture company and its scenarios (SPEC-002-R13): the files, then the graph. No database."""
# covers: SPEC-002-R13

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from thalam_collector.company import read_company, to_graph
from thalam_shared.graph import (
    Step,
    downstream,
    must_ship_before,
    prod_version,
    release,
    release_order,
    upstream,
)

COMPANY = Path(__file__).resolve().parents[3] / "evals" / "company"
FIXTURE = read_company(COMPANY)
GRAPH = to_graph(FIXTURE)


def _labels(steps: Iterable[Step]) -> list[str]:
    return [s.release.label for s in steps]


def test_eight_components_across_four_teams_and_no_warning() -> None:
    assert len(FIXTURE.catalog.components) == 8
    assert FIXTURE.catalog.groups == {"storefront", "checkout", "pricing", "finance"}
    assert {c.owner for c in FIXTURE.catalog.components} == FIXTURE.catalog.groups
    assert FIXTURE.warnings == ()
    assert (len(FIXTURE.releases), sum(len(r.events) for r in FIXTURE.releases),
            len(FIXTURE.items)) == (17, 81, 14)


def test_the_dependency_web() -> None:
    assert upstream(GRAPH, "cart-api") == ["catalog-svc", "ledger-svc", "pricing-svc", "promo-svc"]
    assert downstream(GRAPH, "ledger-svc") == [
        "cart-api", "checkout-svc", "payments-gw", "pricing-svc", "web-shop"]


def test_the_gate() -> None:
    answer = must_ship_before(GRAPH, "cart-api", "2.3")
    assert _labels(answer.steps) == ["pricing-svc 1.8.0"]
    assert ("ledger-svc", "4.2.0") in [(s.need.component, s.prod) for s in answer.satisfied]
    assert answer.blockers == ()


def test_a_two_step_chain() -> None:
    answer = must_ship_before(GRAPH, "checkout-svc", "3.0.0")
    assert _labels(answer.steps) == ["payments-gw 3.2.1", "pricing-svc 1.8.0", "cart-api 2.3.0"]


def test_a_blocker() -> None:
    answer = must_ship_before(GRAPH, "web-shop", "5.1.0")
    assert [(b.need.component, b.reason) for b in answer.blockers] == [
        ("catalog-svc", "no release satisfies it")]


def test_a_cancelled_and_a_rolled_back_release() -> None:
    states = {r.label: r.state for r in GRAPH.releases}
    assert states["promo-svc 1.3.0"] == "cancelled"
    assert states["payments-gw 3.2.0"] == "rolled_back"
    assert prod_version(GRAPH, "payments-gw") == "3.1.0"
    assert [r.label for r in release_order(GRAPH)] == [
        "ledger-svc 4.3.0", "payments-gw 3.2.1", "pricing-svc 1.8.0", "cart-api 2.3.0",
        "checkout-svc 3.0.0", "web-shop 5.1.0"]


def test_a_slipped_release_shows_its_new_window() -> None:
    assert release(GRAPH, "pricing-svc", "1.8.0").window == (date(2026, 12, 3), date(2026, 12, 3))


def test_a_december_freeze() -> None:
    assert any(w.kind == "freeze" and w.starts.month == 12 for w in GRAPH.windows)


def test_every_host_is_xxxx() -> None:
    for path in sorted(COMPANY.rglob("*")):
        if path.is_file():
            for host in re.findall(r"https?://([^/\s\"']+)", path.read_text(encoding="utf-8")):
                assert host == "xxxx.atlassian.net", (path.name, host)
```

- [ ] **Step 2: Run it.** `uv run pytest services/collector/tests/test_fixture_company.py -q`.
      Expected: collection fails with `LoadError`, because the company folder does not exist.

- [ ] **Step 3: Write the catalog.** Each team's file holds its Group and its Components.
      `evals/company/catalog/storefront.yaml`:

```yaml
# The fixture company (SPEC-002-R13): synthetic, every name invented.
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: storefront
  description: The web shop and the product catalogue.
spec:
  type: team
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: web-shop
  description: The customer-facing shop.
spec:
  type: website
  lifecycle: production
  owner: group:storefront
  dependsOn:
    - component:cart-api
    - component:catalog-svc
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: catalog-svc
  description: Products, prices on display, stock levels.
spec:
  type: service
  lifecycle: production
  owner: group:storefront
```

  `evals/company/catalog/checkout.yaml`:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: checkout
  description: The cart and the checkout.
spec:
  type: team
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: cart-api
  description: Holds each customer's cart and prices it.
spec:
  type: service
  lifecycle: production
  owner: group:checkout
  dependsOn:
    - component:pricing-svc
    - component:catalog-svc
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: checkout-svc
  description: Turns a cart into a paid order.
spec:
  type: service
  lifecycle: production
  owner: group:checkout
  dependsOn:
    - component:cart-api
    - component:payments-gw
    - component:ledger-svc
```

  `evals/company/catalog/pricing.yaml`:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: pricing
  description: Prices and promotions.
spec:
  type: team
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: pricing-svc
  description: The price of anything, in any currency.
spec:
  type: service
  lifecycle: production
  owner: group:pricing
  dependsOn:
    - component:ledger-svc
    - component:promo-svc
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: promo-svc
  description: Discount codes and campaigns.
spec:
  type: service
  lifecycle: production
  owner: group:pricing
  dependsOn:
    - component:catalog-svc
```

  `evals/company/catalog/finance.yaml`:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: finance
  description: Money in, money recorded.
spec:
  type: team
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: ledger-svc
  description: The general ledger.
spec:
  type: service
  lifecycle: production
  owner: group:finance
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: payments-gw
  description: Card and wallet payments.
spec:
  type: service
  lifecycle: production
  owner: group:finance
  dependsOn:
    - component:ledger-svc
```

- [ ] **Step 4: Write the release manifests.** Every time is IST (`+05:30`). A released release
      walks the whole life cycle, one step at a time. `evals/company/releases/catalog-svc.yaml`:

```yaml
component: catalog-svc
releases:
  - version: 2.5.0
    window: [2026-11-04, 2026-11-04]
    events:
      - planned 2026-10-20T10:00:00+05:30
      - scoped 2026-10-22T10:00:00+05:30
      - ready 2026-10-29T10:00:00+05:30
      - change_approved 2026-10-30T15:00:00+05:30
      - deploying 2026-11-04T09:00:00+05:30
      - verifying 2026-11-04T09:30:00+05:30
      - released 2026-11-04T11:00:00+05:30
```

  `evals/company/releases/ledger-svc.yaml`:

```yaml
component: ledger-svc
releases:
  - version: 4.1.0
    window: [2026-09-15, 2026-09-15]
    events:
      - planned 2026-09-01T10:00:00+05:30
      - scoped 2026-09-03T10:00:00+05:30
      - ready 2026-09-10T10:00:00+05:30
      - change_approved 2026-09-11T15:00:00+05:30
      - deploying 2026-09-15T09:00:00+05:30
      - verifying 2026-09-15T09:30:00+05:30
      - released 2026-09-15T11:00:00+05:30
  - version: 4.2.0
    window: [2026-10-20, 2026-10-20]
    events:
      - planned 2026-10-05T10:00:00+05:30
      - scoped 2026-10-07T10:00:00+05:30
      - ready 2026-10-14T10:00:00+05:30
      - change_approved 2026-10-15T15:00:00+05:30
      - deploying 2026-10-20T09:00:00+05:30
      - verifying 2026-10-20T09:30:00+05:30
      - released 2026-10-20T11:00:00+05:30
  - version: 4.3.0
    window: [2026-12-15, 2026-12-15]
    events:
      - planned 2026-11-18T10:00:00+05:30
```

  `evals/company/releases/promo-svc.yaml`:

```yaml
component: promo-svc
releases:
  - version: 1.2.0
    window: [2026-10-27, 2026-10-27]
    events:
      - planned 2026-10-12T10:00:00+05:30
      - scoped 2026-10-14T10:00:00+05:30
      - ready 2026-10-21T10:00:00+05:30
      - change_approved 2026-10-22T15:00:00+05:30
      - deploying 2026-10-27T09:00:00+05:30
      - verifying 2026-10-27T09:30:00+05:30
      - released 2026-10-27T11:00:00+05:30
  - version: 1.3.0
    window: [2026-12-01, 2026-12-01]
    events:
      - planned 2026-11-09T10:00:00+05:30
      - cancelled 2026-11-20T15:00:00+05:30
```

  `evals/company/releases/pricing-svc.yaml`:

```yaml
component: pricing-svc
releases:
  - version: 1.7.0
    window: [2026-10-28, 2026-10-28]
    events:
      - planned 2026-10-13T10:00:00+05:30
      - scoped 2026-10-15T10:00:00+05:30
      - ready 2026-10-22T10:00:00+05:30
      - change_approved 2026-10-23T15:00:00+05:30
      - deploying 2026-10-28T09:00:00+05:30
      - verifying 2026-10-28T09:30:00+05:30
      - released 2026-10-28T11:00:00+05:30
  - version: 1.8.0
    window: [2026-12-01, 2026-12-01]
    needs:
      ledger-svc: ">=4.1.0"
      promo-svc: ">=1.2.0"
    events:
      - planned 2026-11-10T10:00:00+05:30
      - scoped 2026-11-13T10:00:00+05:30
      - replan 2026-11-19T12:00:00+05:30 2026-12-03 2026-12-03
```

  `evals/company/releases/cart-api.yaml`:

```yaml
component: cart-api
releases:
  - version: 2.2.0
    window: [2026-11-02, 2026-11-02]
    events:
      - planned 2026-10-16T10:00:00+05:30
      - scoped 2026-10-19T10:00:00+05:30
      - ready 2026-10-27T10:00:00+05:30
      - change_approved 2026-10-28T15:00:00+05:30
      - deploying 2026-11-02T09:00:00+05:30
      - verifying 2026-11-02T09:30:00+05:30
      - released 2026-11-02T11:00:00+05:30
  - version: 2.3.0
    window: [2026-12-08, 2026-12-08]
    needs:
      pricing-svc: ">=1.8.0"
      catalog-svc: ">=2.5.0"
    events:
      - planned 2026-11-16T10:00:00+05:30
```

  `evals/company/releases/payments-gw.yaml`:

```yaml
component: payments-gw
releases:
  - version: 3.1.0
    window: [2026-10-06, 2026-10-06]
    events:
      - planned 2026-09-21T10:00:00+05:30
      - scoped 2026-09-23T10:00:00+05:30
      - ready 2026-09-30T10:00:00+05:30
      - change_approved 2026-10-01T15:00:00+05:30
      - deploying 2026-10-06T09:00:00+05:30
      - verifying 2026-10-06T09:30:00+05:30
      - released 2026-10-06T11:00:00+05:30
  - version: 3.2.0
    window: [2026-11-17, 2026-11-17]
    events:
      - planned 2026-11-02T10:00:00+05:30
      - scoped 2026-11-04T10:00:00+05:30
      - ready 2026-11-10T10:00:00+05:30
      - change_approved 2026-11-11T15:00:00+05:30
      - deploying 2026-11-17T09:00:00+05:30
      - rolled_back 2026-11-17T09:40:00+05:30
  - version: 3.2.1
    window: [2026-12-02, 2026-12-02]
    needs:
      ledger-svc: ">=4.2.0"
    events:
      - planned 2026-11-18T10:00:00+05:30
      - scoped 2026-11-19T10:00:00+05:30
      - ready 2026-11-23T10:00:00+05:30
```

  `evals/company/releases/checkout-svc.yaml`:

```yaml
component: checkout-svc
releases:
  - version: 2.9.0
    window: [2026-10-21, 2026-10-21]
    events:
      - planned 2026-10-06T10:00:00+05:30
      - scoped 2026-10-08T10:00:00+05:30
      - ready 2026-10-15T10:00:00+05:30
      - change_approved 2026-10-16T15:00:00+05:30
      - deploying 2026-10-21T09:00:00+05:30
      - verifying 2026-10-21T09:30:00+05:30
      - released 2026-10-21T11:00:00+05:30
  - version: 3.0.0
    window: [2026-12-10, 2026-12-10]
    needs:
      cart-api: ">=2.3.0"
      payments-gw: ">=3.2.0"
    events:
      - planned 2026-11-20T10:00:00+05:30
```

  `evals/company/releases/web-shop.yaml`:

```yaml
component: web-shop
releases:
  - version: 5.0.0
    window: [2026-11-05, 2026-11-05]
    events:
      - planned 2026-10-21T10:00:00+05:30
      - scoped 2026-10-23T10:00:00+05:30
      - ready 2026-10-30T10:00:00+05:30
      - change_approved 2026-10-31T15:00:00+05:30
      - deploying 2026-11-05T09:00:00+05:30
      - verifying 2026-11-05T09:30:00+05:30
      - released 2026-11-05T11:00:00+05:30
  - version: 5.1.0
    window: [2026-12-11, 2026-12-11]
    needs:
      cart-api: ">=2.3.0"
      catalog-svc: ">=3.0.0"
    events:
      - planned 2026-11-21T10:00:00+05:30
```

- [ ] **Step 5: Write the Jira files.** They use Jira's REST shapes, with `xxxx` hosts.
      Projects: SHOP 10100 (storefront), CHK 10101 (checkout), PRC 10102 (pricing), FIN 10103
      (finance). `evals/company/jira/versions.json`:

```json
[
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10001", "id": "10001", "name": "catalog-svc 2.5.0", "archived": false, "released": true, "releaseDate": "2026-11-04", "projectId": 10100},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10002", "id": "10002", "name": "ledger-svc 4.1.0", "archived": false, "released": true, "releaseDate": "2026-09-15", "projectId": 10103},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10003", "id": "10003", "name": "ledger-svc 4.2.0", "archived": false, "released": true, "releaseDate": "2026-10-20", "projectId": 10103},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10004", "id": "10004", "name": "ledger-svc 4.3.0", "archived": false, "released": false, "releaseDate": "2026-12-15", "projectId": 10103},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10005", "id": "10005", "name": "promo-svc 1.2.0", "archived": false, "released": true, "releaseDate": "2026-10-27", "projectId": 10102},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10006", "id": "10006", "name": "promo-svc 1.3.0", "archived": true, "released": false, "releaseDate": "2026-12-01", "projectId": 10102},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10007", "id": "10007", "name": "pricing-svc 1.7.0", "archived": false, "released": true, "releaseDate": "2026-10-28", "projectId": 10102},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10008", "id": "10008", "name": "pricing-svc 1.8.0", "archived": false, "released": false, "releaseDate": "2026-12-03", "projectId": 10102},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10009", "id": "10009", "name": "cart-api 2.2.0", "archived": false, "released": true, "releaseDate": "2026-11-02", "projectId": 10101},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10010", "id": "10010", "name": "cart-api 2.3.0", "archived": false, "released": false, "releaseDate": "2026-12-08", "projectId": 10101},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10011", "id": "10011", "name": "payments-gw 3.1.0", "archived": false, "released": true, "releaseDate": "2026-10-06", "projectId": 10103},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10012", "id": "10012", "name": "payments-gw 3.2.0", "archived": true, "released": false, "releaseDate": "2026-11-17", "projectId": 10103},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10013", "id": "10013", "name": "payments-gw 3.2.1", "archived": false, "released": false, "releaseDate": "2026-12-02", "projectId": 10103},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10014", "id": "10014", "name": "checkout-svc 2.9.0", "archived": false, "released": true, "releaseDate": "2026-10-21", "projectId": 10101},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10015", "id": "10015", "name": "checkout-svc 3.0.0", "archived": false, "released": false, "releaseDate": "2026-12-10", "projectId": 10101},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10016", "id": "10016", "name": "web-shop 5.0.0", "archived": false, "released": true, "releaseDate": "2026-11-05", "projectId": 10100},
  {"self": "https://xxxx.atlassian.net/rest/api/3/version/10017", "id": "10017", "name": "web-shop 5.1.0", "archived": false, "released": false, "releaseDate": "2026-12-11", "projectId": 10100}
]
```

  `evals/company/jira/search.json`. The issues are fake; their summaries are untrusted text the
  CLI never prints.

```json
{"startAt": 0, "maxResults": 50, "total": 14, "issues": [
  {"id": "20101", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20101", "key": "SHOP-101", "fields": {"summary": "Show delivery dates on the basket page", "status": {"name": "Done"}, "fixVersions": [{"id": "10016", "name": "web-shop 5.0.0"}]}},
  {"id": "20112", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20112", "key": "SHOP-112", "fields": {"summary": "Gift cards at checkout", "status": {"name": "In Progress"}, "fixVersions": [{"id": "10017", "name": "web-shop 5.1.0"}]}},
  {"id": "20113", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20113", "key": "SHOP-113", "fields": {"summary": "Search by colour (needs catalog-svc 3.x)", "status": {"name": "To Do"}, "fixVersions": [{"id": "10017", "name": "web-shop 5.1.0"}]}},
  {"id": "20201", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20201", "key": "CHK-201", "fields": {"summary": "Cart totals in the customer's currency", "status": {"name": "Done"}, "fixVersions": [{"id": "10009", "name": "cart-api 2.2.0"}]}},
  {"id": "20214", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20214", "key": "CHK-214", "fields": {"summary": "Use pricing-svc's bulk price endpoint", "status": {"name": "In Progress"}, "fixVersions": [{"id": "10010", "name": "cart-api 2.3.0"}]}},
  {"id": "20215", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20215", "key": "CHK-215", "fields": {"summary": "Keep the cart for 30 days", "status": {"name": "To Do"}, "fixVersions": [{"id": "10010", "name": "cart-api 2.3.0"}]}},
  {"id": "20230", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20230", "key": "CHK-230", "fields": {"summary": "Split a payment across two cards", "status": {"name": "In Progress"}, "fixVersions": [{"id": "10015", "name": "checkout-svc 3.0.0"}]}},
  {"id": "20231", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20231", "key": "CHK-231", "fields": {"summary": "Post the order to the ledger in one call", "status": {"name": "To Do"}, "fixVersions": [{"id": "10015", "name": "checkout-svc 3.0.0"}]}},
  {"id": "20301", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20301", "key": "PRC-301", "fields": {"summary": "Bulk price endpoint", "status": {"name": "In Review"}, "fixVersions": [{"id": "10008", "name": "pricing-svc 1.8.0"}]}},
  {"id": "20302", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20302", "key": "PRC-302", "fields": {"summary": "Round prices per currency", "status": {"name": "Done"}, "fixVersions": [{"id": "10008", "name": "pricing-svc 1.8.0"}]}},
  {"id": "20401", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20401", "key": "FIN-401", "fields": {"summary": "Archive closed periods", "status": {"name": "To Do"}, "fixVersions": [{"id": "10004", "name": "ledger-svc 4.3.0"}]}},
  {"id": "20410", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20410", "key": "FIN-410", "fields": {"summary": "A new card network", "status": {"name": "Done"}, "fixVersions": [{"id": "10012", "name": "payments-gw 3.2.0"}]}},
  {"id": "20411", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20411", "key": "FIN-411", "fields": {"summary": "Fix the timeout that rolled back 3.2.0", "status": {"name": "In Review"}, "fixVersions": [{"id": "10013", "name": "payments-gw 3.2.1"}]}},
  {"id": "20412", "self": "https://xxxx.atlassian.net/rest/api/3/issue/20412", "key": "FIN-412", "fields": {"summary": "Retries for the card network", "status": {"name": "Done"}, "fixVersions": [{"id": "10013", "name": "payments-gw 3.2.1"}]}}
]}
```

  `evals/company/calendar.yaml`:

```yaml
# Freeze and blackout windows (SPEC-002-R5). Loaded in Phase 1, checked against in Phase 4.
windows:
  - name: year-end freeze
    kind: freeze
    starts: 2026-12-19
    ends: 2027-01-04
  - name: ledger month-end close
    kind: blackout
    starts: 2026-11-28
    ends: 2026-11-30
```

- [ ] **Step 6: Run it.** `uv run pytest services/collector/tests/test_fixture_company.py -q`.
      Expected: 9 passed. If a count or an order differs, recheck the files against "The company"
      above. The test is the spec; never edit it to match a typo.

- [ ] **Step 7: Story close-out.** Commit subject:
      `feat: THL-<n> the fixture company (SPEC-002-R13)`.

---

### Task 10 · THL-37: Read the graph from Postgres as the reader (SPEC-002-R8)

**Files:**
- Create: `services/shared/thalam_shared/graph_read.py`
- Test: `services/shared/tests/test_graph_read.py`

- [ ] **Step 1: Write the failing test** `services/shared/tests/test_graph_read.py`:

```python
"""Postgres gives back the graph the files describe, read as thalam_reader (SPEC-002-R8)."""
# covers: SPEC-002-R8

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session
from thalam_collector.company import read_company, to_graph
from thalam_collector.load import load
from thalam_shared.graph import make_graph
from thalam_shared.graph_read import load_graph

Switch = Callable[[str | None], Session]
COMPANY = Path(__file__).resolve().parents[3] / "evals" / "company"
NOW = datetime(2026, 11, 23, tzinfo=UTC)


def test_the_database_read_matches_the_files(as_role: Switch) -> None:
    company = read_company(COMPANY)
    load(as_role("thalam_loader"), company, now=NOW)
    assert load_graph(as_role("thalam_reader")) == to_graph(company)


def test_an_empty_database_reads_as_an_empty_graph(as_role: Switch) -> None:
    assert load_graph(as_role("thalam_reader")) == make_graph([], [], [])
```

- [ ] **Step 2: Run it.** `uv run pytest services/shared/tests/test_graph_read.py -q`, with the
      database up. Expected: it fails with `ModuleNotFoundError: No module named
      'thalam_shared.graph_read'`.

- [ ] **Step 3: Write `services/shared/thalam_shared/graph_read.py`:**

```python
"""Postgres -> Graph (SPEC-002-R8): every table, read in the caller's one transaction.

The caller picks the role and the isolation level. `make ask` opens a REPEATABLE READ transaction
as thalam_reader, so a load running at the same moment cannot show it half a graph. Free text
(descriptions, summaries) is not read at all: a Graph has nowhere to hold it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from thalam_shared import graph, models
from thalam_shared.lifecycle import Event, current


def load_graph(session: Session) -> graph.Graph:
    components = list(session.scalars(select(models.Component)))
    names = {c.id: c.name for c in components}
    edges = [(names[d.src_id], names[d.dst_id])
             for d in session.scalars(select(models.Dependency))]
    needs: dict[int, list[graph.Need]] = {}
    for n in session.scalars(select(models.ReleaseNeed)):
        needs.setdefault(n.release_id, []).append(graph.Need(names[n.component_id], n.spec))
    events: dict[int, list[Event]] = {}
    for e in session.scalars(select(models.ReleaseEvent)):
        events.setdefault(e.release_id, []).append(e.as_event())
    releases = []
    for r in session.scalars(select(models.Release)):
        state, window = current(events.get(r.id, []))
        releases.append(graph.Release(names[r.component_id], r.version, state, window,
                                      tuple(needs.get(r.id, []))))
    windows = [graph.Window(w.name, w.kind, w.starts, w.ends)
               for w in session.scalars(select(models.CalendarWindow))]
    return graph.make_graph(
        [graph.Component(c.name, c.owner, c.retired_at is not None) for c in components],
        edges, releases, windows)
```

- [ ] **Step 4: Run it.** `uv run pytest services/shared/tests/test_graph_read.py -q`. Expected:
      2 passed.

- [ ] **Step 5: Story close-out.** Commit subject:
      `feat: THL-<n> read the graph from Postgres as the reader (SPEC-002-R8)`.

---

### Task 11 · THL-38: make ask (SPEC-002-R12)

**Files:**
- Create: `services/shared/thalam_shared/ask.py`
- Modify: `Makefile`
- Test: `services/shared/tests/test_ask.py`

- [ ] **Step 1: Write the failing test** `services/shared/tests/test_ask.py`:

```python
"""make ask (SPEC-002-R12): the answers, the exit codes, and validated fields only."""
# covers: SPEC-002-R12

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pytest
from thalam_shared import db
from thalam_shared.ask import ANSWERED, BAD_INPUT, BLOCKED, UNREACHABLE, USAGE, answer, main
from thalam_shared.graph import Component, Need, Release, Window, make_graph


def rel(component: str, version: str, state: str = "planned",
        needs: Iterable[tuple[str, str]] = (), day: date = date(2026, 12, 1)) -> Release:
    return Release(component, version, state, (day, day), tuple(Need(c, s) for c, s in needs))


GATE = make_graph(
    [Component(n, "team") for n in ("cart-api", "catalog-svc", "ledger-svc", "pricing-svc",
                                    "web-shop")],
    [("cart-api", "pricing-svc"), ("cart-api", "catalog-svc"), ("pricing-svc", "ledger-svc"),
     ("web-shop", "catalog-svc")],
    [
        rel("catalog-svc", "2.5.0", "released"),
        rel("ledger-svc", "4.2.0", "released"),
        rel("pricing-svc", "1.7.0", "released"),
        rel("pricing-svc", "1.8.0", "scoped", [("ledger-svc", ">=4.1.0")], date(2026, 12, 3)),
        rel("cart-api", "2.3.0", needs=[("pricing-svc", ">=1.8.0"), ("catalog-svc", ">=2.5.0")],
            day=date(2026, 12, 8)),
        rel("web-shop", "5.1.0", needs=[("catalog-svc", ">=3.0.0")], day=date(2026, 12, 11)),
    ],
    [Window("\x1b[31mplanted", "freeze", date(2026, 12, 19), date(2027, 1, 4))],
)


def test_before_prints_the_answer_upstream_first() -> None:
    assert answer(GATE, ["before", "cart-api", "2.3"]) == (ANSWERED, [
        "cart-api 2.3.0 · planned · window 2026-12-08",
        "Ship first, in order:",
        "  1. pricing-svc 1.8.0 · scoped · 2026-12-03 · cart-api 2.3.0 needs >=1.8.0, "
        "prod runs 1.7.0",
        "Already satisfied:",
        "  - catalog-svc >=2.5.0 (for cart-api 2.3.0) · prod runs 2.5.0",
        "  - ledger-svc >=4.1.0 (for pricing-svc 1.8.0) · prod runs 4.2.0",
        "Blockers: none",
    ])


def test_an_answer_with_blockers_exits_3() -> None:
    assert answer(GATE, ["before", "web-shop", "5.1.0"]) == (BLOCKED, [
        "web-shop 5.1.0 · planned · window 2026-12-11",
        "Ship first: nothing",
        "Blockers:",
        "  - web-shop 5.1.0 needs catalog-svc >=3.0.0: no release satisfies it",
    ])


def test_upstream_downstream_and_order() -> None:
    assert answer(GATE, ["upstream", "cart-api"]) == (ANSWERED, [
        "upstream of cart-api:", "  - catalog-svc", "  - ledger-svc", "  - pricing-svc"])
    assert answer(GATE, ["downstream", "ledger-svc"]) == (ANSWERED, [
        "downstream of ledger-svc:", "  - cart-api", "  - pricing-svc"])
    assert answer(GATE, ["order"]) == (ANSWERED, [
        "In flight, in a safe order:", "  1. pricing-svc 1.8.0 · scoped · 2026-12-03",
        "  2. web-shop 5.1.0 · planned · 2026-12-11", "  3. cart-api 2.3.0 · planned · 2026-12-08"])


@pytest.mark.parametrize(("words", "line"), [
    (["before", "nope", "1.0"], "no component named 'nope'"),
    (["before", "cart-api", "9.9"], "no release cart-api 9.9.0"),
    (["before", "cart-api", "two"], "not a version: 'two' (expected X.Y.Z)"),
    (["sideways"], USAGE),
    (["before", "cart-api"], USAGE),
    ([], USAGE),
])
def test_bad_input_exits_2(words: list[str], line: str) -> None:
    assert answer(GATE, words) == (BAD_INPUT, [line])


def test_a_loop_exits_3_and_names_it() -> None:
    g = make_graph([Component("a", "t"), Component("b", "t")], [], [
        rel("a", "1.0.0", needs=[("b", ">=1.0.0")]), rel("b", "1.0.0", needs=[("a", ">=1.0.0")])])
    code, lines = answer(g, ["before", "a", "1.0.0"])
    assert code == BLOCKED and lines[0].startswith("the needs form a loop")


def test_no_free_text_reaches_the_output() -> None:
    for words in (["before", "cart-api", "2.3"], ["upstream", "web-shop"], ["order"],
                  ["before", "\x1b[2Jcart", "1.0"]):
        assert not any("\x1b" in line for line in answer(GATE, words)[1]), words


def test_bad_input_never_opens_the_database(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["sideways"]) == BAD_INPUT
    assert USAGE in capsys.readouterr().err


def test_an_unreachable_database_exits_1_without_its_address(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name, value in {"POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "9", "POSTGRES_DB": "x",
                        "THALAM_READER_PASSWORD": "pw-must-not-print"}.items():
        monkeypatch.setenv(name, value)
    db.engine.cache_clear()
    try:
        assert main(["order"]) == UNREACHABLE
    finally:
        db.engine.cache_clear()
    err = capsys.readouterr().err
    assert "make db-up" in err
    assert "pw-must-not-print" not in err and "127.0.0.1" not in err
```

- [ ] **Step 2: Run it.** `uv run pytest services/shared/tests/test_ask.py -q`. Expected: it
      fails with `ModuleNotFoundError: No module named 'thalam_shared.ask'`.

- [ ] **Step 3: Write `services/shared/thalam_shared/ask.py`:**

```python
"""Ask the release graph from the command line (SPEC-002-R12): `make ask Q="before cart-api 2.3"`.

    python -m thalam_shared.ask before <component> <version>
    python -m thalam_shared.ask upstream <component>
    python -m thalam_shared.ask downstream <component>
    python -m thalam_shared.ask order

Reads Postgres as thalam_reader, in one REPEATABLE READ transaction. Prints only names, versions,
ranges, states and dates, which the loader validated; never a description or a summary, which are
free text written by people Thalam must not obey (CLAUDE.md rule 4). Anything typed in that does
not match is echoed through repr(), so a planted terminal escape cannot reach the shell.

Exit codes: 0 answered; 3 answered with blockers, or the needs form a loop; 2 an unknown name or
bad input; 1 Postgres unreachable.
"""

from __future__ import annotations

import sys
from datetime import date

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from thalam_shared.console import utf8_output
from thalam_shared.db import engine
from thalam_shared.env import MissingSetting
from thalam_shared.graph import (
    Answer,
    Graph,
    GraphError,
    UnknownName,
    downstream,
    must_ship_before,
    release_order,
    upstream,
)
from thalam_shared.graph_read import load_graph

ANSWERED, UNREACHABLE, BAD_INPUT, BLOCKED = 0, 1, 2, 3
SHAPES = {"before": 2, "upstream": 1, "downstream": 1, "order": 0}
USAGE = ('usage: make ask Q="before <component> <version>", "upstream <component>", '
         '"downstream <component>" or "order"')


def _window(window: tuple[date, date]) -> str:
    start, end = window
    return start.isoformat() if start == end else f"{start.isoformat()} to {end.isoformat()}"


def _before(a: Answer) -> list[str]:
    t = a.target
    lines = [f"{t.label} · {t.state} · window {_window(t.window)}"]
    if a.steps:
        lines.append("Ship first, in order:")
        for i, s in enumerate(a.steps, 1):
            prod = f"prod runs {s.prod}" if s.prod else "not in prod"
            lines.append(f"  {i}. {s.release.label} · {s.release.state} · "
                         f"{_window(s.release.window)} · {s.needed_by} needs {s.need.spec}, {prod}")
    else:
        lines.append("Ship first: nothing")
    if a.satisfied:
        lines.append("Already satisfied:")
        lines += [f"  - {s.need.component} {s.need.spec} (for {s.needed_by}) · prod runs {s.prod}"
                  for s in a.satisfied]
    if a.blockers:
        lines.append("Blockers:")
        lines += [f"  - {b.needed_by} needs {b.need.component} {b.need.spec}: {b.reason}"
                  for b in a.blockers]
    else:
        lines.append("Blockers: none")
    return lines


def answer(g: Graph, words: list[str]) -> tuple[int, list[str]]:
    """The exit code and the lines to print, for one question about g."""
    if not words or SHAPES.get(words[0]) != len(words) - 1:
        return BAD_INPUT, [USAGE]
    command, args = words[0], words[1:]
    try:
        if command == "before":
            result = must_ship_before(g, args[0], args[1])
            return (BLOCKED if result.blockers else ANSWERED), _before(result)
        if command in ("upstream", "downstream"):
            names = upstream(g, args[0]) if command == "upstream" else downstream(g, args[0])
            return ANSWERED, [f"{command} of {args[0]}:"] + ([f"  - {n}" for n in names]
                                                            or ["  none"])
        rows = [f"  {i}. {r.label} · {r.state} · {_window(r.window)}"
                for i, r in enumerate(release_order(g), 1)]
        return ANSWERED, ["In flight, in a safe order:"] + (rows or ["  none"])
    except (UnknownName, ValueError) as exc:
        return BAD_INPUT, [str(exc)]
    except GraphError as exc:
        return BLOCKED, [str(exc)]


def main(argv: list[str] | None = None) -> int:
    utf8_output()
    words = sys.argv[1:] if argv is None else argv
    if not words or SHAPES.get(words[0]) != len(words) - 1:
        print(USAGE, file=sys.stderr)
        return BAD_INPUT
    try:
        reader = engine("reader").execution_options(isolation_level="REPEATABLE READ")
        with Session(reader) as session, session.begin():
            g = load_graph(session)
    except MissingSetting as exc:
        print(f"set {exc.args[0]} in .env (see .env.example)", file=sys.stderr)
        return BAD_INPUT
    except DBAPIError:
        print("Postgres is not reachable as thalam_reader: run `make db-up`, `make migrate`, "
              "`make db-roles` and `make load`", file=sys.stderr)
        return UNREACHABLE
    code, lines = answer(g, words)
    print("\n".join(lines), file=sys.stdout if code in (ANSWERED, BLOCKED) else sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
```

  `UnknownName` subclasses `LookupError`, not `KeyError`, on purpose. `str()` of a `KeyError`
  wraps its message in quotes, and `str()` of a `LookupError` does not, so the message prints as
  written.

- [ ] **Step 4: The Makefile target.** `make` itself exits 2 when the command fails, so the lab
      reads exit codes from the direct command.

```makefile
.PHONY: ask
ask: ## Ask the release graph, e.g. make ask Q="before cart-api 2.3" (SPEC-002-R12)
	@test -n "$(Q)" || { echo 'usage: make ask Q="before cart-api 2.3"'; exit 2; }
	uv run python -m thalam_shared.ask $(Q)
```

- [ ] **Step 5: Run it.** `uv run pytest services/shared/tests/test_ask.py -q`. Expected: 13
      passed (6 of them from the parametrized bad-input test). Then, with the database up and loaded (`make load`), run
      `make ask Q="before cart-api 2.3"`. Expected: the lines in Lab 01 §6.

- [ ] **Step 6: Story close-out.** Commit subject:
      `feat: THL-<n> make ask: the release graph from the command line (SPEC-002-R12)`.

---

### Task 12 · THL-39: Lab 01 and the Phase 1 docs (SPEC-002-R15, ADR-0015)

**Files:**
- Create: `docs/labs/01-release-graph.md`, `docs/adr/0015-phase-1-shape.md`
- Modify:
  - `docs/specs/SPEC-002-phase-1-release-graph.md`, `ROADMAP.md`;
  - `docs/architecture/overview.md`, `docs/architecture/architecture.toml`;
  - `README.md`, `docs/journal/<today>.md`.

- [ ] **Step 1: Write `docs/labs/01-release-graph.md`:**

````markdown
# Lab 01 — The release graph, local (SPEC-002)

You will run Thalam's Phase 1 on your own machine. Postgres runs in Docker, a fixture company of
8 services is loaded into it, and you will ask what must ship before `cart-api 2.3`. No model is
called, nothing goes to Azure, and it costs ₹0.

Never paste a password, a token or an address into chat or into this file. Evidence below records
only commands, outputs that hold none of those, and the date.

**You need:**
- Docker Desktop, running;
- `uv`, `make` (Git Bash on Windows) and a clone of the repository at `main`.

## 1. Settings in `.env`

Copy `.env.example` to `.env` if you have no `.env` yet. Set these, choosing your own passwords:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=thalam
POSTGRES_USER=thalam
POSTGRES_PASSWORD=<your own>
THALAM_LOADER_PASSWORD=<your own>
THALAM_READER_PASSWORD=<your own>
```

## 2. Postgres — SPEC-002-R1

```bash
make sync
make db-up
```

Expected: `Container thalam-postgres-1  Healthy`. Check that it listens on your machine only with
`docker compose ps --format "{{.Ports}}"`. Expected: `127.0.0.1:5432->5432/tcp`.

**Evidence (SPEC-002-R1):** _not run yet_

## 3. The schema and the two roles — SPEC-002-R3

```bash
make migrate
make db-roles
```

Expected: `Running upgrade  -> 0001`, then `roles ready: thalam_loader, thalam_reader`.

## 4. The reader cannot write — SPEC-002-R3

```bash
uv run python - <<'EOF'
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from thalam_shared.db import engine
try:
    with engine("reader").begin() as c:
        c.execute(text("INSERT INTO calendar_window (name, kind, starts, ends) "
                       "VALUES ('x', 'freeze', '2027-01-01', '2027-01-02')"))
    print("WRITE ALLOWED: stop and report this")
except ProgrammingError as exc:
    print("refused:", getattr(exc.orig, "sqlstate", "?"))
EOF
```

Expected: `refused: 42501` (insufficient privilege).

**Evidence (SPEC-002-R3):** _not run yet_

## 5. Load the fixture company

```bash
make load
make load
```

Expected, the first time:
`loaded: 8 component, 11 dependency, 17 release, 9 release_need, 81 release_event, 14 release_item, 2 calendar_window`.
The second time: `loaded: nothing new`.

## 6. The question — SPEC-002-R15

```bash
make ask Q="before cart-api 2.3"
```

Expected:

```
cart-api 2.3.0 · planned · window 2026-12-08
Ship first, in order:
  1. pricing-svc 1.8.0 · scoped · 2026-12-03 · cart-api 2.3.0 needs >=1.8.0, prod runs 1.7.0
Already satisfied:
  - catalog-svc >=2.5.0 (for cart-api 2.3.0) · prod runs 2.5.0
  - ledger-svc >=4.1.0 (for pricing-svc 1.8.0) · prod runs 4.2.0
  - promo-svc >=1.2.0 (for pricing-svc 1.8.0) · prod runs 1.2.0
Blockers: none
```

Then a blocker, read from the direct command so you see its own exit code:

```bash
uv run python -m thalam_shared.ask before web-shop 5.1; echo "exit $?"
```

Expected: a blocker line, `web-shop 5.1.0 needs catalog-svc >=3.0.0: no release satisfies it`,
then `exit 3`.

**Evidence (SPEC-002-R15):** _not run yet_

## 7. Stop it

```bash
make db-down
```

The data volume stays, so `make db-up` brings the graph back. To drop it, run
`docker compose down -v`.

## 8. If something fails

- **`set POSTGRES_PASSWORD in .env`:** a value in §1 is missing.
- **`Postgres is not reachable`:** Docker Desktop is not running, or §2 was skipped.
- **`problem: <file>: <field>: …`:** a fixture file was edited. Nothing was written. Fix the field
  that is named.
- **Port 5432 already in use:** another Postgres is running. Stop it, or change both
  `POSTGRES_PORT` and `compose.yaml`'s host port.
````

- [ ] **Step 2: Write `docs/adr/0015-phase-1-shape.md`** in the house ADR format
      (`docs/adr/0011-phase-0-shape.md` is the model):
  - **Status:** Accepted, 2026-11-23.
  - **Context:** Phase 1's roadmap list was bigger than its exit gate. Self-hosted Langfuse needs
    ClickHouse, Redis and object storage. The laptop has 15.7 GB of RAM, of which Docker gets
    7.6 GB. Building an image on the x86 laptop would mean emulated arm64 builds. Backstage's
    `dependsOn` carries no versions. Phase 6's DORA metrics need the time of every state change.
  - **Decisions:** the seven answers recorded in SPEC-002's open questions, one line each, plus
    two choices made in Construction:
    - the role grants are what enforce "written once";
    - `release_event` holds both state changes and re-plans.
  - **Rejected:**
    - the full stack and all 13 tables;
    - a gateway in Phase 1;
    - component-level blocking;
    - seeding the sandbox Jira now;
    - recursive SQL and networkx;
    - merging the spec with the code, and placeholder tests.
  - **Consequences:**
    - Phase 2 adds Ollama, Langfuse and `audit_event`;
    - Phase 3 must revisit `release.jira_version_id`, because the executor creates Jira versions
      after a release is planned, while the column is written once;
    - real catalogs with `resource:` dependencies need a rule before Phase 2 reads one.
  - **Revisit if:** a query needs more than one snapshot in memory (thousands of components), or
    Langfuse Cloud's free tier replaces self-hosting (ADR-0004).

- [ ] **Step 3: Amend SPEC-002 to match what was built** (DoD 0):
  - **Header line:** add
    `- **Amended in Construction:** <date>, approved by Roshan. <the list below>`.
  - **Numbers:** "about 25 releases, 60 events and 80 Jira issues" becomes "17 releases, 81 events,
    9 needs, 14 Jira issues and 11 dependencies".
  - **R6:**
    - "is dated before the release's previous event" becomes "is not later than the release's
      previous event";
    - add "a Jira version names no release in the manifests, an issue names an unknown Jira
      version".
  - **R12:** "3 when answered with blockers" becomes "3 when answered with blockers or when the
    needs form a loop".

- [ ] **Step 4: The architecture.**
  - **`docs/architecture/overview.md`'s core-entities table:**
    - the `dependency` row reads "component → component, from Backstage `dependsOn`";
    - add a row for `release_need`: "a release's need of an upstream version range";
    - add a row for `release_event`: "every state change and re-plan, written once".
    - Under the table, add a sentence saying which phase adds each remaining table.
  - **`docs/architecture/architecture.toml`'s `graph` node:** its definition reads "The system of
    record: components, dependencies, releases with their needs and events (written once,
    enforced by grants), Jira items and calendar windows. Later phases add checks, proposals and
    the audit trail."
  - **The `collector` node:** its definition adds "In Phase 1 it reads files: the Backstage
    catalog, release manifests, Jira-shaped JSON and a calendar."
  - **Add this flow:**

```toml
[[flow]]
id = "flow-before"
title = "What must ship before a release"
phase = 1
trigger = "A release manager runs make ask Q=\"before cart-api 2.3\"."
outcome = "The releases to ship first, upstream first, with what prod already satisfies and what nothing can. No model was called and nothing was written."
lanes = [["catalog", "Catalog files"], ["collector", "Collector"], ["graph", "Release graph"], ["people", "Release manager"]]
steps = [
  { from = "collector", to = "catalog", kind = "call", label = "read, check", note = "make load reads the Backstage catalog, the release manifests, the Jira-shaped files and the calendar, and checks them all first. One problem anywhere and nothing is written." },
  { from = "collector", to = "graph", kind = "write", label = "mirror, append", note = "As thalam_loader. The catalog tables follow the files; releases, needs and events are only added, because the role cannot UPDATE or DELETE them." },
  { from = "people", to = "graph", kind = "call", label = "before cart-api 2.3", note = "make ask, as thalam_reader, in one REPEATABLE READ transaction. The role can only read." },
  { from = "graph", to = "people", kind = "return", label = "the order", note = "graphlib orders what must ship first; packaging checks each need's range against what prod runs. Only names, versions, ranges, states and dates are printed." },
]
```

  Run `uv run pytest scripts/tracking -q`. Expected: the architecture tests pass with the new flow.

- [ ] **Step 5: ROADMAP and README.**
  - **ROADMAP:** tick Phase 1's five items. The phase stays `[~]` until Lab 01's evidence is
    recorded.
  - **README:** its status line says "Phase 1: the release graph, local (SPEC-002)". The repository
    map's `evals/` row adds "the fixture company (`evals/company/`, SPEC-002)".

- [ ] **Step 6: Story close-out**, except for setting SPEC-002 to Built. Commit subject:
      `docs: THL-<n> Lab 01, ADR-0015 and the Phase 1 docs (SPEC-002-R15)`.

- [ ] **Step 7: Roshan runs Lab 01** on his laptop. He reports the outputs of §2, §4 and §6 and
      the date, which contain no secrets. Record them under each Evidence heading in place of
      `_not run yet_`, in a `docs: THL-<n>` PR.
  - **That PR also:**
    - sets SPEC-002 to Built and fills its "Measured" section;
    - sets ROADMAP Phase 1 to `[x]`;
    - moves THL-<n> and the epic THL-2 to Done.
  - The spec check fails Built while a lab still says `_not run yet_` (SPEC-001-R8), so this order
    is enforced.

---

## Self-review (done while writing; re-check after any change)

| Requirement | Task | Proof |
|---|---|---|
| R1 compose, digest, localhost, CI same image | 2 | `scripts/dev/test_compose.py`, Lab 01 §2 |
| R2 seven tables, `alembic check`, round trip | 3 | `services/shared/tests/test_migrations.py`, CI steps |
| R3 the reader reads only; the loader cannot change history | 4 | `services/shared/tests/test_db_roles.py`, Lab 01 §4 |
| R4 the catalog: `safe_load_all`, names, owner, dependsOn, cap; the mirror | 6, 8 | `services/collector/tests/test_catalog.py` |
| R5 manifests (strict), ranges, Jira (loose), summaries capped, calendar | 7 | `services/collector/tests/test_releases.py` |
| R6 fails closed, naming the file and field; history rewrite refused | 7, 8 | `services/collector/tests/test_load.py` |
| R7 idempotent, append-only, the drift warning | 8 | `services/collector/tests/test_load.py` |
| R8 the database read equals the files' graph, as the reader | 10 | `services/shared/tests/test_graph_read.py` |
| R9 upstream, downstream, prod version | 5 | `services/shared/tests/test_graph.py` |
| R10 must ship before: satisfied, lowest in flight, blockers, retired, loop | 5 | `services/shared/tests/test_graph.py` |
| R11 release order | 5 | `services/shared/tests/test_graph.py` |
| R12 the CLI's commands, reader role, validated fields, exit codes | 11 | `services/shared/tests/test_ask.py` |
| R13 the fixture company's scenarios, `xxxx` hosts | 9 | `services/collector/tests/test_fixture_company.py` |
| R14 CI's Postgres, fail-not-skip, importlib | 1, 3 | `services/shared/tests/test_db_guard.py`, `ci.yml` |
| R15 Lab 01 from a clean clone | 12 | `docs/labs/01-release-graph.md` |

**Names used across tasks, checked:**
- **`lifecycle`:** `STATES`, `NOT_IN_FLIGHT`, `allowed`, `Event`, `current`.
- **`graph`:** `Component`, `Need(component, spec)`, `Release.label` / `.in_flight`, `Window`,
  `Graph`, `make_graph`, `parse_version`, `parse_range`, `upstream`, `downstream`, `prod_version`,
  `release`, `must_ship_before`, `release_order`, `Answer`, `Step`, `Satisfied`, `Blocker`,
  `GraphError`, `UnknownName`.
- **`company`:** `read_company`, `to_graph`, `SUMMARY_CAP`.
- **`load`:** `load`, `TABLES`, `Report`.
- **`db_roles`:** `apply`.
- **`db`:** `engine`, `database_url`.
- **`env`:** `setting`, `MissingSetting`.
- **Fixtures:** `migrated_engine`, `db`, `as_role`, `company_tree`.
