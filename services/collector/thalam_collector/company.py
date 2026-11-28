"""The fixture company's files -> checked records (SPEC-002-R4, R5, R6, R13).

    <company>/catalog/*.yaml      Backstage Components and Groups (thalam_collector.catalog)
    <company>/releases/*.yaml     one manifest per component: versions, needs, events
    <company>/jira/versions.json  Jira's project-versions response shape
    <company>/jira/search.json    Jira's issue-search response shape
    <company>/calendar.yaml       freeze and blackout windows

read_company() collects every problem, each with its file and field, and raises LoadError when
there is any, so a load writes nothing (R6). Our own files are strict (unknown fields refused);
Jira's shapes keep only the fields Thalam reads, as the real API sends many more.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from thalam_shared import graph
from thalam_shared.lifecycle import NOT_IN_FLIGHT, STATES, Event, allowed, current

from thalam_collector.catalog import Catalog, pydantic_problems, read_catalog
from thalam_collector.problems import LoadError, Problem

SUMMARY_CAP = 255
STATUS_CAP = 64
EVENT = re.compile(r"^(?P<state>[a-z_]+) (?P<at>\S+)(?: (?P<start>\S+) (?P<end>\S+))?$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Release(_Strict):
    version: str
    window: tuple[date, date]
    needs: dict[str, str] = Field(default_factory=dict)
    events: list[str]

    @field_validator("version", mode="before")
    @classmethod
    def _yaml_number(cls, value: object) -> object:
        # YAML reads an unquoted 1.1 as a number. Turn it back into text, so the X.Y.Z check
        # can say what is wrong with it (found by the plan's dry run).
        if isinstance(value, int | float) and not isinstance(value, bool):
            return str(value)
        return value


class _Manifest(_Strict):
    component: str
    releases: list[_Release]


class _Window(_Strict):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["freeze", "blackout"]
    starts: date
    ends: date


class _Calendar(_Strict):
    windows: list[_Window]


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _JiraVersion(_Loose):
    id: str
    name: str


class _JiraStatus(_Loose):
    name: str


class _JiraFixVersion(_Loose):
    id: str


class _JiraFields(_Loose):
    summary: str
    status: _JiraStatus
    fixVersions: list[_JiraFixVersion] = Field(default_factory=list)


class _JiraIssue(_Loose):
    key: str = Field(pattern=r"^[A-Z][A-Z0-9]+-[0-9]+$")
    fields: _JiraFields


class _JiraSearch(_Loose):
    issues: list[_JiraIssue]


@dataclass(frozen=True)
class ReleaseRecord:
    component: str
    version: str
    needs: tuple[tuple[str, str], ...]  # (component, range), sorted by component
    events: tuple[Event, ...]
    file: str
    jira_version_id: str | None = None


@dataclass(frozen=True)
class ItemRecord:
    component: str
    version: str
    jira_key: str
    summary: str  # untrusted text, capped; stored, never printed
    status: str


@dataclass(frozen=True)
class WindowRecord:
    name: str
    kind: str
    starts: date
    ends: date


@dataclass(frozen=True)
class Company:
    catalog: Catalog
    releases: tuple[ReleaseRecord, ...]
    items: tuple[ItemRecord, ...]
    windows: tuple[WindowRecord, ...]
    warnings: tuple[str, ...]


def _read(root: Path, rel: str, problems: list[Problem]) -> Any:
    path = root / rel
    if not path.is_file():
        problems.append(Problem(rel, "(file)", "the file is missing"))
        return None
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text) if rel.endswith(".json") else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        kind = rel.rsplit(".", 1)[1].upper()
        problems.append(Problem(rel, "(file)", f"not valid {kind}: {first!r}"))
        return None


def _event(line: str, window: tuple[date, date]) -> Event:
    match = EVENT.match(line)
    if not match:
        raise ValueError("expected '<state> <time>' or 'replan <time> <start> <end>'")
    at = datetime.fromisoformat(match["at"])
    if at.tzinfo is None:
        raise ValueError("the time needs its UTC offset, such as +05:30")
    if match["state"] == "replan":
        if not match["start"]:
            raise ValueError("a replan names its new window: replan <time> <start> <end>")
        new = (date.fromisoformat(match["start"]), date.fromisoformat(match["end"]))
        if new[1] < new[0]:
            raise ValueError("the window ends before it starts")
        return Event("replan", at, None, new)
    if match["start"]:
        raise ValueError("only a replan names a window")
    if match["state"] not in STATES:
        raise ValueError(f"unknown state {match['state']!r}")
    return Event("state", at, match["state"], window if match["state"] == "planned" else None)


def _release(rel: str, where: str, component: str, doc: _Release, known: set[str],
             problems: list[Problem]) -> ReleaseRecord:
    try:
        if graph.parse_version(doc.version) != doc.version:
            raise ValueError
    except ValueError:
        problems.append(Problem(rel, f"{where}.version", f"{doc.version!r} is not X.Y.Z"))
    if doc.window[1] < doc.window[0]:
        problems.append(Problem(rel, f"{where}.window", "the window ends before it starts"))
    needs = []
    for name, spec in sorted(doc.needs.items()):
        field = f"{where}.needs.{name}"
        if name == component:
            problems.append(Problem(rel, field, "a release cannot need its own component"))
        elif name not in known:
            problems.append(Problem(rel, field, f"no component named {name!r} in the catalog"))
        try:
            graph.parse_range(spec)
        except ValueError as exc:
            problems.append(Problem(rel, field, str(exc)))
        needs.append((name, spec))
    events: list[Event] = []
    state: str | None = None
    for j, line in enumerate(doc.events):
        field = f"{where}.events[{j}]"
        try:
            event = _event(line, doc.window)
        except ValueError as exc:
            problems.append(Problem(rel, field, str(exc)))
            continue
        if events and event.at <= events[-1].at:
            problems.append(Problem(rel, field, "is not later than the event before it"))
        if event.kind == "replan" and (state is None or state in NOT_IN_FLIGHT):
            problems.append(Problem(rel, field, "a replan needs a release in flight"))
        if event.kind == "state":
            assert event.state is not None
            if not allowed(state, event.state):
                problems.append(Problem(rel, field,
                                        f"{state or 'nothing'} cannot move to {event.state}"))
            state = event.state
        events.append(event)
    if not doc.events:
        problems.append(Problem(rel, f"{where}.events", "a release starts with a planned event"))
    return ReleaseRecord(component, doc.version, tuple(needs), tuple(events), rel)


def _releases(root: Path, catalog: Catalog, problems: list[Problem]) -> list[ReleaseRecord]:
    known = {c.name for c in catalog.components}
    records: list[ReleaseRecord] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted((root / "releases").glob("*.yaml")):
        rel = path.relative_to(root).as_posix()
        data = _read(root, rel, problems)
        if data is None:
            continue
        try:
            manifest = _Manifest.model_validate(data)
        except ValidationError as exc:
            problems += pydantic_problems(rel, "", exc)
            continue
        if manifest.component not in known:
            problems.append(Problem(rel, "component",
                                    f"no component named {manifest.component!r} in the catalog"))
            continue
        for i, doc in enumerate(manifest.releases):
            where = f"releases[{i}]"
            key = (manifest.component, doc.version)
            if key in seen:
                problems.append(Problem(rel, f"{where}.version",
                                        f"{manifest.component} {doc.version} is defined twice"))
                continue
            seen.add(key)
            records.append(_release(rel, where, manifest.component, doc, known, problems))
    return records


def _jira(root: Path, records: list[ReleaseRecord], problems: list[Problem]
          ) -> tuple[list[ReleaseRecord], list[ItemRecord]]:
    by_label = {f"{r.component} {r.version}": r for r in records}
    ids: dict[str, ReleaseRecord] = {}
    data = _read(root, "jira/versions.json", problems)
    if isinstance(data, list):
        for i, raw in enumerate(data):
            try:
                version = _JiraVersion.model_validate(raw)
            except ValidationError as exc:
                problems += pydantic_problems("jira/versions.json", f"[{i}]", exc)
                continue
            record = by_label.get(version.name)
            if record is None:
                problems.append(Problem("jira/versions.json", f"[{i}].name",
                                        f"{version.name!r} names no release in the manifests"))
            elif version.id in ids or record.jira_version_id is not None:
                problems.append(Problem("jira/versions.json", f"[{i}]",
                                        "a Jira version is listed twice"))
            else:
                updated = replace(record, jira_version_id=version.id)
                by_label[version.name] = ids[version.id] = updated
    elif data is not None:
        problems.append(Problem("jira/versions.json", "(file)", "expected a list of versions"))
    items: list[ItemRecord] = []
    data = _read(root, "jira/search.json", problems)
    if data is not None:
        try:
            search = _JiraSearch.model_validate(data)
        except ValidationError as exc:
            problems += pydantic_problems("jira/search.json", "", exc)
        else:
            for i, issue in enumerate(search.issues):
                for j, fix in enumerate(issue.fields.fixVersions):
                    owner = ids.get(fix.id)
                    if owner is None:
                        problems.append(Problem("jira/search.json",
                                                f"issues[{i}].fields.fixVersions[{j}]",
                                                f"no Jira version with id {fix.id!r}"))
                        continue
                    items.append(ItemRecord(owner.component, owner.version, issue.key,
                                            issue.fields.summary[:SUMMARY_CAP],
                                            issue.fields.status.name[:STATUS_CAP]))
    return list(by_label.values()), items


def _windows(root: Path, problems: list[Problem]) -> list[WindowRecord]:
    data = _read(root, "calendar.yaml", problems)
    if data is None:
        return []
    try:
        calendar = _Calendar.model_validate(data)
    except ValidationError as exc:
        problems += pydantic_problems("calendar.yaml", "", exc)
        return []
    out: list[WindowRecord] = []
    for i, w in enumerate(calendar.windows):
        if w.ends < w.starts:
            problems.append(Problem("calendar.yaml", f"windows[{i}]",
                                    "the window ends before it starts"))
        elif w.name in {x.name for x in out}:
            problems.append(Problem("calendar.yaml", f"windows[{i}].name",
                                    f"{w.name!r} is defined twice"))
        else:
            out.append(WindowRecord(w.name, w.kind, w.starts, w.ends))
    return out


def read_company(root: Path) -> Company:
    """Every record under root, checked across files; LoadError lists every problem at once."""
    catalog, problems = read_catalog(root)
    records = _releases(root, catalog, problems)
    records, items = _jira(root, records, problems)
    windows = _windows(root, problems)
    if problems:
        raise LoadError(problems)
    depends = {c.name: set(c.depends_on) for c in catalog.components}
    warnings = tuple(
        f"{r.component} {r.version} needs {name}, but {r.component}'s catalog entry does not "
        "depend on it"
        for r in records for name, _ in r.needs if name not in depends[r.component]
    )
    return Company(catalog, tuple(records), tuple(items), tuple(windows), warnings)


def to_graph(company: Company) -> graph.Graph:
    """The Graph these files describe: what Postgres must give back after a load (R8)."""
    releases = []
    for r in company.releases:
        state, window = current(r.events)
        releases.append(graph.Release(r.component, r.version, state, window,
                                      tuple(graph.Need(c, s) for c, s in r.needs)))
    return graph.make_graph(
        [graph.Component(c.name, c.owner) for c in company.catalog.components],
        [(c.name, d) for c in company.catalog.components for d in c.depends_on],
        releases,
        [graph.Window(w.name, w.kind, w.starts, w.ends) for w in company.windows],
    )
