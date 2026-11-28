"""Backstage catalog files -> components and groups (SPEC-002-R4).

Reads every *.yaml under <company>/catalog/ with yaml.safe_load_all: never yaml.load, which can
build arbitrary Python objects from a planted tag. Documents of kind Group and Component are read;
other kinds (API, System, Resource) are skipped. Only `component:` dependencies are read in Phase 1,
and each must name a Component in the catalog: a dropped edge would make "must ship before"
silently wrong, so an unknown one fails the load rather than being skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from thalam_collector.problems import Problem

NAME = r"^[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*$"  # Backstage's rule, at most 63 characters
REF = re.compile(  # "component:name", "component:default/name" or "name"
    r"^(?:(?P<kind>[A-Za-z]+):)?(?:default/)?"
    r"(?P<name>[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*)$"
)
DESCRIPTION_CAP = 1000


class _Metadata(BaseModel):
    model_config = ConfigDict(extra="ignore")  # real catalogs carry annotations, tags, links
    name: str = Field(pattern=NAME, max_length=63)
    description: str = ""


class _ComponentSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str = Field(pattern=NAME)
    lifecycle: str = Field(pattern=NAME)
    owner: str
    dependsOn: list[str] = Field(default_factory=list)


class _Group(BaseModel):
    model_config = ConfigDict(extra="ignore")
    apiVersion: Literal["backstage.io/v1alpha1"]
    kind: Literal["Group"]
    metadata: _Metadata


class _Component(BaseModel):
    model_config = ConfigDict(extra="ignore")
    apiVersion: Literal["backstage.io/v1alpha1"]
    kind: Literal["Component"]
    metadata: _Metadata
    spec: _ComponentSpec


@dataclass(frozen=True)
class CatalogComponent:
    name: str
    owner: str  # the Group's name, without "group:"
    type: str
    lifecycle: str
    description: str  # untrusted text, capped; stored, never printed
    depends_on: tuple[str, ...]
    file: str
    where: str  # "documents[n]"


@dataclass(frozen=True)
class Catalog:
    components: tuple[CatalogComponent, ...]
    groups: frozenset[str]


def pydantic_problems(file: str, prefix: str, exc: ValidationError) -> list[Problem]:
    """One Problem per Pydantic error, located as "prefix.field[i]"."""
    out = []
    for error in exc.errors():
        loc = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error["loc"])
        out.append(Problem(file, (prefix + loc).lstrip("."), error["msg"]))
    return out


def _docs(path: Path, rel: str) -> tuple[list[Any], list[Problem]]:
    try:
        return list(yaml.safe_load_all(path.read_text(encoding="utf-8"))), []
    except yaml.YAMLError as exc:
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return [], [Problem(rel, "(file)", f"not valid YAML: {first!r}")]


def read_catalog(root: Path) -> tuple[Catalog, list[Problem]]:
    """Every component and group under root/catalog/, and every problem found on the way."""
    problems: list[Problem] = []
    groups: set[str] = set()
    raw: list[tuple[CatalogComponent, list[tuple[int, str, str]]]] = []
    files = sorted((root / "catalog").glob("*.yaml"))
    if not files:
        return Catalog((), frozenset()), [Problem("catalog/", "(folder)", "no catalog files")]
    for path in files:
        rel = path.relative_to(root).as_posix()
        docs, found = _docs(path, rel)
        problems += found
        for i, doc in enumerate(docs):
            where = f"documents[{i}]"
            kind = doc.get("kind") if isinstance(doc, dict) else None
            try:
                if kind == "Group":
                    groups.add(_Group.model_validate(doc).metadata.name)
                elif kind == "Component":
                    parsed = _Component.model_validate(doc)
                    refs = [(j, f"{where}.spec.dependsOn[{j}]", ref)
                            for j, ref in enumerate(parsed.spec.dependsOn)]
                    raw.append((CatalogComponent(
                        parsed.metadata.name, parsed.spec.owner, parsed.spec.type,
                        parsed.spec.lifecycle, parsed.metadata.description[:DESCRIPTION_CAP], (),
                        rel, where), refs))
                elif not isinstance(doc, dict):
                    problems.append(Problem(rel, where, "a catalog document must be a mapping"))
            except ValidationError as exc:
                problems += pydantic_problems(rel, where, exc)
    names = [c.name for c, _ in raw]
    components: list[CatalogComponent] = []
    for c, refs in raw:
        if names.count(c.name) > 1 and c.name not in {x.name for x in components}:
            problems.append(Problem(c.file, f"{c.where}.metadata.name",
                                    f"{c.name!r} is defined twice"))
        owner = REF.match(c.owner)
        is_group = owner is not None and (owner["kind"] or "group").lower() == "group"
        owner_name = owner["name"] if owner is not None and is_group else None
        if owner_name not in groups:
            shown = owner_name if owner_name is not None else c.owner
            problems.append(Problem(c.file, f"{c.where}.spec.owner",
                                    f"no Group named {shown!r} in the catalog"))
        depends: list[str] = []
        for _, field, ref in refs:
            m = REF.match(ref)
            if not m or not m["kind"] or m["kind"].lower() != "component":
                problems.append(Problem(c.file, field, f"{ref!r} is not component:<name>"))
            elif m["name"] == c.name:
                problems.append(Problem(c.file, field, "a component cannot depend on itself"))
            elif m["name"] not in names:
                problems.append(Problem(c.file, field,
                                        f"no Component named {m['name']!r} in the catalog"))
            else:
                depends.append(m["name"])
        components.append(CatalogComponent(c.name, owner_name or c.owner, c.type, c.lifecycle,
                                           c.description, tuple(sorted(set(depends))), c.file,
                                           c.where))
    return Catalog(tuple(components), frozenset(groups)), problems
