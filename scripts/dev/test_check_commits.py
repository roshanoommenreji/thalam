"""Tests for the commit-message check (SPEC-001-R5; copied from Kaval KAV-25)."""
# covers: SPEC-001-R5

from __future__ import annotations

import pytest
from check_commits import problems

STORY = "feat/THL-1-foundations"


@pytest.mark.parametrize(
    "message",
    [
        "feat: THL-1 commit-msg hook",
        "fix(ci): THL-1 pin the gitleaks checksum",
        "infra!: THL-7 move the database to its own server",
        "docs: THL-1 Lab 00\n\nBody text with #hashtag and a PR ref #1.",
        "Merge pull request #2 from roshanoommenreji/feat/THL-1-foundations",
        "Merge branch 'feat/THL-2-release-graph'",
        'Revert "feat: THL-1 commit-msg hook"',
        "# Please enter the commit message\nchore: THL-1 tidy\n# comment line",
    ],
)
def test_accepts(message: str) -> None:
    assert problems(message, STORY) == []


def test_housekeeping_branch_needs_no_key() -> None:
    assert problems("chore: tidy the root", "chore/repo-structure") == []


@pytest.mark.parametrize(
    ("message", "fragment"),
    [
        ("added the hook", "must start with"),
        ("feature: THL-1 hook", "must start with"),
        ("feat:THL-1 no space", "must start with"),
        ("Feat: THL-1 capital", "must start with"),
        ("feat: add the hook", "needs its THL key"),
        ("feat: THL-1 " + "x" * 100, "keep it to 100"),
        ("feat: THL-1 hook #comment done", "smart-commit"),
        ("feat: THL-1 hook\n\nTHL-1 #time 2h", "smart-commit"),
        ("feat: THL-1 #done", "smart-commit"),
        ("", "empty"),
        ("# only comments", "empty"),
    ],
)
def test_rejects(message: str, fragment: str) -> None:
    found = problems(message, STORY)
    assert any(fragment in p for p in found), found


def test_autosquash_allowed_locally_refused_in_ci() -> None:
    message = "fixup! feat: THL-1 hook"
    assert problems(message, STORY) == []
    assert problems(message, STORY, in_ci=True)
