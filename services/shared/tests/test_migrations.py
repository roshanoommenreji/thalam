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
from sqlalchemy import Connection, Engine, inspect, text
from sqlalchemy.orm import Session
from thalam_shared.models import Base

ROOT = Path(__file__).resolve().parents[3]
TABLES = {"component", "dependency", "release", "release_need", "release_event", "release_item",
          "calendar_window"}
# `alembic check` and compare_metadata never compare CHECK constraints, so a migration whose CHECK
# differs from its model passes both. This reads every CHECK's definition from Postgres instead.
CHECKS = text(
    "SELECT c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid)"
    " FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace"
    " WHERE c.contype = 'c' AND n.nspname = :schema"
)


def test_the_seven_tables_and_nothing_else(migrated_engine: Engine) -> None:
    assert set(inspect(migrated_engine).get_table_names()) == TABLES | {"alembic_version"}


def test_the_models_and_the_migrations_agree(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_server_default": True})
        assert compare_metadata(context, Base.metadata) == []


def _checks(connection: Connection, schema: str) -> dict[tuple[str, str], str]:
    rows = connection.execute(CHECKS, {"schema": schema})
    return {(table.rsplit(".", 1)[-1], name): definition for table, name, definition in rows}


def test_the_check_constraints_and_the_models_agree(db: Session) -> None:
    connection = db.connection()
    migrated = _checks(connection, "public")
    assert migrated, "no CHECK constraints found in public: the comparison would prove nothing"
    # Same transaction as the `db` fixture, so the probe schema is rolled back with it.
    connection.execute(text("CREATE SCHEMA drift_probe"))
    connection.execute(text("SET LOCAL search_path TO drift_probe"))
    Base.metadata.create_all(connection, checkfirst=False)
    assert _checks(connection, "drift_probe") == migrated


def test_every_migration_can_be_reversed() -> None:
    for path in sorted((ROOT / "migrations" / "versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert re.search(r"def downgrade\(\) -> None:\n(?!\s+pass\b)", text), path.name
