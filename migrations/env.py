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
