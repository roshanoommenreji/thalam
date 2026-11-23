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
