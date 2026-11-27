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
    # hide_parameters: errors otherwise print bound values (role passwords, untrusted text).
    return create_engine(
        database_url(role),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )
