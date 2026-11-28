"""The hardened readers every company-folder file goes through (SPEC-002-R6).

Untrusted text (CLAUDE.md rule 4): yaml.safe_load_all only, a size cap, and every failure turned
into a Problem that names the file. Nothing a file contains may raise out of read_yaml or
read_json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from thalam_collector.problems import Problem
from thalam_collector.text import shown

MAX_FILE_BYTES = 1_048_576  # pure-Python PyYAML took 83 s on a 4 MB file


# Never walk, copy, repr or serialise a whole raw document. YAML aliases are shared objects, so
# walking one can blow up (a "billion laughs" file); only validated fields are ever read.
# Never echo str(exc) of a non-YAML error: int()'s message, for one, quotes the input.
def read_yaml(path: Path, rel: str) -> tuple[list[Any], list[Problem]]:
    """Every document in one file, or no documents and one Problem. MemoryError is not caught."""

    def fail(message: str) -> tuple[list[Any], list[Problem]]:
        return [], [Problem(rel, "(file)", message)]

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return fail("larger than 1 MiB")
        return list(yaml.safe_load_all(path.read_text(encoding="utf-8"))), []
    except UnicodeDecodeError:
        return fail("not UTF-8")
    except yaml.MarkedYAMLError as exc:
        text = str(exc.problem or exc.context or type(exc).__name__)[:200]
        if exc.problem_mark is None:
            return fail(f"not valid YAML: {text!r}")
        return fail(f"not valid YAML at line {exc.problem_mark.line + 1}: {text!r}")
    except yaml.YAMLError as exc:
        return fail(f"not valid YAML: {type(exc).__name__}")
    except OSError as exc:
        return fail(f"unreadable: {type(exc).__name__}")
    except MemoryError:
        raise
    except Exception as exc:  # ValueError, RecursionError, and whatever a tag constructor raises
        return fail(f"not valid YAML: a value could not be read ({type(exc).__name__})")


def read_json(path: Path, rel: str) -> tuple[Any, list[Problem]]:
    """The one JSON value in a file, or None and one Problem. MemoryError is not caught.

    Same rules as read_yaml: a size cap, and never str(exc), whose message may quote the input.
    json's own `msg` is a fixed phrase such as "Expecting value", so it is safe to show.
    """

    def fail(message: str) -> tuple[Any, list[Problem]]:
        return None, [Problem(rel, "(file)", message)]

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return fail("larger than 1 MiB")
        return json.loads(path.read_text(encoding="utf-8")), []
    except UnicodeDecodeError:
        return fail("not UTF-8")
    except json.JSONDecodeError as exc:
        return fail(f"not valid JSON at line {exc.lineno}: {shown(exc.msg, 200)}")
    except OSError as exc:
        return fail(f"unreadable: {type(exc).__name__}")
    except MemoryError:
        raise
    except Exception as exc:  # RecursionError, ValueError (an integer too long to read), ...
        return fail(f"not valid JSON: a value could not be read ({type(exc).__name__})")
