"""Settings by name: the environment first, then .env, for that one name only (SPEC-002).

Thalam's Makefile never sources .env (scripts/ops/tf.py's rule): exporting all of it would hand
every Jira, ServiceNow and Foundry secret to every command. A caller asks for the names it needs.
Values are returned to the caller, never printed here.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class MissingSetting(KeyError):
    """The setting is in neither the environment nor .env; args[0] is its name."""


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


def setting(name: str, env_file: Path = ENV_FILE) -> str:
    if name in os.environ:
        return os.environ[name]
    try:
        values = _parse(env_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        values = {}
    if name in values:
        return values[name]
    raise MissingSetting(name)
