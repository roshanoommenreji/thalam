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

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    ValidationError,
    field_validator,
)
from thalam_shared import graph
from thalam_shared.lifecycle import NOT_IN_FLIGHT, STATES, Event, allowed, current

from thalam_collector.catalog import Catalog, pydantic_problems, read_catalog
from thalam_collector.files import read_json, read_yaml
from thalam_collector.problems import LoadError, Problem
from thalam_collector.text import flatten, shown

SUMMARY_CAP = 255
STATUS_CAP = 64
EVENT = re.compile(r"(?P<state>[a-z_]+) (?P<at>\S+)(?: (?P<start>\S+) (?P<end>\S+))?")  # fullmatch
YEARS = range(2000, 2101)  # a date outside these is a typo or a planted value, not a release
_ID = r"^[0-9]{1,20}$"  # Jira's ids are numeric strings
_Date = Annotated[date, Strict()]  # an integer or a string is not a date (0 is 1970-01-01)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Release(_Strict):
    version: str
    window: tuple[_Date, _Date]
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
    starts: _Date
    ends: _Date


class _Calendar(_Strict):
    windows: list[_Window]


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _JiraVersion(_Loose):
    id: str = Field(pattern=_ID)
    name: str


class _JiraStatus(_Loose):
    name: str


class _JiraFixVersion(_Loose):
    id: str = Field(pattern=_ID)


class _JiraFields(_Loose):
    summary: str
    status: _JiraStatus
    fixVersions: list[_JiraFixVersion] = Field(default_factory=list)


class _JiraIssue(_Loose):
    key: str = Field(pattern=r"^[A-Z][A-Z0-9]+-[0-9]+$", max_length=100)
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


class _Failed:
    """What _read returns, instead of a document, when it has already filed the problem."""


_FAILED = _Failed()


def _read(root: Path, rel: str, problems: list[Problem]) -> object:
    """The one document in a file, or _FAILED after adding why to `problems`.

    Both readers are the hardened ones in thalam_collector.files: nothing in a file can raise out
    of this function, and no problem quotes the file.
    """
    path = root / rel
    if not path.is_file():
        problems.append(Problem(rel, "(file)", "the file is missing"))
        return _FAILED
    if rel.endswith(".json"):
        value, found = read_json(path, rel)
        problems += found
        return _FAILED if found else value
    docs, found = read_yaml(path, rel)
    problems += found
    if found:
        return _FAILED
    if not docs:
        problems.append(Problem(rel, "(file)", "the file is empty"))
        return _FAILED
    if len(docs) > 1:
        problems.append(Problem(rel, "(file)", "one document per file"))
        return _FAILED
    return docs[0]


def _unknown(name: str, known: set[str]) -> str:
    """Names are exact (our own files fail closed), but a different case earns a hint."""
    message = f"no component named {shown(name)} in the catalog"
    near = sorted(k for k in known if k.casefold() == name.casefold())
    return f"{message} (did you mean {shown(near[0])}?)" if near else message


class _BadEvent(ValueError):
    """An event line that cannot be read; `message` is fixed text, never a quote of the line."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _years_ok(*days: date | datetime) -> bool:
    return all(day.year in YEARS for day in days)


def _event(line: str, window: tuple[date, date]) -> Event:
    match = EVENT.fullmatch(line)
    if not match:
        raise _BadEvent("expected '<state> <time>' or 'replan <time> <start> <end>', with the "
                        "time written without spaces, such as 'planned 2026-11-10T10:00:00+05:30'")
    try:
        at = datetime.fromisoformat(match["at"])
    except ValueError:
        raise _BadEvent("the time is not an ISO 8601 date and time with a UTC offset") from None
    if at.tzinfo is None:
        raise _BadEvent("the time needs its UTC offset, such as +05:30")
    if not _years_ok(at):
        raise _BadEvent("the time's year out of range (2000 to 2100)")
    if match["state"] == "replan":
        if not match["start"]:
            raise _BadEvent("a replan names its new window: replan <time> <start> <end>")
        try:
            new = (date.fromisoformat(match["start"]), date.fromisoformat(match["end"]))
        except ValueError:
            raise _BadEvent("a replan's window dates must be YYYY-MM-DD") from None
        if new[1] < new[0]:
            raise _BadEvent("the window ends before it starts")
        if not _years_ok(*new):
            raise _BadEvent("the window's year out of range (2000 to 2100)")
        return Event("replan", at, None, new)
    if match["start"]:
        raise _BadEvent("only a replan names a window")
    if match["state"] not in STATES:
        raise _BadEvent(f"unknown state {shown(match['state'])}")
    return Event("state", at, match["state"], window if match["state"] == "planned" else None)


def _release(rel: str, where: str, component: str, doc: _Release, known: set[str],
             catalog_ok: bool, problems: list[Problem]) -> ReleaseRecord:
    try:
        if graph.parse_version(doc.version) != doc.version:
            raise ValueError
    except ValueError:
        problems.append(Problem(rel, f"{where}.version", f"{shown(doc.version)} is not X.Y.Z"))
    if doc.window[1] < doc.window[0]:
        problems.append(Problem(rel, f"{where}.window", "the window ends before it starts"))
    if not _years_ok(*doc.window):
        problems.append(Problem(rel, f"{where}.window", "year out of range (2000 to 2100)"))
    needs = []
    for name, spec in sorted(doc.needs.items()):
        field = f"{where}.needs.{flatten(name, 60)}"  # printed, so never the raw key
        if name == component:
            problems.append(Problem(rel, field, "a release cannot need its own component"))
        elif name not in known and catalog_ok:  # else the catalog's problems are the cause
            problems.append(Problem(rel, field, _unknown(name, known)))
        try:
            graph.parse_range(spec)
        except ValueError:  # its own message quotes the whole text, so ours is capped
            problems.append(Problem(rel, field, f"not a version range: {shown(spec)} "
                                                "(use >=, >, <=, <, == or !=)"))
        needs.append((name, spec))
    events: list[Event] = []
    state: str | None = None
    for j, line in enumerate(doc.events):
        field = f"{where}.events[{j}]"
        try:
            event = _event(line, doc.window)
        except _BadEvent as exc:
            problems.append(Problem(rel, field, exc.message))
            continue
        if events and event.at <= events[-1].at:
            problems.append(Problem(rel, field, "is not later than the event before it"))
        if event.kind == "replan" and (state is None or state in NOT_IN_FLIGHT):
            problems.append(Problem(rel, field, "a replan needs a release in flight"))
        if event.kind == "state" and event.state is not None:
            if state is None and event.state != "planned":
                problems.append(Problem(rel, field, "a release must start with planned"))
            elif not allowed(state, event.state):
                problems.append(Problem(rel, field, f"{state} cannot move to {event.state}"))
            state = event.state
        events.append(event)
    if not doc.events:
        problems.append(Problem(rel, f"{where}.events", "a release starts with a planned event"))
    return ReleaseRecord(component, doc.version, tuple(needs), tuple(events), rel)


def _releases(root: Path, catalog: Catalog, catalog_ok: bool, problems: list[Problem]
              ) -> tuple[list[ReleaseRecord], set[str], bool]:
    """The release records, the components whose manifest failed, and whether no manifest was read.

    A failed manifest is one cause: the Jira files must not also complain about its versions.
    """
    known = {c.name for c in catalog.components}
    records: list[ReleaseRecord] = []
    failed: set[str] = set()
    seen: set[tuple[str, str]] = set()
    read_any = False
    folder = root / "releases"
    for path in sorted(folder.iterdir(), key=lambda p: p.name) if folder.is_dir() else []:
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".yml":
            problems.append(Problem(rel, "(file)", "only .yaml files are read: rename it to .yaml"))
            failed.add(path.stem)
            continue
        if path.suffix.lower() != ".yaml":
            continue
        read_any = True
        data = _read(root, rel, problems)
        if data is _FAILED:
            failed.add(path.stem)
            continue
        names = {path.stem}  # a manifest is named for its component, but only by habit
        if isinstance(data, dict) and isinstance(data.get("component"), str):
            names.add(data["component"])
        try:
            manifest = _Manifest.model_validate(data)
        except ValidationError as exc:
            problems += pydantic_problems(rel, "", exc)
            failed |= names
            continue
        if manifest.component not in known:
            if catalog_ok:  # else the catalog's problems are the cause
                problems.append(Problem(rel, "component", _unknown(manifest.component, known)))
            failed |= names
            continue
        for i, doc in enumerate(manifest.releases):
            where = f"releases[{i}]"
            key = (manifest.component, doc.version)
            if key in seen:
                label = flatten(f"{manifest.component} {doc.version}", 80)
                problems.append(Problem(rel, f"{where}.version", f"{label} is defined twice"))
                continue
            seen.add(key)
            records.append(
                _release(rel, where, manifest.component, doc, known, catalog_ok, problems))
    if not read_any:
        problems.append(Problem("releases/", "(folder)", "no release manifests"))
    return records, failed, not read_any


def _jira(root: Path, records: list[ReleaseRecord], failed: set[str], nothing_read: bool,
          problems: list[Problem]) -> tuple[list[ReleaseRecord], list[ItemRecord]]:
    by_label = {f"{r.component} {r.version}": r for r in records}
    ids: dict[str, ReleaseRecord] = {}
    skipped: set[str] = set()  # Jira ids of versions whose manifest failed: already one problem
    before = len(problems)
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
                if nothing_read or version.name.rpartition(" ")[0] in failed:
                    skipped.add(version.id)
                    continue
                problems.append(Problem("jira/versions.json", f"[{i}].name",
                                        f"{shown(version.name)} names no release in the manifests"))
            elif record.jira_version_id is not None:
                problems.append(Problem("jira/versions.json", f"[{i}]",
                                        f"Jira version {shown(version.name)} is listed twice"))
            elif version.id in ids:
                problems.append(Problem("jira/versions.json", f"[{i}]",
                                        f"Jira id {shown(version.id)} is used twice"))
            else:
                updated = replace(record, jira_version_id=version.id)
                by_label[version.name] = ids[version.id] = updated
    elif data is not _FAILED:
        problems.append(Problem("jira/versions.json", "(file)", "expected a list of versions"))
    versions_ok = len(problems) == before  # else the items' ids would only repeat the cause
    items: list[ItemRecord] = []
    listed: set[tuple[str, str, str]] = set()
    data = _read(root, "jira/search.json", problems)
    if data is not _FAILED:
        try:
            search = _JiraSearch.model_validate(data)
        except ValidationError as exc:
            problems += pydantic_problems("jira/search.json", "", exc)
        else:
            for i, issue in enumerate(search.issues):
                for j, fix in enumerate(issue.fields.fixVersions):
                    where = f"issues[{i}].fields.fixVersions[{j}]"
                    owner = ids.get(fix.id)
                    if owner is None:
                        if versions_ok and fix.id not in skipped:
                            problems.append(Problem("jira/search.json", where,
                                                    f"no Jira version with id {shown(fix.id)}"))
                        continue
                    if (owner.component, owner.version, issue.key) in listed:
                        label = flatten(f"{owner.component} {owner.version}", 80)
                        problems.append(Problem("jira/search.json", where,
                                                f"{issue.key} is listed twice for {label}"))
                        continue
                    listed.add((owner.component, owner.version, issue.key))
                    items.append(ItemRecord(owner.component, owner.version, issue.key,
                                            flatten(issue.fields.summary, SUMMARY_CAP),
                                            flatten(issue.fields.status.name, STATUS_CAP)))
    return list(by_label.values()), items


def _windows(root: Path, problems: list[Problem]) -> list[WindowRecord]:
    data = _read(root, "calendar.yaml", problems)
    if data is _FAILED:
        return []
    try:
        calendar = _Calendar.model_validate(data)
    except ValidationError as exc:
        problems += pydantic_problems("calendar.yaml", "", exc)
        return []
    out: list[WindowRecord] = []
    names: set[str] = set()
    for i, w in enumerate(calendar.windows):
        name = flatten(w.name, 100)  # "a<tab>b" and "a b" are one name
        where = f"windows[{i}]"
        if not name:
            problems.append(Problem("calendar.yaml", where, "a window needs a name"))
        elif w.ends < w.starts:
            problems.append(Problem("calendar.yaml", where, "the window ends before it starts"))
        elif not _years_ok(w.starts, w.ends):
            problems.append(Problem("calendar.yaml", where, "year out of range (2000 to 2100)"))
        elif name in names:
            problems.append(Problem("calendar.yaml", f"{where}.name",
                                    f"{shown(name)} is defined twice"))
        else:
            names.add(name)
            out.append(WindowRecord(name, w.kind, w.starts, w.ends))
    return out


def read_company(root: Path) -> Company:
    """Every record under root, checked across files; LoadError lists every problem at once."""
    catalog, problems = read_catalog(root)
    catalog_ok = not problems  # else a name missing from the catalog may be the catalog's fault
    records, failed, nothing_read = _releases(root, catalog, catalog_ok, problems)
    records, items = _jira(root, records, failed, nothing_read, problems)
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
