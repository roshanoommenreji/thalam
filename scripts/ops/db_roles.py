#!/usr/bin/env python3
"""Create or update thalam_loader and thalam_reader (SPEC-002-R3): `make db-roles`.

Runs scripts/ops/db-roles.sql as the owner. THALAM_LOADER_PASSWORD and THALAM_READER_PASSWORD
come from the environment, then .env. What is guaranteed about them:
  - the plaintext never leaves this process: libpq computes each SCRAM-SHA-256 verifier here, and
    only the verifier is sent, as a bound parameter, and put in the statements the server logs;
  - the script keeps statement text out of the errors it raises (see db-roles.sql);
  - main() prints the error's class, its SQLSTATE and Postgres's primary message, which never
    includes the statement, and no traceback.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError, OperationalError
from thalam_shared.db import engine
from thalam_shared.env import MissingSetting, setting

SQL = Path(__file__).with_name("db-roles.sql")


def apply(connection: Connection, loader_password: str, reader_password: str) -> None:
    """Run the roles script inside the caller's transaction (tests roll it back)."""
    raw = connection.connection.driver_connection
    if raw is None:
        raise RuntimeError("no DBAPI connection")
    for name, value in (("loader", loader_password), ("reader", reader_password)):
        # Computed here: the server, and so its log, only ever sees the verifier.
        verifier = raw.pgconn.encrypt_password(
            value.encode(), f"thalam_{name}".encode(), b"scram-sha-256").decode()
        # is_local=true: the setting lasts for this transaction only.
        connection.execute(text(f"SELECT set_config('thalam.{name}_verifier', :v, true)"),
                           {"v": verifier})
    # No parameters, so psycopg sends the script as is: several statements, % signs untouched.
    with raw.cursor() as cursor:
        cursor.execute(SQL.read_text(encoding="utf-8"))


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
    except (DBAPIError, psycopg.Error) as exc:
        # Not str(exc): that carries CONTEXT, which can hold SQL text. message_primary never does.
        original = exc.orig if isinstance(exc, DBAPIError) else exc
        state = getattr(original, "sqlstate", None)
        diag = getattr(original, "diag", None)
        message = (diag.message_primary if diag is not None else None) or ""
        hint = ": run `make migrate` first" if state == "42P01" else ""
        print(f"db-roles failed: {type(original).__name__}, SQLSTATE {state}{hint}"
              f"{': ' + message if message else ''}", file=sys.stderr)
        return 1
    print("roles ready: thalam_loader, thalam_reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
