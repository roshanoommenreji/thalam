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
