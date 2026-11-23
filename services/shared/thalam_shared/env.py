"""Settings by name: the environment first, then .env, for that one name only (SPEC-002).

Thalam's Makefile never sources .env (scripts/ops/tf.py's rule): exporting all of it would hand
every Jira, ServiceNow and Foundry secret to every command. A caller asks for the names it needs.
Values are returned to the caller, never printed here. .env is read the same way as
scripts/dev/check_sandboxes.py reads it, and an empty value counts as unset.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class MissingSetting(KeyError):
    """The setting is in neither the environment nor .env; args[0] is its name."""


def _clean_value(raw: str) -> str:
    value = raw.strip()
    if value[:1] in ("\"", "'"):
        end = value.find(value[0], 1)
        return value[1:end] if end != -1 else value[1:]
    return re.split(r"(?:^|\s)#", raw, maxsplit=1)[0].strip()


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[re.sub(r"^export\s+", "", key.strip())] = _clean_value(value)
    return values


def setting(name: str, env_file: Path = ENV_FILE) -> str:
    if os.environ.get(name):
        return os.environ[name]
    try:
        values = _parse(env_file.read_text(encoding="utf-8-sig"))  # PowerShell 5.1 adds a BOM
    except FileNotFoundError:
        values = {}
    if values.get(name):
        return values[name]
    raise MissingSetting(name)
