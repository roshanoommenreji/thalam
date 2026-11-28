"""The one place untrusted text is flattened and quoted (CLAUDE.md rule 4, SPEC-002-R6).

flatten() is for text that is stored (a Jira summary, a catalog description) and for names built
into a problem's field; shown() is for a file's value that appears in a Problem message.
"""

from __future__ import annotations

import unicodedata

# Unicode categories that become part of a run collapsing to one space: control characters
# (C0, DEL, C1), format characters (zero-width characters, the bidi controls that reorder text
# when it is printed, LRM and RLM, and the Tag block U+E0000 to U+E007F, which carries invisible
# text a model can still read), lone surrogates, and every kind of space or line separator.
_UNSAFE = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp", "Zs"})


def flatten(text: str, cap: int) -> str:
    """One line of plain text, at most `cap` characters, with no leading or trailing space.

    Every run of whitespace or of unsafe characters becomes one space. A zero-width joiner inside
    an emoji sequence is one of them, so flattening splits the sequence: that is accepted.
    """
    spaced = "".join(" " if unicodedata.category(ch) in _UNSAFE else ch for ch in text)
    return " ".join(spaced.split())[:cap].rstrip()


def shown(value: object, cap: int = 80) -> str:
    """repr() of a file's value for a message, cut to `cap` characters with an ellipsis."""
    out = repr(value)
    return out if len(out) <= cap else out[: cap - 1] + "…"
