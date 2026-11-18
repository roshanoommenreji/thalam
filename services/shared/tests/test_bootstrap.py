"""The empty package installs from the lock and imports (SPEC-001-R3)."""
# covers: SPEC-001-R3

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_package_imports_and_reports_the_project_version() -> None:
    import thalam_shared

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert thalam_shared.__version__ == project["version"]
