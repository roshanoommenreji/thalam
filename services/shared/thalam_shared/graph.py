"""The release graph's queries (SPEC-002-R9, R10, R11): pure functions over one snapshot.

Nothing here touches a database or a model. thalam_shared.graph_read builds a Graph from Postgres
and thalam_collector.company builds one from the fixture files; the same functions answer both, so
the logic is proved without Postgres and the read is proved on its own (R8).

A Graph holds no free text (no description, no summary), so nothing printed from it can carry a
planted terminal escape.

Two kinds of edge, kept apart. `depends_on` (the catalogue's declared dependencies between
components) drives `upstream` and `downstream`. Needs (a release's version ranges on other
components) drive `must_ship_before` and `release_order`. Nothing here requires a need to follow a
declared dependency; the loader (Task 7) warns when one does not.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from graphlib import CycleError, TopologicalSorter

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from thalam_shared.lifecycle import NOT_IN_FLIGHT

# A number is one to nine digits: Python refuses to turn 4,300 digits into an int, and no real
# release number needs more than nine.
VERSION = re.compile(r"([0-9]{1,9})\.([0-9]{1,9})(?:\.([0-9]{1,9}))?")
RANGE_PART = re.compile(
    r"[ \t]*(==|!=|<=|>=|<|>)[ \t]*([0-9]{1,9}(?:\.[0-9]{1,9}){0,2})[ \t]*")


class GraphError(Exception):
    """The needs form a loop, so no order exists. The message names one loop; others may exist."""


class UnknownName(LookupError):
    """A component or a release the graph does not hold."""


def parse_version(text: str) -> str:
    """'2.3' or '2.3.0' -> '2.3.0'. Anything else is a ValueError."""
    match = VERSION.fullmatch(text.strip())
    if not match:
        raise ValueError(f"not a version: {text!r} (expected X.Y.Z)")
    return f"{int(match[1])}.{int(match[2])}.{int(match[3] or 0)}"


def parse_range(text: str) -> SpecifierSet:
    """'>=1.8.0,<2': plain release numbers and the six comparison operators, nothing else.

    No '~=', '===' or wildcards, no epochs, pre-releases, dev, post or local versions, and no
    empty part.
    """
    parts = [RANGE_PART.fullmatch(part) for part in text.split(",")]
    if not all(parts):
        raise ValueError(f"not a version range: {text!r} (use >=, >, <=, <, == or !=)")
    try:
        return SpecifierSet(",".join(m[1] + m[2] for m in parts if m))
    except InvalidSpecifier:
        raise ValueError(f"not a version range: {text!r}") from None


@dataclass(frozen=True)
class Component:
    name: str
    owner: str
    retired: bool = False


@dataclass(frozen=True)
class Need:
    component: str
    spec: str  # a version range


@dataclass(frozen=True)
class Release:
    component: str
    version: str  # X.Y.Z
    state: str  # the current state (thalam_shared.lifecycle)
    window: tuple[date, date]  # the current window
    needs: tuple[Need, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.component} {self.version}"

    @property
    def in_flight(self) -> bool:
        return self.state not in NOT_IN_FLIGHT


@dataclass(frozen=True)
class Window:
    name: str
    kind: str  # freeze | blackout
    starts: date
    ends: date


@dataclass(frozen=True)
class Graph:
    components: Mapping[str, Component]
    depends_on: Mapping[str, frozenset[str]]
    releases: tuple[Release, ...]
    windows: tuple[Window, ...] = ()


def make_graph(components: Iterable[Component], edges: Iterable[tuple[str, str]],
               releases: Iterable[Release], windows: Iterable[Window] = ()) -> Graph:
    """A well-formed Graph in one canonical order, so two built from the same facts compare equal.

    Refused: an edge, a release or a need on a component that is not one (UnknownName); a need
    whose range does not parse, a release whose version is not one, a component that depends on
    itself, or two releases with one label (ValueError). Versions are stored as X.Y.Z. A Graph
    built directly skips these checks, so the queries still check what they read.
    """
    comps = {c.name: c for c in sorted(components, key=lambda c: c.name)}
    deps: dict[str, set[str]] = {name: set() for name in comps}
    for src, dst in edges:
        _component_in(comps, src)
        _component_in(comps, dst)
        if src == dst:
            raise ValueError(f"{src} depends on itself")
        deps[src].add(dst)
    rels: dict[str, Release] = {}
    for r in releases:
        _component_in(comps, r.component)
        for need in r.needs:
            _component_in(comps, need.component)
            parse_range(need.spec)
        fixed = replace(
            r, version=parse_version(r.version),
            needs=tuple(sorted(r.needs, key=lambda n: (n.component, n.spec))),
        )
        if fixed.label in rels:
            raise ValueError(f"two releases are called {fixed.label}")
        rels[fixed.label] = fixed
    ordered = sorted(rels.values(), key=lambda r: (r.component, Version(r.version)))
    return Graph(comps, {k: frozenset(v) for k, v in deps.items()}, tuple(ordered),
                 tuple(sorted(windows, key=lambda w: (w.name, w.starts, w.ends, w.kind))))


def _component_in(components: Mapping[str, Component], name: str) -> Component:
    try:
        return components[name]
    except KeyError:
        raise UnknownName(f"no component named {name!r}") from None


def _component(g: Graph, name: str) -> Component:
    return _component_in(g.components, name)


def _walk(start: str, next_of: Mapping[str, Iterable[str]]) -> list[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        for name in next_of.get(stack.pop(), ()):
            if name not in seen:
                seen.add(name)
                stack.append(name)
    seen.discard(start)
    return sorted(seen)


def upstream(g: Graph, name: str) -> list[str]:
    """Every component `name` depends on, directly or not."""
    _component(g, name)
    return _walk(name, g.depends_on)


def downstream(g: Graph, name: str) -> list[str]:
    """Every component that depends on `name`, directly or not: its blast radius."""
    _component(g, name)
    users: dict[str, set[str]] = {}
    for src, dsts in g.depends_on.items():
        for dst in dsts:
            users.setdefault(dst, set()).add(src)
    return _walk(name, users)


def _releases_of(g: Graph, name: str) -> list[Release]:
    return [r for r in g.releases if r.component == name]


def prod_version(g: Graph, name: str) -> str | None:
    """The highest version whose current state is `released`; None: not in prod."""
    _component(g, name)
    released = [Version(r.version) for r in _releases_of(g, name) if r.state == "released"]
    return str(max(released)) if released else None


def release(g: Graph, name: str, version: str) -> Release:
    _component(g, name)
    wanted = parse_version(version)
    for r in _releases_of(g, name):
        if r.version == wanted:
            return r
    raise UnknownName(f"no release {name} {wanted}")


@dataclass(frozen=True)
class Step:
    release: Release  # to ship first
    needed_by: str  # the first release that reached it; others may need it too
    need: Need  # that release's need
    prod: str | None  # what prod runs today


@dataclass(frozen=True)
class Satisfied:
    need: Need
    needed_by: str
    prod: str


@dataclass(frozen=True)
class Blocker:
    need: Need
    needed_by: str
    reason: str


@dataclass(frozen=True)
class Answer:
    target: Release
    steps: tuple[Step, ...]  # upstream first
    satisfied: tuple[Satisfied, ...]
    blockers: tuple[Blocker, ...]


def _resolve(g: Graph, needer: Release, need: Need) -> Satisfied | Blocker | Release:
    """Prod already meets it, nothing can, or this in-flight release (the lowest that does)."""
    if _component(g, need.component).retired:
        return Blocker(need, needer.label, f"{need.component} is retired")
    spec = parse_range(need.spec)
    prod = prod_version(g, need.component)
    if prod is not None and Version(prod) in spec:
        return Satisfied(need, needer.label, prod)
    candidates = [r for r in _releases_of(g, need.component)
                  if r.in_flight and Version(r.version) in spec]
    if not candidates:
        return Blocker(need, needer.label,
                       f"no release satisfies {spec} (prod runs {prod or 'nothing'})")
    return min(candidates, key=lambda r: Version(r.version))


def _by_version(label: str) -> tuple[str, Version]:
    name, _, version = label.rpartition(" ")
    return name, Version(version)


def _ordered(edges: Mapping[str, set[str]], nodes: Iterable[str]) -> list[str]:
    """Every node after the nodes it needs; ties in name order, then lowest version first."""
    sorter = TopologicalSorter({n: edges.get(n, set()) for n in sorted(nodes, key=_by_version)})
    try:
        sorter.prepare()
    except CycleError as exc:
        # args[1] lists each node as the predecessor of the next, and repeats the first at the end.
        # A predecessor is what a release needs, so reverse it to read "needs".
        loop = list(reversed(exc.args[1][:-1]))
        start = loop.index(min(loop))
        loop = loop[start:] + loop[:start]
        raise GraphError("the needs form a loop: " + " → ".join([*loop, loop[0]])) from None
    order: list[str] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready(), key=_by_version)
        order += ready
        sorter.done(*ready)
    return order


def must_ship_before(g: Graph, name: str, version: str) -> Answer:
    """What has to ship before `name version`, upstream first, and what nothing can satisfy.

    It answers for any release, including one already released or cancelled.
    """
    target = release(g, name, version)
    steps: dict[str, Step] = {}
    satisfied: list[Satisfied] = []
    blockers: list[Blocker] = []
    edges: dict[str, set[str]] = {}
    seen = {target.label}
    queue = [target]
    while queue:
        needer = queue.pop(0)
        for need in needer.needs:
            found = _resolve(g, needer, need)
            if isinstance(found, Satisfied):
                satisfied.append(found)
            elif isinstance(found, Blocker):
                blockers.append(found)
            else:
                edges.setdefault(needer.label, set()).add(found.label)
                if found.label not in seen:
                    seen.add(found.label)
                    steps[found.label] = Step(found, needer.label, need,
                                              prod_version(g, need.component))
                    queue.append(found)
    order = _ordered(edges, seen)
    return Answer(target, tuple(steps[label] for label in order if label in steps),
                  tuple(satisfied), tuple(blockers))


def release_order(g: Graph) -> list[Release]:
    """Every release in flight, each after the releases it needs.

    Nothing orders two in-flight versions of one component except a need between them; the
    version order is only the tie-break within a layer.
    """
    flying = {r.label: r for r in g.releases if r.in_flight}
    edges: dict[str, set[str]] = {}
    for r in flying.values():
        for need in r.needs:
            found = _resolve(g, r, need)
            if isinstance(found, Release):
                edges.setdefault(r.label, set()).add(found.label)
    return [flying[label] for label in _ordered(edges, flying)]
