"""Fixtures for every service's tests (SPEC-002-R14). Copied from Kaval's services/conftest.py.

A test that needs Postgres asks for `db`: the owner role, inside one transaction that is rolled
back at the end, so nothing persists. Without a reachable, migrated database the test skips and
says why; CI sets THALAM_REQUIRE_DB=1, which turns that skip into a failure, so a database test can
never vanish from a green run (Kaval KAV-24).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

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
