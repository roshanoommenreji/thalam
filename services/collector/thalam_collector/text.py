"""The one place untrusted text is flattened and quoted (CLAUDE.md rule 4, SPEC-002-R6).

flatten() is for text that is stored (a Jira summary, a catalog description); shown() is for a
file's value that appears in a Problem message. Both are written with escapes, never with literal
invisible characters, so a reviewer can see what is in the set.
"""

from __future__ import annotations

import re

# One space replaces each run of: control characters (C0, DEL, C1), lone surrogates, the line and
# paragraph separators U+2028 and U+2029, the bidi controls U+202A-U+202E and U+2066-U+2069 (they
# reorder text when it is printed), and whitespace of every kind.
_FLATTEN = re.compile(
    "[\\x00-\\x1f\\x7f-\\x9f\\ud800-\\udfff\\u2028\\u2029\\u202a-\\u202e\\u2066-\\u2069\\s]+")


def flatten(text: str, cap: int) -> str:
    """One line of plain text, at most `cap` characters, with no leading or trailing space."""
    return _FLATTEN.sub(" ", text).strip()[:cap].rstrip()


def shown(value: object, cap: int = 80) -> str:
    """repr() of a file's value for a message, cut to `cap` characters with an ellipsis."""
    out = repr(value)
    return out if len(out) <= cap else out[: cap - 1] + "…"
