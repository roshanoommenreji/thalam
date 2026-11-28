"""The one place untrusted text is flattened and quoted (CLAUDE.md rule 4)."""
# covers: SPEC-002-R6

from __future__ import annotations

from thalam_collector.text import flatten, shown


def test_flatten_turns_every_unsafe_run_into_one_space() -> None:
    # NUL, ESC and DEL are control characters; U+2028 and U+2029 separate lines; U+202E and
    # U+2066 are bidi controls that reorder text when printed; a lone surrogate cannot be encoded.
    raw = "a\x00b\x1bc\x7fd e f\u202Eg\u2066h\ud800i \t\n j"
    assert flatten(raw, 200) == "a b c d e f g h i j"


def test_flatten_strips_cuts_and_strips_again() -> None:
    assert flatten("  hello world  ", 200) == "hello world"
    assert flatten("hello world", 6) == "hello"  # the cut leaves a space, which is removed


def test_shown_is_a_capped_repr() -> None:
    assert shown("abc") == "'abc'"
    assert shown(12) == "12"
    out = shown("x" * 5000)
    assert len(out) == 80 and out.endswith("…")
    assert shown("x" * 100, cap=10) == "'xxxxxxxx…"
