"""The hardened readers every company-folder file goes through (SPEC-002-R6).

Untrusted text (CLAUDE.md rule 4): a safe loader only, a size cap, and every failure turned
into a Problem that names the file. Nothing a file contains may raise out of read_yaml or
read_json.
"""

from __future__ import annotations

import json
from collections.abc import Hashable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from yaml.nodes import MappingNode

from thalam_collector.problems import Problem
from thalam_collector.text import shown

MAX_FILE_BYTES = 1_048_576  # pure-Python PyYAML took 83 s on a 4 MB file

# libyaml's parser when PyYAML was built with it (about ten times faster), otherwise the pure-
# Python one. Both are safe loaders: neither builds a Python object from a tag. Their error text
# differs, so nothing here or in a test may depend on the wording after the line number.
if TYPE_CHECKING:
    _Base = yaml.SafeLoader
else:
    _Base = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class _DuplicateKey(Exception):
    """A mapping repeats a key; the last value would silently win. Carries what to say."""

    def __init__(self, key: object, line: int | None) -> None:
        super().__init__()
        self.key = key
        self.line = line


class _Loader(_Base):
    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        """Refuse a repeated literal key. A `<<` merge key is not literal, so merges stay legal."""
        seen: set[object] = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=True)
            try:
                repeated = key in seen
            except TypeError:  # an unhashable key: the base class refuses it, with its own error
                continue
            if repeated:
                raise _DuplicateKey(key, key_node.start_mark.line + 1)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _no_repeated_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise _DuplicateKey(key, None)
        out[key] = value
    return out


# Never walk, copy, repr or serialise a whole raw document. YAML aliases are shared objects, so
# walking one can blow up (a "billion laughs" file); only validated fields are ever read.
# Never echo str(exc) of a non-YAML error: int()'s message, for one, quotes the input.
def read_yaml(path: Path, rel: str) -> tuple[list[Any], list[Problem]]:
    """Every document in one file, or no documents and one Problem. MemoryError is not caught.

    A mapping that repeats a key is a Problem, not a silent last-wins.
    """

    def fail(message: str) -> tuple[list[Any], list[Problem]]:
        return [], [Problem(rel, "(file)", message)]

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return fail("larger than 1 MiB")
        return list(yaml.load_all(path.read_text(encoding="utf-8"), Loader=_Loader)), []
    except UnicodeDecodeError:
        return fail("not UTF-8")
    except _DuplicateKey as exc:
        return fail(f"duplicate key {shown(exc.key, 60)} at line {exc.line}")
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
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_no_repeated_keys), []
    except UnicodeDecodeError:
        return fail("not UTF-8")
    except _DuplicateKey as exc:
        return fail(f"duplicate key {shown(exc.key, 60)}")
    except json.JSONDecodeError as exc:
        return fail(f"not valid JSON at line {exc.lineno}: {shown(exc.msg, 200)}")
    except OSError as exc:
        return fail(f"unreadable: {type(exc).__name__}")
    except MemoryError:
        raise
    except Exception as exc:  # RecursionError, ValueError (an integer too long to read), ...
        return fail(f"not valid JSON: a value could not be read ({type(exc).__name__})")
