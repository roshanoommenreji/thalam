"""A database test never vanishes from CI (SPEC-002-R14).

Runs a real database test in a child pytest pointed at a closed port: without THALAM_REQUIRE_DB
it skips and says why; with THALAM_REQUIRE_DB=1 (as in CI) it fails.
"""
# covers: SPEC-002-R14

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = "services/shared/tests/test_migrations.py::test_the_seven_tables_and_nothing_else"


def _run(require: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "9", "POSTGRES_DB": "x",
           "POSTGRES_USER": "x", "POSTGRES_PASSWORD": "x", "THALAM_REQUIRE_DB": require}
    return subprocess.run(
        [sys.executable, "-m", "pytest", TARGET, "-q", "-p", "no:cacheprovider", "-rs"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
    )


def test_without_the_flag_a_database_test_skips_and_says_why() -> None:
    result = _run("0")
    assert result.returncode == 0, result.stdout
    assert "no reachable, migrated Postgres" in result.stdout


def test_with_the_flag_a_database_test_fails() -> None:
    result = _run("1")
    assert result.returncode == 1, result.stdout
    assert "THALAM_REQUIRE_DB=1, so this fails rather than skips" in result.stdout
