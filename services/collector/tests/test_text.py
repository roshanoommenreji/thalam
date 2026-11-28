"""The one place untrusted text is flattened and quoted (CLAUDE.md rule 4)."""
# covers: SPEC-002-R6

from __future__ import annotations

import time

import pytest
from thalam_collector.text import flatten, shown


def test_flatten_turns_every_unsafe_run_into_one_space() -> None:
    # NUL, ESC and DEL are control characters; U+2028 and U+2029 separate lines; U+202E and
    # U+2066 are bidi controls that reorder text when printed; a lone surrogate cannot be encoded.
    raw = "a\x00b\x1bc\x7fd\u2028e\u2029f\u202eg\u2066h\ud800i \t\n j"
    assert flatten(raw, 200) == "a b c d e f g h i j"


def test_flatten_strips_cuts_and_strips_again() -> None:
    assert flatten("  hello world  ", 200) == "hello world"
    assert flatten("hello world", 6) == "hello"  # the cut leaves a space, which is removed


@pytest.mark.parametrize("invisible", [
    "\u200b",  # zero-width space
    "\u2060",  # word joiner
    "\u00ad",  # soft hyphen
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
    "\ufeff",  # byte order mark
    "\U000e0041",  # a Tag-block character: invisible text a model could still read
    "\U000e007f",  # the last of the Tag block
    "\ud800",  # a lone surrogate
    "\u00a0",  # a no-break space
    "\u3000",  # an ideographic space
])
def test_an_invisible_character_inside_a_word_becomes_one_space(invisible: str) -> None:
    assert flatten(f"a{invisible}b", 200) == "a b"
    assert flatten(f"a{invisible}{invisible}b", 200) == "a b"


def test_visible_text_survives_including_non_latin_scripts() -> None:
    assert flatten("Zahlung für താളം 汉字", 200) == (
        "Zahlung für താളം 汉字")


# --- A joiner is spelling in Indic and Persian words, so one after a letter stays ---

ZWJ = "\u200d"  # zero-width joiner
ZWNJ = "\u200c"  # zero-width non-joiner
CHILLU = "\u0d28\u0d4d\u200d"  # Malayalam: na, virama, ZWJ spell the chillu letter "n"
PERSIAN = "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645"  # "mikhaham": a ZWNJ between letters
MA = "\u0d2e"  # Malayalam ma, a letter that can follow a chillu


@pytest.mark.parametrize("text", [
    pytest.param(CHILLU, id="chillu-alone"),
    pytest.param(f"അ{CHILLU}", id="chillu-at-the-end-of-a-word"),
    pytest.param(f"{CHILLU} {MA}", id="chillu-before-a-space"),
    pytest.param(f"അ{CHILLU}{MA}", id="chillu-in-the-middle-of-a-word"),
    pytest.param(PERSIAN, id="persian"),
    pytest.param(f"{PERSIAN} {PERSIAN}", id="persian-twice"),
    pytest.param(f"a{ZWJ}b", id="zwj-between-letters"),
    pytest.param(f"a{ZWNJ}b", id="zwnj-between-letters"),
])
def test_a_joiner_that_spells_a_word_is_kept(text: str) -> None:
    assert flatten(text, 200) == text


def test_a_joiner_before_whitespace_that_collapses_anyway_is_kept() -> None:
    assert flatten(f"{CHILLU}\n\n{MA}", 200) == f"{CHILLU} {MA}"
    assert flatten(f"{CHILLU}\u00a0{MA}", 200) == f"{CHILLU} {MA}"


@pytest.mark.parametrize("joiner", [ZWJ, ZWNJ], ids=["zwj", "zwnj"])
@pytest.mark.parametrize(("text", "expected"), [
    pytest.param("{j}b", "b", id="at-the-start"),
    pytest.param("a {j}b", "a b", id="after-a-space"),
    pytest.param("a\t{j}b", "a b", id="after-a-tab"),
    pytest.param("\U0001f600{j}b", "\U0001f600 b", id="after-an-emoji"),
    pytest.param("1{j}2", "1 2", id="after-a-digit"),
    pytest.param("a-{j}b", "a- b", id="after-punctuation"),
    pytest.param("a{j}{j}b", "a b", id="a-run-of-two"),
    pytest.param("a{j}{j}{j}b", "a b", id="a-run-of-three"),
    pytest.param("a" + "{j}" * 50 + "b", "a b", id="a-long-run"),
    pytest.param("a{j}\u200bb", "a b", id="before-a-zero-width-space"),
    pytest.param("a\u200b{j}b", "a b", id="after-a-zero-width-space"),
    pytest.param("a{j}\u202eb", "a b", id="before-a-bidi-control"),
    pytest.param("a{j}\U000e0041b", "a b", id="before-a-tag-block-character"),
    pytest.param("a{j}\x00b", "a b", id="before-a-control-character"),
    pytest.param("a{j}\ud800b", "a b", id="before-a-lone-surrogate"),
])
def test_a_joiner_that_does_not_join_a_word_becomes_a_space(
        joiner: str, text: str, expected: str) -> None:
    assert flatten(text.format(j=joiner), 200) == expected


def test_a_joiner_run_never_survives_so_it_cannot_carry_a_message() -> None:
    # Hidden data hides in runs of joiners (a ZWJ is 1, a ZWNJ is 0, and so on), so any run of two
    # or more, mixed or not, flattens. One joiner after a letter can still carry one bit: that is
    # the known limit. The Tag block, which models read as text, is what the rule exists to close.
    assert flatten(f"a{ZWJ}{ZWNJ}{ZWJ}{ZWJ}{ZWNJ}b", 200) == "a b"
    assert flatten(f"a{ZWJ} {ZWJ}b", 200) == f"a{ZWJ} b"


def test_flatten_stays_linear_on_a_megabyte_of_mixed_text() -> None:
    chunk = f"word {CHILLU} {PERSIAN} a{ZWJ}{ZWJ}b\u200b \U0001f600{ZWJ}x\n"
    text = chunk * (1_000_000 // len(chunk))
    start = time.perf_counter()
    out = flatten(text, len(text))
    # About 0.3 s here. A bound this loose is not flaky, and a quadratic loop would take minutes.
    assert time.perf_counter() - start < 3
    assert CHILLU in out and PERSIAN in out


def test_shown_is_a_capped_repr() -> None:
    assert shown("abc") == "'abc'"
    assert shown(12) == "12"
    out = shown("x" * 5000)
    assert len(out) == 80 and out.endswith("…")
    assert shown("x" * 100, cap=10) == "'xxxxxxxx…"
