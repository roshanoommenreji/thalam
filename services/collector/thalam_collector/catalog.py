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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from thalam_collector.problems import Problem

_NAME_PART = r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*"  # Backstage's rule, written once
NAME = rf"^{_NAME_PART}$"  # at most 63 characters, checked beside it
REF = re.compile(  # "component:name", "component:default/name" or "name"; use fullmatch
    rf"(?:(?P<kind>[A-Za-z]+):)?(?:default/)?(?P<name>{_NAME_PART})"
)
DESCRIPTION_CAP = 1000
MAX_FILE_BYTES = 1_048_576  # pure-Python PyYAML took 83 s on a 4 MB file
# Control characters, lone surrogates, line separators and whitespace all become one space.
_FLATTEN = re.compile(r"[\x00-\x1f\x7f-\x9f\ud800-\udfff  \s]+")
_SPELT = {"component": "Component", "group": "Group"}


class _Metadata(BaseModel):
    model_config = ConfigDict(extra="ignore")  # real catalogs carry annotations, tags, links
    name: str = Field(pattern=NAME, max_length=63)
    namespace: str | None = None
    description: str = ""

    @field_validator("description", mode="before")
    @classmethod
    def _flatten(cls, value: object) -> object:
        """Untrusted text: one line of plain text, no NUL, capped (CLAUDE.md rule 4)."""
        if value is None:
            return ""
        if not isinstance(value, str):
            return value
        return _FLATTEN.sub(" ", value).strip()[:DESCRIPTION_CAP].rstrip()


class _ComponentSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str = Field(pattern=NAME, max_length=63)
    lifecycle: str = Field(pattern=NAME, max_length=63)
    owner: str = Field(max_length=200)
    dependsOn: list[str] = Field(default_factory=list, max_length=200)


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
    owner: str  # the Group's name as its own document writes it, without "group:"
    type: str
    lifecycle: str
    description: str  # untrusted text, flattened and capped; stored, never printed
    depends_on: tuple[str, ...]  # each target's name as its own document writes it
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


# Never walk, copy, repr or serialise a whole raw document. YAML aliases are shared objects, so
# walking one can blow up (a "billion laughs" file); only the validated fields are ever read.
# Nothing a file contains may raise out of here: every failure becomes a Problem naming the file.
def _docs(path: Path, rel: str) -> tuple[list[Any], list[Problem]]:
    def fail(message: str) -> tuple[list[Any], list[Problem]]:
        return [], [Problem(rel, "(file)", message)]

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return fail("larger than 1 MiB")
        return list(yaml.safe_load_all(path.read_text(encoding="utf-8"))), []
    except UnicodeDecodeError:
        return fail("not UTF-8")
    except yaml.MarkedYAMLError as exc:
        text = str(exc.problem or exc.context or type(exc).__name__)[:200]
        if exc.problem_mark is None:
            return fail(f"not valid YAML: {text!r}")
        return fail(f"not valid YAML at line {exc.problem_mark.line + 1}: {text!r}")
    except yaml.YAMLError as exc:
        return fail(f"not valid YAML: {type(exc).__name__}")
    except (ValueError, RecursionError) as exc:  # e.g. a bad timestamp, or 20,000 nested "["
        return fail(f"not valid YAML: a value could not be read ({type(exc).__name__})")
    except OSError as exc:
        return fail(f"unreadable: {type(exc).__name__}")


def read_catalog(root: Path) -> tuple[Catalog, list[Problem]]:
    """Every component and group under root/catalog/, and every problem found on the way.

    When the problems are not empty, the Catalog is partial and must not be used: Task 8 refuses
    the load. Only files directly in catalog/ are read; its subfolders are not.
    """
    problems: list[Problem] = []
    groups: dict[str, tuple[str, str, str]] = {}  # folded name -> (name, file, where), first seen
    raw: list[tuple[CatalogComponent, list[tuple[str, str]]]] = []  # (component, (field, ref))
    folder = root / "catalog"
    read_any = False
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".yml":
            problems.append(Problem(rel, "(file)", "only .yaml files are read: rename it to .yaml"))
            continue
        if path.suffix.lower() != ".yaml":
            continue
        read_any = True
        docs, found = _docs(path, rel)
        problems += found
        for i, doc in enumerate(docs):
            if doc is None:  # an empty document, from a stray or trailing "---"
                continue
            where = f"documents[{i}]"
            if not isinstance(doc, dict):
                problems.append(Problem(rel, where, "a catalog document must be a mapping"))
                continue
            kind = doc.get("kind")
            try:
                if kind == "Group":
                    group = _Group.model_validate(doc)
                    problems += _namespace(rel, where, group.metadata)
                    name = group.metadata.name
                    first = groups.setdefault(name.casefold(), (name, rel, where))
                    if first[1:] != (rel, where):
                        problems.append(Problem(rel, f"{where}.metadata.name",
                                                f"{name!r} is defined twice "
                                                f"(first at {first[1]} {first[2]})"))
                elif kind == "Component":
                    parsed = _Component.model_validate(doc)
                    problems += _namespace(rel, where, parsed.metadata)
                    refs = [(f"{where}.spec.dependsOn[{j}]", ref)
                            for j, ref in enumerate(parsed.spec.dependsOn)]
                    raw.append((CatalogComponent(
                        parsed.metadata.name, parsed.spec.owner, parsed.spec.type,
                        parsed.spec.lifecycle, parsed.metadata.description, (), rel, where), refs))
                elif not isinstance(kind, str):
                    problems.append(Problem(rel, f"{where}.kind",
                                            "kind must be a string such as 'Component'"))
                elif kind.casefold() in _SPELT:
                    problems.append(Problem(rel, f"{where}.kind",
                                            f"kind must be exactly '{_SPELT[kind.casefold()]}'"))
            except ValidationError as exc:
                problems += pydantic_problems(rel, where, exc)
    if not read_any:
        return Catalog((), frozenset()), [*problems,
                                          Problem("catalog/", "(folder)", "no catalog files")]
    if not raw:
        problems.append(Problem("catalog/", "(folder)", "no Component in the catalog"))
    first_seen: dict[str, CatalogComponent] = {}
    for c, _ in raw:
        first_seen.setdefault(c.name.casefold(), c)
    components: list[CatalogComponent] = []
    for c, refs in raw:
        original = first_seen[c.name.casefold()]
        if original is not c:
            problems.append(Problem(c.file, f"{c.where}.metadata.name",
                                    f"{c.name!r} is defined twice "
                                    f"(first at {original.file} {original.where})"))
        owner = REF.fullmatch(c.owner)
        ref_name = (owner["name"] if owner is not None
                    and (owner["kind"] or "group").casefold() == "group" else None)
        group_entry = groups.get(ref_name.casefold()) if ref_name is not None else None
        if group_entry is None:
            shown = ref_name if ref_name is not None else c.owner
            problems.append(Problem(c.file, f"{c.where}.spec.owner",
                                    f"no Group named {shown!r} in the catalog"))
        depends: list[str] = []
        for field, ref in refs:
            m = REF.fullmatch(ref)
            if not m or not m["kind"] or m["kind"].casefold() != "component":
                problems.append(Problem(c.file, field, f"{ref!r} is not component:<name>"))
            elif m["name"].casefold() == c.name.casefold():
                problems.append(Problem(c.file, field, "a component cannot depend on itself"))
            elif m["name"].casefold() not in first_seen:
                problems.append(Problem(c.file, field,
                                        f"no Component named {m['name']!r} in the catalog"))
            else:
                depends.append(first_seen[m["name"].casefold()].name)
        components.append(CatalogComponent(
            c.name, group_entry[0] if group_entry is not None else c.owner, c.type, c.lifecycle,
            c.description, tuple(sorted(set(depends))), c.file, c.where))
    return Catalog(tuple(components), frozenset(g[0] for g in groups.values())), problems


def _namespace(file: str, where: str, metadata: _Metadata) -> list[Problem]:
    """Refs accept only the default namespace, so a document in another one is refused."""
    if metadata.namespace is None or metadata.namespace == "default":
        return []
    return [Problem(file, f"{where}.metadata.namespace", "only the default namespace is read")]
