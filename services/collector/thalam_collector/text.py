"""The one place untrusted text is flattened and quoted (CLAUDE.md rule 4, SPEC-002-R6).

flatten() is for text that is stored (a Jira summary, a catalog description) and for names built
into a problem's field; shown() is for a file's value that appears in a Problem message.
"""

from __future__ import annotations

import re
import unicodedata

# Unicode categories that become part of a run collapsing to one space: control characters
# (C0, DEL, C1), format characters (zero-width characters, the bidi controls that reorder text
# when it is printed, LRM and RLM, and the Tag block U+E0000 to U+E007F, which carries invisible
# text a model can still read), lone surrogates, and every kind of space or line separator.
#
# One exception, because it is spelling: a single zero-width joiner or non-joiner (U+200D, U+200C)
# after a letter or a mark, as in a Malayalam chillu or a Persian word. See _spells_a_word.
_UNSAFE = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp", "Zs"})
_JOINERS = frozenset({"\u200c", "\u200d"})
_JOINER_RUN = re.compile("[\u200c\u200d]+")


class _Table(dict[int, str]):
    """The table str.translate reads: an unsafe character maps to a space, any other to itself.

    A joiner maps to itself here; flatten() decides about each one afterwards, because that needs
    the characters around it. The table fills as translate asks, so a text costs one category
    lookup per distinct character, not per character, and each flatten() builds its own, so
    nothing accumulates between calls.
    """

    def __missing__(self, code: int) -> str:
        ch = chr(code)
        out = " " if unicodedata.category(ch) in _UNSAFE and ch not in _JOINERS else ch
        self[code] = out
        return out


def _spells_a_word(text: str, i: int) -> bool:
    """Whether the single joiner at text[i] is spelling: a letter or mark before, nothing odd after.

    A Malayalam chillu is na, virama, ZWJ; Persian writes a ZWNJ between the letters of a word.
    Flattening either splits the word, so one joiner after a letter or a mark is kept. Everything
    is judged in the original text: a joiner after a space, an emoji, a digit or the start, or
    next to another invisible character, is not kept, and the run-length channel (hidden data
    written as runs of joiners) stays closed. flatten() flattens every run of two or more itself.

    The known limit: one joiner after a letter can still carry one bit. The Tag block, which
    models read as text, is what the rule exists to close.
    """
    if i == 0 or unicodedata.category(text[i - 1])[0] not in "LM":
        return False
    if i + 1 == len(text):
        return True
    after = text[i + 1]
    # Whitespace collapses to a space anyway, so a chillu before one is safe: its length is lost.
    return unicodedata.category(after) not in _UNSAFE or after.isspace()


def flatten(text: str, cap: int) -> str:
    """One line of plain text, at most `cap` characters, with no leading or trailing space.

    Every run of whitespace or of unsafe characters becomes one space, except a single joiner that
    spells a word (_spells_a_word). In an emoji sequence a joiner follows an emoji, so flattening
    splits the sequence: that is accepted. (One that follows a variation selector, which is a mark,
    is kept.)
    """
    spaced = text.translate(_Table())  # the same length as text, so a position means the same
    pieces: list[str] = []
    done = 0
    for run in _JOINER_RUN.finditer(text):
        start, end = run.span()
        if end - start == 1 and _spells_a_word(text, start):
            continue
        pieces += [spaced[done:start], " " * (end - start)]
        done = end
    if pieces:
        spaced = "".join(pieces) + spaced[done:]
    return " ".join(spaced.split())[:cap].rstrip()


def shown(value: object, cap: int = 80) -> str:
    """repr() of a file's value for a message, cut to `cap` characters with an ellipsis."""
    out = repr(value)
    return out if len(out) <= cap else out[: cap - 1] + "…"
