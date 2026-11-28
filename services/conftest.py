"""Fixtures for every service's tests (SPEC-002-R14). Copied from Kaval's services/conftest.py.

A test that needs Postgres asks for `db`: the owner role, inside one transaction that is rolled
back at the end, so nothing persists. Without a reachable, migrated database the test skips and
says why; CI sets THALAM_REQUIRE_DB=1, which turns that skip into a failure, so a database test can
never vanish from a green run (Kaval KAV-24).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NoReturn

import db_roles
import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from thalam_shared.db import engine
from thalam_shared.env import MissingSetting
from thalam_shared.models import Base

REQUIRE = "THALAM_REQUIRE_DB"
ROOT = Path(__file__).resolve().parents[1]


def no_database(reason: str) -> NoReturn:
    if os.environ.get(REQUIRE) == "1":
        pytest.fail(f"{reason} ({REQUIRE}=1, so this fails rather than skips)", pytrace=False)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def migrated_engine() -> Engine:
    """Probed once per run, because each failed connection costs connect_timeout times the
    addresses `localhost` resolves to (::1 first on Windows). POSTGRES_HOST=127.0.0.1 avoids that.

    The database must be at the migration head: `alembic downgrade base` leaves an empty
    alembic_version table, and a database behind a newer migration would also pass a bare probe."""
    try:
        owner = engine("owner")
        with owner.connect() as probe:
            version = probe.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except (DBAPIError, MissingSetting) as exc:
        no_database(f"no reachable, migrated Postgres: {type(exc).__name__}")
    # Not from_config: alembic.ini's prepend_sys_path would put "." on this process's sys.path.
    head = ScriptDirectory(str(ROOT / "migrations")).get_current_head()
    if version != head:
        no_database("Postgres is not at the migration head: run make migrate")
    return owner


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Session]:
    """One test, one outer transaction, rolled back at teardown. The code under test's own
    commits become SAVEPOINTs (`join_transaction_mode`), so nothing persists either way.

    Every test starts from empty tables: the TRUNCATE runs inside the same transaction and is
    rolled back with it. A database that holds Lab 01's data still passes and keeps that data
    (the plan's dry run found tests failing after a real `make load`).

    The TRUNCATE holds ACCESS EXCLUSIVE locks until the rollback, so a test must not open a second
    connection (e.g. engine("reader")) to these tables: it would wait forever."""
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


ROLES = ("thalam_loader", "thalam_reader")


@pytest.fixture
def as_role(db: Session) -> Callable[[str | None], Session]:
    """The real roles script, applied inside the test's transaction (rolled back with it); then
    `as_role("thalam_reader")` acts as that role until `as_role(None)` returns to the owner.

    If the code under test calls session.rollback(), the savepoint rollback undoes SET LOCAL ROLE
    and later statements run as the owner: a test must not rely on a rollback inside a switch."""
    db_roles.apply(db.connection(), "test-loader", "test-reader")

    def switch(role: str | None) -> Session:
        assert role is None or role in ROLES
        db.execute(text("RESET ROLE" if role is None else f"SET LOCAL ROLE {role}"))
        return db

    return switch


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
