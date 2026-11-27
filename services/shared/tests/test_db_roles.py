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
