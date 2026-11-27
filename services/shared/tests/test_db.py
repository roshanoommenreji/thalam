"""Database errors never carry the values bound to the statement (plumbing for db.py's engines).

Task 4 binds role passwords and Task 8 binds untrusted text; SQLAlchemy prints bound values in its
error messages unless the engine says hide_parameters.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


def test_an_error_does_not_print_the_bound_values(db: Session) -> None:
    with pytest.raises(DBAPIError) as excinfo:
        db.execute(text("SELECT CAST(:v AS text), 1/0"), {"v": "bound-value-xyz"})
    assert "bound-value-xyz" not in str(excinfo.value)
    assert "division by zero" in str(excinfo.value)
