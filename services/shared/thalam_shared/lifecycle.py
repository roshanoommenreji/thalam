"""A release's life cycle (SPEC-002, "The life cycle"; docs/architecture/overview.md).

planned → scoped → ready → change_approved → deploying → verifying → released, one step at a
time; `cancelled` can follow planned, scoped, ready or change_approved; `rolled_back` can follow
deploying, verifying or released. A release's first event is `planned`, carrying its window; a
`replan` event moves the window. The current state and window are the latest of each.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

STATES = (
    "planned", "scoped", "ready", "change_approved", "deploying", "verifying", "released",
    "rolled_back", "cancelled",
)
_NEXT = dict(zip(STATES[:6], STATES[1:7], strict=True))  # planned→scoped … verifying→released
_CANCEL_FROM = frozenset({"planned", "scoped", "ready", "change_approved"})
_ROLL_BACK_FROM = frozenset({"deploying", "verifying", "released"})
NOT_IN_FLIGHT = frozenset({"released", "rolled_back", "cancelled"})


def allowed(previous: str | None, new: str) -> bool:
    """Whether a release in state `previous` (None: no event yet) may move to `new`."""
    if previous is None:
        return new == "planned"
    if new == "cancelled":
        return previous in _CANCEL_FROM
    if new == "rolled_back":
        return previous in _ROLL_BACK_FROM
    return _NEXT.get(previous) == new


@dataclass(frozen=True)
class Event:
    kind: str  # "state" or "replan"
    at: datetime  # timezone-aware
    state: str | None = None  # set when kind is "state"
    window: tuple[date, date] | None = None  # set on "planned" and on every "replan"


def current(events: Iterable[Event]) -> tuple[str, tuple[date, date]]:
    """The latest state and the latest window, whatever order the events arrive in."""
    state: str | None = None
    window: tuple[date, date] | None = None
    for event in sorted(events, key=lambda e: e.at):
        if event.kind == "state":
            state = event.state
        if event.window is not None:
            window = event.window
    if state is None or window is None:
        raise ValueError("a release needs a planned event with its window")
    return state, window
