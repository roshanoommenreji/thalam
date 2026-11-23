"""compose.yaml runs Postgres only: pinned, local-only, nothing built (SPEC-002-R1)."""
# covers: SPEC-002-R1

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PINNED = re.compile(r"^pgvector/pgvector:[\w.-]+@sha256:[0-9a-f]{64}$")


def _yaml(path: str) -> dict[str, Any]:
    data = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


COMPOSE = _yaml("compose.yaml")
POSTGRES = COMPOSE["services"]["postgres"]


def test_postgres_is_the_only_service() -> None:
    assert list(COMPOSE["services"]) == ["postgres"]


def test_the_image_is_pinned_by_digest() -> None:
    assert PINNED.match(POSTGRES["image"])


def test_nothing_is_built() -> None:
    assert all("build" not in service for service in COMPOSE["services"].values())


def test_the_port_listens_on_localhost_only() -> None:
    assert POSTGRES["ports"] == ["127.0.0.1:5432:5432"]
    assert "network_mode" not in POSTGRES  # host networking would bypass the binding


def test_every_credential_must_be_set() -> None:
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        assert POSTGRES["environment"][name].startswith("${" + name + ":?")


def test_ci_runs_the_same_image() -> None:
    ci = _yaml(".github/workflows/ci.yml")
    assert ci["jobs"]["test"]["services"]["postgres"]["image"] == POSTGRES["image"]
