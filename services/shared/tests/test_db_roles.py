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
import psycopg
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session
from thalam_shared import models
from thalam_shared.db import Role, engine
from thalam_shared.env import MissingSetting

Switch = Callable[[str | None], Session]
COLUMN = {"component": "name", "dependency": "src_id", "release": "version",
          "release_need": "spec", "release_event": "kind", "release_item": "summary",
          "calendar_window": "name"}
ROLE_NAMES = ("thalam_loader", "thalam_reader")
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
            "delete": f"DELETE FROM {table}",
            "truncate": f"TRUNCATE {table}"}


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
    for kind in ("update", "delete", "truncate"):
        assert not _may(db, as_role, "thalam_loader", statements[kind]), (table, kind)


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
    # A component's identity is its name: renaming would move a release to another component.
    assert not _may(db, as_role, "thalam_loader", "UPDATE component SET name = name")


def test_the_script_can_run_twice(as_role: Switch) -> None:
    db = as_role(None)
    db_roles.apply(db.connection(), "again-loader", "again-reader")
    rows = db.execute(text("SELECT rolname, rolcanlogin, rolconfig FROM pg_roles "
                           "WHERE rolname IN ('thalam_loader', 'thalam_reader')")).all()
    assert {r.rolname for r in rows} == set(ROLE_NAMES)
    assert all(r.rolcanlogin for r in rows)
    reader = next(r for r in rows if r.rolname == "thalam_reader")
    assert "default_transaction_read_only=on" in (reader.rolconfig or [])


def test_every_table_gets_a_grant_decision() -> None:
    # A new table must be added to COLUMN (and so to the reader and loader tests above).
    assert set(COLUMN) == {t.name for t in models.Base.metadata.sorted_tables}


def test_a_failing_script_leaves_no_password_in_the_error(as_role: Switch) -> None:
    """The reader may not alter roles, so the script fails. PL/pgSQL puts the failed statement,
    `ALTER ROLE ... PASSWORD '...'`, in the error CONTEXT unless it is kept out."""
    db = as_role(None)
    with pytest.raises(psycopg.Error) as caught, db.begin_nested():
        as_role("thalam_reader")
        db_roles.apply(db.connection(), "leak-probe-loader", "leak-probe-reader")
    as_role(None)
    # Pin the cause: an unrelated earlier failure would also leave no password in its message.
    assert caught.value.sqlstate == "42501"  # insufficient_privilege: the reader cannot ALTER ROLE
    assert (caught.value.diag.message_primary or "").startswith("thalam_loader: ")
    message = str(caught.value)
    assert "leak-probe" not in message
    assert "SCRAM-SHA-256$" not in message


def test_each_role_can_log_in(migrated_engine: Engine) -> None:
    """SET ROLE skips LOGIN, the password, pg_hba and the role's own settings: log in for real.
    Not the `db` fixture: its TRUNCATE locks would block a second connection."""
    logins: tuple[tuple[Role, str], ...] = (
        ("reader", "thalam_reader"), ("loader", "thalam_loader"))
    for role, user in logins:
        try:
            with engine(role).connect() as connection:
                assert connection.execute(text("SELECT current_user")).scalar() == user
                if role == "reader":
                    assert connection.execute(
                        text("SHOW default_transaction_read_only")).scalar() == "on"
                with pytest.raises(DBAPIError) as refused:
                    connection.execute(text("CREATE TEMP TABLE t (x int)"))
                state = getattr(refused.value.orig, "sqlstate", None)
                # The reader is refused as read-only first (25006); only the loader, which is
                # not read-only, proves the REVOKE of TEMPORARY from PUBLIC: exactly 42501.
                assert state in ("25006", "42501") if role == "reader" else state == "42501"
                connection.rollback()
        except MissingSetting as exc:
            pytest.fail(f"set {exc.args[0]} in .env (see .env.example)")
        except OperationalError:
            pytest.fail(f"cannot log in as {user}: run `make db-roles` with the passwords in .env")
