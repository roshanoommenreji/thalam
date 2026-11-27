"""The release graph's seven tables (SPEC-002-R2).

Two kinds, and scripts/ops/db-roles.sql holds each to its kind with grants (R3):
- mirrors of a source file: component, dependency, release_item, calendar_window. The loader
  makes them match the files on every load; a component that leaves the catalog is retired, never
  deleted, so its old releases keep their link.
- written once: release, release_need, release_event. Nothing UPDATEs or DELETEs them; a state
  change or a re-plan is a new release_event row (Kaval's append-only spine, ADR-0002).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    MetaData,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from thalam_shared.lifecycle import STATES, Event

STATE_LIST = ", ".join(f"'{s}'" for s in STATES)
NAMES = {
    "pk": "pk_%(table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMES)


class Component(Base):
    __tablename__ = "component"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    owner: Mapped[str] = mapped_column(Text)  # a Backstage Group's name
    type: Mapped[str] = mapped_column(Text)
    lifecycle: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)  # untrusted text, capped; never printed
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dependency(Base):
    __tablename__ = "dependency"
    __table_args__ = (CheckConstraint("src_id <> dst_id", name="not_self"),)
    src_id: Mapped[int] = mapped_column(ForeignKey("component.id"), primary_key=True)
    dst_id: Mapped[int] = mapped_column(ForeignKey("component.id"), primary_key=True)


class Release(Base):
    __tablename__ = "release"
    __table_args__ = (
        UniqueConstraint("component_id", "version"),
        CheckConstraint(r"version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'", name="version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("component.id"))
    version: Mapped[str] = mapped_column(Text)
    jira_version_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReleaseNeed(Base):
    __tablename__ = "release_need"
    __table_args__ = (UniqueConstraint("release_id", "component_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("release.id"))
    component_id: Mapped[int] = mapped_column(ForeignKey("component.id"))
    spec: Mapped[str] = mapped_column(Text)  # a version range such as ">=1.8.0,<2"


class ReleaseEvent(Base):
    __tablename__ = "release_event"
    __table_args__ = (
        UniqueConstraint("release_id", "at"),
        CheckConstraint("kind IN ('state', 'replan')", name="kind"),
        CheckConstraint(f"state IS NULL OR state IN ({STATE_LIST})", name="state"),
        CheckConstraint(
            "(kind = 'state' AND state IS NOT NULL"
            " AND (state = 'planned') = (window_start IS NOT NULL))"
            " OR (kind = 'replan' AND state IS NULL AND window_start IS NOT NULL)",
            name="shape",
        ),
        CheckConstraint(
            "(window_start IS NULL) = (window_end IS NULL)"
            " AND (window_end IS NULL OR window_end >= window_start)",
            name="window",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("release.id"))
    kind: Mapped[str] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def as_event(self) -> Event:
        window = None
        if self.window_start is not None and self.window_end is not None:
            window = (self.window_start, self.window_end)
        return Event(self.kind, self.at, self.state, window)

    @classmethod
    def from_event(cls, release_id: int, event: Event) -> ReleaseEvent:
        start, end = event.window if event.window is not None else (None, None)
        return cls(release_id=release_id, kind=event.kind, state=event.state,
                   window_start=start, window_end=end, at=event.at)


class ReleaseItem(Base):
    __tablename__ = "release_item"
    __table_args__ = (UniqueConstraint("release_id", "jira_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("release.id"))
    jira_key: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)  # untrusted text, capped at 255; never printed
    status: Mapped[str] = mapped_column(Text)


class CalendarWindow(Base):
    __tablename__ = "calendar_window"
    __table_args__ = (
        CheckConstraint("kind IN ('freeze', 'blackout')", name="kind"),
        CheckConstraint("ends >= starts", name="order"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    starts: Mapped[date] = mapped_column(Date)
    ends: Mapped[date] = mapped_column(Date)
