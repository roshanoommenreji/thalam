#!/usr/bin/env python3
"""Generate Thalam's progress dashboard, docs/dashboard.html (Kaval's dashboard, for Thalam).

Reads the repository and renders one page. Nothing here records status: ROADMAP.md says what is
done, the specs and Lab 00 say what is proven, guardrails.json holds every cost number, and this
only reflects them. A dashboard holding its own copy of "what's done" drifts within two sessions
and then misleads (Kaval's lesson).

Two things come from outside the repository, each from a saved copy that is never committed:
- docs/jira-stories.json: the THL issues (key, title, status, parent epic) and the day they were
  read. Jira owns that list; the page shows it with its date.
- docs/azure-snapshot.json: this month's spend on each budget and whether the Claude deployment is
  parked. `--azure` refreshes it with read-only `az` calls and saves no name, address or ID.
Without a copy the page says so, and the rest of it is still true.

    make dashboard                                        # from the saved copies
    uv run python scripts/tracking/dashboard.py --azure   # read Azure again first

Python 3.11 stdlib only, plus scripts/dev/spec_coverage.py and scripts/ops/azure_cli.py.
"""

from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
import azure_cli  # noqa: E402
import diagrams  # noqa: E402
import spec_coverage  # noqa: E402

CONFIG = Path(__file__).resolve().with_name("dashboard.toml")
ARCH = Path("docs") / "architecture" / "architecture.toml"
OUT = Path("docs") / "dashboard.html"
JIRA_CACHE = Path("docs") / "jira-stories.json"
AZURE_CACHE = Path("docs") / "azure-snapshot.json"
NUMBERS = Path("infra") / "modules" / "azure-guardrails" / "guardrails.json"
BUDGETS_API = "2023-11-01"  # as scripts/ops/azure_cli.py reads the budgets
VIEWS = [
    ("board", "Progress"),
    ("delivery", "Delivery"),
    ("requirements", "Requirements"),
    ("cost", "Cost"),
    ("architecture", "Architecture"),
    ("flows", "Flows"),
    ("azure", "Azure"),
    ("devops", "DevOps"),
    ("decisions", "Decisions"),
    ("glossary", "Glossary"),
]
STATE = {" ": "not started", "~": "in progress", "x": "done", "-": "retired"}

# ── reading the repository ──────────────────────────────────────────────────────────────────


@dataclass
class Task:
    done: bool
    text: str
    subs: list[str] = field(default_factory=list)


@dataclass
class Phase:
    num: int
    title: str
    marker: str
    tasks: list[Task] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # paragraphs and plan steps that are not tasks
    gate: str = ""

    @property
    def done(self) -> int:
        return sum(1 for t in self.tasks if t.done)

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def state(self) -> str:
        return STATE.get(self.marker, "not started")


PHASE_HEAD = re.compile(r"^## Phase (\d+) — (.+?) · `\[(.)\]`\s*$")
TASK = re.compile(r"^- \[([ x])\] (.*)$")
GATE = re.compile(r"^\*\*Exit gate:\*\* (.*)$")
STEP = re.compile(r"^\d+\. ")


def read_roadmap(path: Path) -> list[Phase]:
    """Phases as ROADMAP.md writes them: tasks with their wrapped lines and sub-items, plain
    paragraphs and numbered steps as notes, and the exit gate."""
    phases: list[Phase] = []
    cur: Phase | None = None
    mode = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            head = PHASE_HEAD.match(line)
            cur = Phase(int(head[1]), head[2], head[3]) if head else None
            if cur:
                phases.append(cur)
            mode = ""
            continue
        if cur is None or line.startswith("---"):
            continue
        body = line.strip()
        if not body:
            mode = ""
            continue
        indented = raw[:1] in (" ", "\t")
        if task := TASK.match(line):
            cur.tasks.append(Task(task[1] == "x", task[2]))
            mode = "task"
        elif gate := GATE.match(line):
            cur.gate, mode = gate[1], "gate"
        elif mode == "task" and indented:
            last = cur.tasks[-1]
            if body.startswith("- "):
                last.subs.append(body[2:])
            elif last.subs:
                last.subs[-1] += " " + body
            else:
                last.text += " " + body
        elif mode == "gate":
            cur.gate += " " + body
        elif mode == "note" and (indented or not STEP.match(body)):
            cur.notes[-1] += " " + body
        else:
            cur.notes.append(body)
            mode = "note"
    return phases


def current_phase(phases: list[Phase]) -> Phase | None:
    """The one in progress, else the first not started, else the last one built."""
    for marker in ("~", " "):
        for p in phases:
            if p.marker == marker:
                return p
    built = [p for p in phases if p.marker == "x"]
    return built[-1] if built else None


@dataclass
class Adr:
    num: int
    title: str
    status: str
    day: str
    path: str
    amended_by: list[int]


ADR_HEAD = re.compile(r"^# ADR-(\d{4}) — (.+)$", re.MULTILINE)
ADR_FIELD = re.compile(r"^- \*\*(Status|Date):\*\*\s*(.+)$", re.MULTILINE)
SUPERSEDED = re.compile(r"[Ss]uperseded[^\n]*?ADR-(\d{4})")


def read_adrs(root: Path) -> list[Adr]:
    out: list[Adr] = []
    for path in sorted((root / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        head = ADR_HEAD.search(text)
        if not head:
            continue
        fields = {k: v.strip() for k, v in ADR_FIELD.findall(text)}
        num = int(head[1])
        amended = sorted({int(n) for n in SUPERSEDED.findall(text)} - {num})
        out.append(Adr(num, head[2], fields.get("Status", "?"), fields.get("Date", ""),
                       path.relative_to(root).as_posix(), amended))
    return out


@dataclass
class Spec:
    sid: str
    title: str
    status: str
    amendments: int
    path: str
    plan: str


def read_specs(root: Path) -> list[Spec]:
    out: list[Spec] = []
    for path in sorted((root / spec_coverage.SPECS).glob("SPEC-*.md")):
        text = path.read_text(encoding="utf-8")
        head = re.search(r"^# (SPEC-\d{3}) — (.+)$", text, re.MULTILINE)
        status = spec_coverage.STATUS.search(text)
        if not head or not status:
            continue
        plan = root / spec_coverage.SPECS / "plans" / f"{head[1]}-plan.md"
        out.append(Spec(head[1], head[2], status[1],
                        len(re.findall(r"^- \*\*Amended", text, re.MULTILINE)),
                        path.relative_to(root).as_posix(),
                        plan.relative_to(root).as_posix() if plan.is_file() else ""))
    return out


@dataclass(frozen=True)
class Evidence:
    state: str  # "recorded" or "pending"
    day: str
    section: str


LAB_IDS = re.compile(r"SPEC-(\d{3})-R(\d+)(?:\s+to\s+R(\d+))?")
SHORT_ID = re.compile(r"\bR(\d+)\b")
EVIDENCE = re.compile(r"^\*\*Evidence([^*]*?):\*\*")
DAY = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _ids(text: str, spec: str) -> list[str]:
    """IDs a lab names: `SPEC-001-R13 to R20` is eight; a bare `R13` belongs to `spec`."""
    out: list[str] = []
    for m in LAB_IDS.finditer(text):
        low = int(m[2])
        high = int(m[3]) if m[3] else low
        out += [f"SPEC-{m[1]}-R{n}" for n in range(low, high + 1)]
    if not out and spec:
        out = [f"SPEC-{spec}-R{m[1]}" for m in SHORT_ID.finditer(text)]
    return out


def _better(old: Evidence | None, new: Evidence) -> Evidence:
    if old is None:
        return new
    if (old.state == "recorded") != (new.state == "recorded"):
        return new if new.state == "recorded" else old
    return new if new.day > old.day else old


def read_evidence(text: str) -> dict[str, Evidence]:
    """What a lab says about each requirement. An evidence line that names IDs belongs to them;
    one that names none belongs to the IDs its section's heading names and no other line claims.
    `_not run yet_` anywhere in the paragraph means the proof is still to be recorded."""
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
    found: dict[str, Evidence] = {}
    for heading, lines in sections:
        ids = _ids(heading, "")
        spec = ids[0].split("-")[1] if ids else ""
        items: list[tuple[list[str], str, str]] = []
        i = 0
        while i < len(lines):
            m = EVIDENCE.match(lines[i])
            if not m:
                i += 1
                continue
            block = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip() and not EVIDENCE.match(lines[i]):
                block.append(lines[i])
                i += 1
            items.append((_ids(m[1], spec), m[1], " ".join(block)))
        claimed = {rid for named, _, _ in items for rid in named}
        rest = [rid for rid in ids if rid not in claimed]
        for named, label, para in items:
            day = DAY.search(label) or DAY.search(para)
            ev = Evidence("pending" if spec_coverage.PENDING in para else "recorded",
                          day[0] if day else "", heading)
            for rid in named or rest:
                found[rid] = _better(found.get(rid), ev)
    return found


@dataclass
class Req:
    rid: str
    spec: str
    text: str
    proofs: tuple[str, ...]
    lives: tuple[str, ...]
    cited: tuple[str, ...]
    live: str = ""  # "" (no live proof asked), "recorded", "pending" or "missing"
    live_day: str = ""

    @property
    def kind(self) -> str:
        """proved-live, proved-tests or waiting: how the Requirements view groups it."""
        if self.live == "recorded":
            return "proved-live"
        if self.live in ("pending", "missing"):
            return "waiting"
        return "proved-tests"


def read_requirements(root: Path) -> list[Req]:
    reqs, cited, _ = spec_coverage.check(root)
    texts: dict[str, str] = {}
    for path in sorted((root / spec_coverage.SPECS).glob("SPEC-*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = spec_coverage._cells(line)
            if cells and len(cells) >= 3 and spec_coverage.REQ_ID.fullmatch(cells[0]):
                texts[cells[0]] = cells[1]
    evidence: dict[str, Evidence] = {}
    for lab in sorted({lab for r in reqs for lab in r.lives}):
        if (root / lab).is_file():
            for rid, ev in read_evidence((root / lab).read_text(encoding="utf-8")).items():
                evidence[rid] = _better(evidence.get(rid), ev)
    out: list[Req] = []
    for r in reqs:
        if r.status == "Retired":
            continue
        mine = evidence.get(r.rid)
        live = "" if not r.lives else (mine.state if mine else "missing")
        out.append(Req(r.rid, r.spec, texts.get(r.rid, ""), r.proofs, r.lives,
                       tuple(sorted(cited.get(r.rid, ()))), live,
                       mine.day if mine and live else ""))
    return sorted(out, key=lambda q: (q.spec, int(q.rid.rsplit("R", 1)[1])))


@dataclass
class Pr:
    num: int
    day: str
    kind: str
    key: str
    title: str


@dataclass
class Git:
    head: str = ""
    day: str = ""
    branch: str = ""
    dirty: bool = False
    commits: int = 0
    prs: list[Pr] = field(default_factory=list)


PR_SUBJECT = re.compile(r"^(?P<kind>[a-z]+)(?:\([^)]*\))?: (?:(?P<key>THL-\d+) )?(?P<title>.+?)"
                        r" \(#(?P<num>\d+)\)$")


def _git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              encoding="utf-8", check=False)
    except OSError:
        return ""
    return done.stdout if done.returncode == 0 else ""


def read_git(root: Path) -> Git:
    info = Git(head=_git(root, "rev-parse", "--short", "HEAD").strip(),
               day=_git(root, "log", "-1", "--format=%cd", "--date=short").strip(),
               branch=_git(root, "rev-parse", "--abbrev-ref", "HEAD").strip(),
               dirty=bool(_git(root, "status", "--porcelain").strip()))
    log = _git(root, "log", "--first-parent", "--format=%ad%x1f%s", "--date=short")
    for line in log.splitlines():
        day, _, subject = line.partition("\x1f")
        info.commits += 1
        if m := PR_SUBJECT.match(subject):
            info.prs.append(Pr(int(m["num"]), day, m["kind"], m["key"] or "", m["title"]))
    return info


def count_tests(root: Path) -> dict[str, int]:
    """Test functions per folder (a parametrized test counts once)."""
    out: dict[str, int] = {}
    for top in ("services", "scripts", "infra"):
        for path in sorted((root / top).rglob("test_*.py")):
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(root).parts
            folder = "/".join(rel[:2]) if len(rel) > 2 else rel[0]
            n = len(re.findall(r"^\s*def test_", path.read_text(encoding="utf-8"), re.MULTILINE))
            out[folder] = out.get(folder, 0) + n
    return out


def read_journal(root: Path) -> list[tuple[str, list[str], str]]:
    out: list[tuple[str, list[str], str]] = []
    for path in sorted((root / "docs" / "journal").glob("????-??-??.md"), reverse=True):
        heads = re.findall(r"^## (.+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
        out.append((path.stem, heads, path.relative_to(root).as_posix()))
    return out


def read_future(root: Path) -> list[tuple[str, str]]:
    path = root / "docs" / "future-scope.md"
    if not path.is_file():
        return []
    return re.findall(r"^## (FS-\d+) — (.+)$", path.read_text(encoding="utf-8"), re.MULTILINE)


@dataclass
class Overview:
    """What the architecture overview says in prose: the life cycle, the entities, the boundaries."""

    cycle: list[str] = field(default_factory=list)  # states before the last arrow
    ends: list[str] = field(default_factory=list)  # the possible ends, split by |
    entities: list[tuple[str, str]] = field(default_factory=list)
    bounds: list[str] = field(default_factory=list)


def read_overview(root: Path) -> Overview:
    path = root / "docs" / "architecture" / "overview.md"
    if not path.is_file():
        return Overview()
    text = path.read_text(encoding="utf-8")
    out = Overview()
    if cycle := re.search(r"^## Release life cycle\s+`([^`]+)`", text, re.MULTILINE):
        states = [s.strip() for s in cycle[1].split("→") if s.strip()]
        if states:
            out.ends = [s.strip() for s in states[-1].split("|")]
            out.cycle = states[:-1]
    if section := re.search(r"^## Core entities\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL):
        for line in section[1].splitlines():
            cells = spec_coverage._cells(line)
            if cells and len(cells) >= 2 and not set(cells[0]) <= {"-", " "} and cells[0] != "Table":
                out.entities.append((cells[0], cells[1]))
    if bounds := re.search(r"^## Trust boundaries\n+((?:\d+\..+\n?)+)", text, re.MULTILINE):
        out.bounds = [re.sub(r"^\d+\.\s*", "", b) for b in bounds[1].splitlines() if b.strip()]
    return out


PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def placeholders(n: dict[str, Any]) -> dict[str, str]:
    """The names and numbers architecture.toml may quote, all from guardrails.json."""
    total, model = n["budgets"]["thalam-total"], n["budgets"]["thalam-model"]
    return {
        "ceiling": rupees(n["ceiling"]), "plan": rupees(n["plan"]),
        "total_amount": rupees(total["amount"]), "model_amount": rupees(model["amount"]),
        "total_brake": rupees(total["amount"] * total["brake_at"] / 100),
        "model_brake": rupees(model["amount"] * model["brake_at"] / 100),
        "total_brake_pct": str(total["brake_at"]), "model_brake_pct": str(model["brake_at"]),
        "nightly": f"{n['brake']['nightly_at']} IST", "capacity": str(n["model"]["capacity"]),
        "cap": str(n["model"]["capacity_cap"]), "region": n["region"],
        "lag_days": str(n["runaway"]["lag_days"]), "model": n["model"]["name"],
        "sku": n["model"]["sku"], "resource_group": n["resource_group"],
        "assignment": n["policy"]["assignment"], "action_group": n["brake"]["action_group"],
        "runbook": n["brake"]["runbook"], "schedule": n["brake"]["schedule"],
        "automation_account": n["brake"]["automation_account"],
    }


def fill(value: Any, values: dict[str, str]) -> Any:
    """Every {placeholder} in every string of a TOML tree, filled; an unknown one is left as is."""
    if isinstance(value, str):
        return PLACEHOLDER.sub(lambda m: values.get(m[1], m[0]), value)
    if isinstance(value, list):
        return [fill(v, values) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, values) for k, v in value.items()}
    return value


def read_architecture(root: Path, numbers: dict[str, Any]) -> dict[str, Any]:
    path = root / ARCH
    if not path.is_file():
        return {}
    data: dict[str, Any] = fill(tomllib.loads(path.read_text(encoding="utf-8")),
                                placeholders(numbers))
    return data


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_jira(root: Path) -> dict[str, Any] | None:
    return _load_json(root / JIRA_CACHE)


def read_azure(root: Path) -> dict[str, Any] | None:
    return _load_json(root / AZURE_CACHE)


def load_numbers(root: Path) -> dict[str, Any]:
    numbers: dict[str, Any] = json.loads((root / NUMBERS).read_text(encoding="utf-8"))
    return numbers


def fetch_azure(runner: azure_cli.Runner, numbers: dict[str, Any], env: dict[str, str],
                today: str) -> dict[str, Any]:
    """What exists in Thalam's resource group and what it has cost this month, read-only.

    Keeps amounts, states, resource types and counts, the guardrail checks (the lines
    `make foundry-up` prints) and the model's public name. Never the account, the deployment's
    name, an address or an ID (CLAUDE.md rule 6); an error is Azure's code only."""
    snap: dict[str, Any] = {"read": today, "budgets": {}, "deployments": None, "types": None,
                            "checks": [], "error": ""}
    errors: list[str] = []
    try:
        found = azure_cli.arm_get(
            runner, f"{azure_cli.group_path(numbers)}/providers/Microsoft.Consumption/budgets",
            BUDGETS_API) or {}
        for b in found.get("value", []):
            name = str(b.get("name", ""))
            if name not in numbers["budgets"]:
                continue
            spend = (b.get("properties") or {}).get("currentSpend") or {}
            snap["budgets"][name] = {"spend": float(spend.get("amount") or 0),
                                     "unit": str(spend.get("unit") or numbers["currency"])}
    except azure_cli.AzError as err:
        errors.append(str(err))
    try:
        account = env.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
        if azure_cli.RESOURCE_NAME.match(account):
            snap["deployments"] = [_deployment(d, numbers)
                                   for d in azure_cli.deployments(runner, numbers, account)]
    except azure_cli.AzError as err:
        errors.append(str(err))
    try:
        listed = azure_cli.az_json(runner, ["resource", "list", "--resource-group",
                                            numbers["resource_group"], "-o", "json"]) or []
        types: dict[str, int] = {}
        for r in listed:
            kind = str(r.get("type", "?"))
            types[kind] = types.get(kind, 0) + 1
        snap["types"] = types
    except azure_cli.AzError as err:
        errors.append(str(err))
    snap["checks"] = [{"name": r.name, "ok": r.ok, "detail": r.detail}
                      for r in azure_cli.guardrails(runner, numbers)]
    snap["error"] = "; ".join(sorted(set(errors)))
    return snap


def _deployment(d: dict[str, Any], numbers: dict[str, Any]) -> dict[str, Any]:
    """A deployment's state, capacity and model, and nothing that names or addresses it."""
    props = d.get("properties") or {}
    model = str((props.get("model") or {}).get("name", ""))
    return {"state": str(props.get("provisioningState", "?")),
            "capacity": (d.get("sku") or {}).get("capacity"),
            "model": model if model == numbers["model"]["name"] else "another model"}


@dataclass
class Data:
    config: dict[str, Any]
    phases: list[Phase]
    adrs: list[Adr]
    specs: list[Spec]
    reqs: list[Req]
    git: Git
    tests: dict[str, int]
    journal: list[tuple[str, list[str], str]]
    future: list[tuple[str, str]]
    overview: Overview
    numbers: dict[str, Any]
    arch: dict[str, Any]
    jira: dict[str, Any] | None
    azure: dict[str, Any] | None


def collect(root: Path) -> Data:
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    numbers = load_numbers(root)
    return Data(config, read_roadmap(root / "ROADMAP.md"), read_adrs(root), read_specs(root),
                read_requirements(root), read_git(root), count_tests(root), read_journal(root),
                read_future(root), read_overview(root), numbers,
                read_architecture(root, numbers), read_jira(root), read_azure(root))


# ── writing the page ────────────────────────────────────────────────────────────────────────


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


INLINE = re.compile(r"`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\*\*(.+?)\*\*|(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])")


class Md:
    """The inline Markdown the repo's documents use: code, links, bold and italics. Everything
    else is escaped. A relative link points at the file on GitHub; a link that is neither http(s)
    nor relative is shown as plain text."""

    def __init__(self, repo: str, branch: str) -> None:
        self.repo, self.branch = repo.rstrip("/"), branch

    def url(self, target: str, base: str = "") -> str | None:
        if re.match(r"^https?://", target):
            return target
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
            return None
        path, _, anchor = target.partition("#")
        if not path:
            return None
        joined = posixpath.normpath(posixpath.join(base, path))
        if joined.startswith(".."):
            return None
        kind = "tree" if path.endswith("/") else "blob"
        return f"{self.repo}/{kind}/{self.branch}/{joined}" + (f"#{anchor}" if anchor else "")

    def __call__(self, text: str, base: str = "") -> str:
        out: list[str] = []
        pos = 0
        for m in INLINE.finditer(text):
            out.append(esc(text[pos:m.start()]))
            code, label, target, bold, italic = m.groups()
            if code is not None:
                out.append(f"<code>{esc(code)}</code>")
            elif label is not None:
                href = self.url(target, base)
                inner = self(label, base)
                out.append(f'<a href="{esc(href)}">{inner}</a>' if href else inner)
            elif bold is not None:
                out.append(f"<strong>{self(bold, base)}</strong>")
            else:
                out.append(f"<em>{self(italic, base)}</em>")
            pos = m.end()
        out.append(esc(text[pos:]))
        return "".join(out)


def rupees(amount: float, decimals: int = 0) -> str:
    return f"₹{amount:,.{decimals}f}"


def pill(kind: str, text: str) -> str:
    return f'<span class="pill {esc(kind)}">{esc(text)}</span>'


def _phase_kind(p: Phase) -> str:
    return {"x": "done", "~": "now", "-": "retired"}.get(p.marker, "todo")


STORY_KIND = {"done": "done", "indeterminate": "now", "new": "todo"}


def _stories(jira: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [i for i in (jira or {}).get("issues", []) if i.get("type") != "Epic"]


def _epics(jira: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for i in (jira or {}).get("issues", []):
        m = re.match(r"^Phase (\d+)\b", str(i.get("summary", "")))
        if i.get("type") == "Epic" and m:
            out[int(m[1])] = i
    return out


def _issue_link(i: dict[str, Any]) -> str:
    url = str(i.get("url", ""))
    key = esc(i.get("key", "?"))
    return f'<a class="key" href="{esc(url)}">{key}</a>' if url.startswith("https://") else (
        f'<span class="key">{key}</span>')


def _story_row(i: dict[str, Any]) -> str:
    kind = STORY_KIND.get(str(i.get("category")), "todo")
    return (f'<li class="story">{_issue_link(i)}<span class="stitle">{esc(i.get("summary", ""))}'
            f"</span>{pill(kind, str(i.get('status', '?')))}</li>")


def render_header(d: Data) -> str:
    cfg = d.config["project"]
    now = current_phase(d.phases)
    beats = []
    for p in d.phases:
        kind = _phase_kind(p)
        beats.append(
            f'<li class="beat {kind}"><a href="#phase-{p.num}" title="Phase {p.num} — '
            f'{esc(p.title)}: {esc(p.state)}"><span class="dot" aria-hidden="true"></span>'
            f'<span class="n">{p.num}</span><span class="sr">Phase {p.num}, {esc(p.title)}, '
            f"{esc(p.state)}</span></a></li>")
    git = d.git
    built = (f"main @ <code>{esc(git.head)}</code>" if git.branch == "main"
             else f"{esc(git.branch)} @ <code>{esc(git.head)}</code>") if git.head else "no git"
    local = " · with local changes" if git.dirty else ""
    jira = d.jira.get("read", "?") if d.jira else "no saved copy"
    azure = d.azure.get("read", "?") if d.azure else "no saved copy"
    where = f" · now: Phase {now.num}" if now else ""
    return f"""
<header class="top">
  <div class="wrap top-in">
    <div class="brand-block">
      <h1 class="brand">{esc(cfg["name"])} <span class="ml" lang="ml">{esc(cfg["native"])}</span></h1>
      <p class="tag">{esc(cfg["tagline"])}</p>
      <p class="meta">Built {esc(date.today().isoformat())} from {built}{local} · Jira read {esc(jira)} · Azure read {esc(azure)}</p>
    </div>
    <div class="cycle">
      <p class="eyebrow">Nine phases, one cycle{where}</p>
      <ol class="beats">{"".join(beats)}</ol>
    </div>
  </div>
</header>
<nav class="tabs" aria-label="Views"><div class="wrap tabs-in">{"".join(f'<a href="#{v}">{esc(label)}</a>' for v, label in VIEWS)}</div></nav>
"""


def _tally(reqs: list[Req]) -> dict[str, int]:
    out = {"proved-live": 0, "proved-tests": 0, "waiting": 0}
    for r in reqs:
        out[r.kind] += 1
    return out


def _spend(d: Data, name: str) -> float | None:
    budgets = (d.azure or {}).get("budgets") or {}
    item = budgets.get(name)
    return float(item["spend"]) if isinstance(item, dict) and "spend" in item else None


def _deployment_state(d: Data) -> tuple[str, str]:
    """(kind, words) for the Claude deployment, from the Azure copy."""
    if not d.azure:
        return "todo", "not read"
    if d.azure.get("error"):
        return "bad", f"not read ({d.azure['error']})"
    deps = d.azure.get("deployments")
    if deps is None:
        return "todo", "not read"
    if not deps:
        return "done", "parked"
    states = sorted({str(x.get("state")) for x in deps})
    if states == ["Succeeded"]:
        return "warn", f"up, capacity {deps[0].get('capacity')}"
    return "warn", ", ".join(s.lower() for s in states)


def render_board(d: Data, md: Md) -> str:
    now = current_phase(d.phases)
    tally = _tally(d.reqs)
    stories = _stories(d.jira)
    done_stories = sum(1 for s in stories if s.get("category") == "done")
    total = d.numbers["budgets"]["thalam-total"]["amount"]
    spend = _spend(d, "thalam-total")
    dep_kind, dep_words = _deployment_state(d)
    proved = tally["proved-live"] + tally["proved-tests"]
    stats = [
        ("Now", f"Phase {now.num}" if now else "—",
         f"{now.title}: {now.done} of {now.total} roadmap tasks" if now else ""),
        ("Requirements", f"{proved} of {len(d.reqs)}",
         f"proved; {tally['waiting']} waiting for a live proof"),
        ("Jira stories", f"{done_stories} of {len(stories)}" if d.jira else "—",
         "done" if d.jira else "no saved copy"),
        ("Pull requests", str(len(d.git.prs)), f"merged; {d.git.commits} commits on main"),
        ("This month", rupees(spend, 2) if spend is not None else "—",
         f"of {rupees(total)} on Azure" if spend is not None else "Azure not read"),
        ("Claude", dep_words.split(" (")[0], "deployment on Foundry"),
    ]
    tiles = "".join(
        f'<div class="stat"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>'
        f'<div class="s">{esc(s)}</div></div>' for k, v, s in stats)
    epics = _epics(d.jira)
    rows = []
    for p in d.phases:
        rows.append(render_phase(p, d, md, epics.get(p.num), p is now))
    side = render_side(d, md, now)
    return f"""
<section class="view" id="view-board" aria-labelledby="h-board">
  <h2 id="h-board" class="sr">Progress</h2>
  <div class="stats">{tiles}</div>
  <div class="board">
    <div class="phases">{"".join(rows)}</div>
    {side}
  </div>
</section>"""


def render_phase(p: Phase, d: Data, md: Md, epic: dict[str, Any] | None, is_now: bool) -> str:
    kind = _phase_kind(p)
    pct = round(100 * p.done / p.total) if p.total else 0
    meter = (f'<span class="pmeter"><span class="pbar" role="img" aria-label="{p.done} of '
             f'{p.total} tasks done"><span style="width:{pct}%"></span></span>'
             f'<span class="pcount">{p.done} / {p.total}</span></span>') if p.total else (
        '<span class="pmeter"><span class="pcount wide">plan, no task list yet</span></span>')
    purpose = d.config.get("phases", {}).get(str(p.num), "")
    tasks = "".join(
        f'<li class="{"done" if t.done else "open"}"><span class="tick" aria-hidden="true"></span>'
        f'<span class="sr">{"Done" if t.done else "Open"}: </span><span class="ttext">{md(t.text)}'
        + (f'<ul class="subs">{"".join(f"<li>{md(s)}</li>" for s in t.subs)}</ul>' if t.subs
           else "") + "</span></li>"
        for t in p.tasks)
    notes = "".join(f"<p class=\"note\">{md(n)}</p>" for n in p.notes)
    gate = (f'<div class="gate"><span class="k">Exit gate</span><p>{md(p.gate)}</p></div>'
            if p.gate else "")
    jira = ""
    if d.jira is None:
        jira = '<p class="muted small">No saved copy of Jira, so the stories are not shown.</p>'
    elif epic:
        kids = [s for s in _stories(d.jira) if s.get("parent") == epic.get("key")]
        listing = "".join(_story_row(s) for s in kids) or (
            '<li class="muted small">No stories under this epic yet.</li>')
        jira = (f'<div class="jira"><h4>Jira {_issue_link(epic)} <span class="muted">read '
                f'{esc(d.jira.get("read", "?"))}</span></h4><ul class="stories">{listing}</ul>'
                "</div>")
    return f"""
<details class="phase {kind}" id="phase-{p.num}"{" open" if is_now else ""}>
  <summary>
    <span class="pnum">{p.num}</span>
    <span class="ptitle">{esc(p.title)}</span>
    {pill(kind, p.state)}
    {meter}
  </summary>
  <div class="pbody">
    {f'<p class="purpose">{esc(purpose)}</p>' if purpose else ""}
    {notes}
    {f'<ul class="tasks">{tasks}</ul>' if tasks else ""}
    {gate}
    {jira}
  </div>
</details>"""


def render_side(d: Data, md: Md, now: Phase | None) -> str:
    cards = []
    if now:
        open_tasks = [t for t in now.tasks if not t.done]
        items = "".join(f"<li>{md(t.text)}</li>" for t in open_tasks) or (
            '<li class="muted">Every task is ticked.</li>')
        cards.append(f'<div class="card"><h3>Open in Phase {now.num}</h3>'
                     f'<p class="muted small">Unticked in ROADMAP.md.</p><ul class="plain">'
                     f"{items}</ul></div>")
    moving = [s for s in _stories(d.jira) if s.get("category") in ("indeterminate", "new")]
    if d.jira is not None:
        items = "".join(_story_row(s) for s in moving) or (
            '<li class="muted">Nothing open in Jira.</li>')
        cards.append(f'<div class="card"><h3>Open in Jira</h3><p class="muted small">Read '
                     f'{esc(d.jira.get("read", "?"))}.</p><ul class="stories">{items}</ul></div>')
    waiting = [r for r in d.reqs if r.kind == "waiting"]
    if waiting:
        items = "".join(
            f'<li><a class="key" href="#requirements">{esc(r.rid)}</a> {md(r.text)}</li>'
            for r in waiting)
        cards.append(f'<div class="card"><h3>Waiting for a live proof</h3><ul class="plain">'
                     f"{items}</ul></div>")
    links = "".join(
        f'<li><a href="{esc(link["url"])}">{esc(link["label"])}</a>'
        f'<span class="muted small">{esc(link.get("note", ""))}</span></li>'
        for link in d.config.get("links", []))
    cards.append(f'<div class="card"><h3>Links</h3><ul class="links">{links}</ul></div>')
    return f'<aside class="side">{"".join(cards)}</aside>'


def render_delivery(d: Data, md: Md) -> str:
    repo = d.config["project"]["repo"].rstrip("/")
    prs = "".join(
        f'<tr><td><a class="key" href="{esc(repo)}/pull/{p.num}">#{p.num}</a></td>'
        f'<td class="num">{esc(p.day)}</td><td>{pill("kind", p.kind)}</td>'
        f'<td><span class="key">{esc(p.key)}</span></td><td>{md(p.title)}</td></tr>'
        for p in d.git.prs)
    if d.jira is None:
        jira = '<p class="muted">No saved copy of Jira.</p>'
    else:
        order = {"indeterminate": 0, "new": 1, "done": 2}
        phase_of = {e.get("key"): n for n, e in _epics(d.jira).items()}
        rows = sorted(_stories(d.jira), key=lambda s: (order.get(str(s.get("category")), 3),
                                                       int(str(s.get("key", "0-0")).split("-")[1])))
        jira = ('<div class="scroll"><table><thead><tr><th>Story</th><th>Title</th>'
                "<th>Phase</th><th>Status</th></tr></thead><tbody>" + "".join(
                    f"<tr><td>{_issue_link(s)}</td><td>{esc(s.get('summary', ''))}</td>"
                    f'<td class="num">{esc(phase_of.get(s.get("parent"), "—"))}</td>'
                    f"<td>{pill(STORY_KIND.get(str(s.get('category')), 'todo'), str(s.get('status')))}"
                    "</td></tr>" for s in rows) + "</tbody></table></div>"
                f'<p class="muted small">Jira read {esc(d.jira.get("read", "?"))}.</p>')
    journal = "".join(
        f'<li><a href="{esc(md.url(path) or "")}"><span class="num">{esc(day)}</span></a>'
        f'<ul class="plain">{"".join(f"<li>{md(h)}</li>" for h in heads)}</ul></li>'
        for day, heads, path in d.journal)
    tests = "".join(f'<tr><td><code>{esc(k)}</code></td><td class="num">{v}</td></tr>'
                    for k, v in sorted(d.tests.items()))
    counts = [("Commits on main", d.git.commits), ("Pull requests merged", len(d.git.prs)),
              ("Test functions", sum(d.tests.values())), ("ADRs", len(d.adrs)),
              ("Specs", len(d.specs)), ("Journal days", len(d.journal))]
    figures = "".join(f'<div class="fig"><span class="v">{v}</span><span class="k">{esc(k)}'
                      "</span></div>" for k, v in counts)
    return f"""
<section class="view" id="view-delivery" aria-labelledby="h-delivery" hidden>
  <h2 id="h-delivery">Delivery</h2>
  <div class="figs">{figures}</div>
  <div class="two">
    <div class="min0">
      <h3>Merged pull requests</h3>
      <div class="scroll"><table><thead><tr><th>PR</th><th>Merged</th><th>Kind</th><th>Story</th><th>Title</th></tr></thead><tbody>{prs}</tbody></table></div>
      <h3>Jira stories</h3>
      {jira}
    </div>
    <div class="min0">
      <h3>Journal</h3>
      <ul class="journal">{journal}</ul>
      <h3>Tests by folder</h3>
      <div class="scroll"><table class="narrow"><thead><tr><th>Folder</th><th>Test functions</th></tr></thead><tbody>{tests}</tbody></table></div>
      <p class="muted small">A parametrized test counts once here; pytest runs each case.</p>
    </div>
  </div>
</section>"""


KIND_WORDS = {"proved-live": "Proved live", "proved-tests": "Proved by tests or files",
              "waiting": "Waiting for a live proof"}


def _req_state(r: Req) -> str:
    if r.live == "recorded":
        return pill("done", f"live · {r.live_day}" if r.live_day else "live")
    if r.live == "pending":
        return pill("warn", "live proof not run yet")
    if r.live == "missing":
        return pill("warn", "no evidence line")
    return pill("tests", "tests" if r.cited else "files")


def render_requirements(d: Data, md: Md) -> str:
    specs = "".join(
        f'<div class="card spec"><div class="spec-head"><span class="key">{esc(s.sid)}</span>'
        f'{pill("done" if s.status in ("Built", "Amended") else "now", s.status)}</div>'
        f'<p class="spec-title">{esc(s.title)}</p><p class="muted small">{s.amendments} '
        f'amendments, each approved by Roshan. <a href="{esc(md.url(s.path) or "")}">Spec</a>'
        + (f' · <a href="{esc(md.url(s.plan) or "")}">Plan</a>' if s.plan else "")
        + "</p></div>" for s in d.specs)
    tally = _tally(d.reqs)
    total = max(1, len(d.reqs))
    parts = "".join(
        f'<span class="seg {k}" style="width:{100 * n / total:.2f}%" '
        f'title="{esc(KIND_WORDS[k])}: {n}"></span>' for k, n in tally.items() if n)
    legend = "".join(f'<li><span class="sw {k}" aria-hidden="true"></span>{esc(KIND_WORDS[k])} '
                     f'<span class="num">{n}</span></li>' for k, n in tally.items())

    def proof(r: Req) -> str:
        files = [p for p in r.proofs if p not in r.lives]
        bits = [f'<a href="{esc(md.url(p.split("::")[0]) or "")}"><code>'
                f'{esc(p.split("/")[-1])}</code></a>' for p in files]
        bits += [f'<a href="{esc(md.url(p) or "")}"><code>{esc(p.split("/")[-1])}</code></a> '
                 '<span class="muted small">live</span>' for p in r.lives]
        cited = (f'<span class="muted small">cited by {len(r.cited)} file'
                 f'{"s" if len(r.cited) != 1 else ""}</span>') if r.cited else ""
        return "<br>".join(bits) + (f"<br>{cited}" if cited else "")

    rows = "".join(
        f'<tr class="{r.kind}"><td><span class="key">{esc(r.rid.split("-", 2)[2])}</span></td>'
        f"<td>{md(r.text)}</td><td>{proof(r)}</td><td>{_req_state(r)}</td></tr>"
        for r in d.reqs)
    return f"""
<section class="view" id="view-requirements" aria-labelledby="h-req" hidden>
  <h2 id="h-req">Requirements</h2>
  <p class="lede">A requirement with no test is a wish (ADR-0010). Each row comes from the spec's table, its citations from <code># covers:</code> tags, and its live proof from the lab's evidence lines.</p>
  <div class="specs">{specs}</div>
  <div class="card">
    <div class="segbar" role="img" aria-label="{tally['proved-live']} proved live, {tally['proved-tests']} proved by tests, {tally['waiting']} waiting">{parts}</div>
    <ul class="legend">{legend}</ul>
  </div>
  <div class="scroll"><table class="reqs"><thead><tr><th>ID</th><th>Requirement</th><th>Proved by</th><th>State</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>"""


def meter_svg(amount: float, marks: list[tuple[float, str, str]], spend: float | None,
              plan: float | None, label: str) -> str:
    """A budget drawn to scale: the track is the budget, ticks are its alert lines, the fill is
    this month's spend. Labels sit in two rows above so close lines never collide."""
    width, pad = 640.0, 6.0
    inner = width - 2 * pad

    def x(v: float) -> float:
        return pad + inner * min(max(v, 0.0), amount) / amount

    first_alert = min(v for v, _, _ in marks)
    brake = max(v for v, _, k in marks if k == "brake")
    level = "good" if spend is None or spend < first_alert else (
        "warn" if spend < brake else "bad")
    out = [f'<svg class="meter" viewBox="0 0 {width:.0f} 92" role="img" '
           f'aria-label="{esc(label)}">',
           f'<rect class="track {level}" x="{pad}" y="40" width="{inner:.1f}" height="12" '
           'rx="6"/>']
    if spend:
        out.append(f'<rect class="fill {level}" x="{pad}" y="40" '
                   f'width="{max(x(spend) - pad, 4):.1f}" height="12" rx="6"/>')
    for i, (v, text, kind) in enumerate(sorted(marks)):
        px = x(v)
        anchor = "end" if px > width - 70 else ("start" if px < 70 else "middle")
        ty = 14 if i % 2 == 0 else 29
        out.append(f'<g class="mark {kind}"><title>{esc(text)}</title>'
                   f'<line x1="{px:.1f}" x2="{px:.1f}" y1="{ty + 5}" y2="58"/>'
                   f'<text x="{px:.1f}" y="{ty}" text-anchor="{anchor}">{esc(text)}</text></g>')
    if plan is not None:
        px = x(plan)
        out.append(f'<g class="mark plan"><title>Plan: {esc(rupees(plan))}</title>'
                   f'<line x1="{px:.1f}" x2="{px:.1f}" y1="36" y2="64"/>'
                   f'<text x="{px:.1f}" y="80" text-anchor="middle">plan {esc(rupees(plan))}'
                   "</text></g>")
    out.append(f'<text class="axis" x="{pad}" y="80">₹0</text>')
    out.append(f'<text class="axis" x="{width - pad}" y="80" text-anchor="end">'
               f"{esc(rupees(amount))}</text></svg>")
    return "".join(out)


def render_cost(d: Data, md: Md) -> str:
    n = d.numbers
    cards = []
    for name, title in (("thalam-total", "Everything on Azure"), ("thalam-model", "The model")):
        b = n["budgets"][name]
        amount = float(b["amount"])
        marks = [(amount * t / 100, f"{t}% {rupees(amount * t / 100)}",
                  "brake" if t == b["brake_at"] else "alert") for t in b["alerts"]]
        spend = _spend(d, name)
        plan = float(n["plan"]) if name == "thalam-total" else None
        words = (f"{rupees(spend, 2)} spent this month" if spend is not None
                 else "Spend not read yet")
        brake_words = f"the brake fires at {b['brake_at']}% ({rupees(amount * b['brake_at'] / 100)})"
        cards.append(f"""
<div class="card">
  <div class="meter-head"><h3>{esc(title)} <span class="key">{esc(name)}</span></h3><span class="spend">{esc(words)}</span></div>
  {meter_svg(amount, marks, spend, plan, f"{title}: budget {rupees(amount)}, {words}")}
  <p class="muted small">Alerts at {" / ".join(str(t) for t in b["alerts"])} % of {rupees(amount)} by e-mail; {esc(brake_words)} and deletes the deployment.</p>
</div>""")
    r = n["runaway"]
    per_day = (r["tokens_per_minute_per_unit"] * 60 * 24
               * (r["usd_per_million_input"] + r["usd_per_million_output"]) / 1e6
               * r["inr_per_usd"])
    model = n["model"]
    cap = model["capacity_cap"]
    dep_kind, dep_words = _deployment_state(d)
    by_id = {q.rid: q for q in d.reqs}
    guards = "".join(
        f'<li><span class="key">{esc(rid.split("-", 2)[2])}</span><span>{md(by_id[rid].text)}'
        f"</span>{_req_state(by_id[rid])}</li>"
        for rid in d.config.get("cost", {}).get("guardrail_requirements", []) if rid in by_id)
    banned = "".join(f'<span class="chip">{esc(t.split("/")[-1])}</span>'
                     for t in n["policy"]["not_allowed_types"])
    read = (f"Azure read {esc(d.azure.get('read', '?'))}." if d.azure
            else "Azure has not been read: run <code>make dashboard-azure</code>.")
    brake = n["brake"]
    return f"""
<section class="view" id="view-cost" aria-labelledby="h-cost" hidden>
  <h2 id="h-cost">Cost</h2>
  <p class="lede">At most {rupees(n["ceiling"])} a month, planned under {rupees(n["plan"])} ({md("[ADR-0013](docs/adr/0013-cost-ceiling-1500-inr.md)")}). Every number here is read from <code>guardrails.json</code>; spend comes from Azure's budgets, which lag by up to {r["lag_days"]} days. {read}</p>
  <div class="two">{"".join(cards)}</div>
  <div class="two">
    <div class="card">
      <h3>The Claude deployment</h3>
      <p class="big">{pill(dep_kind, dep_words)}</p>
      <dl class="facts">
        <dt>Model</dt><dd><code>{esc(model["name"])}</code>, {esc(model["sku"])}</dd>
        <dt>Capacity</dt><dd>{model["capacity"]}, with a cap of {cap} in Azure Policy</dd>
        <dt>Region</dt><dd><code>{esc(n["region"])}</code></dd>
        <dt>Nightly park</dt><dd>{esc(brake["nightly_at"])} IST, whatever the spend</dd>
      </dl>
    </div>
    <div class="card">
      <h3>If it were left running</h3>
      <dl class="facts">
        <dt>Capacity 1</dt><dd>about {rupees(per_day)} a day at full use</dd>
        <dt>The cap of {cap}</dt><dd>about {rupees(round(per_day) * cap)} a day</dd>
        <dt>{r["lag_days"]} days unseen</dt><dd>about {rupees(round(per_day) * cap * r["lag_days"])}, inside the {rupees(n["ceiling"] - n["plan"])} between plan and ceiling</dd>
      </dl>
      <p class="muted small">Budgets only alert, and late; Azure pay-as-you-go has no hard limit. That is why the deployment is parked by default and the brake also runs every night ({md("[ADR-0014](docs/adr/0014-azure-cost-guardrails.md)")}).</p>
    </div>
  </div>
  <div class="card">
    <h3>The guardrails, as requirements</h3>
    <ul class="guards">{guards}</ul>
  </div>
  <div class="card">
    <h3>Refused by Azure Policy on <code>{esc(n["resource_group"])}</code></h3>
    <div class="chips">{banned}</div>
    <p class="muted small">Also refused: any region but {", ".join(f"<code>{esc(x)}</code>" for x in n["policy"]["allowed_locations"])}, any account kind but {", ".join(esc(x) for x in n["policy"]["allowed_account_kinds"])}, and AI Search above the {", ".join(esc(x) for x in n["policy"]["allowed_search_skus"])} tier.</p>
  </div>
</section>"""


# ── Architecture, Flows, Azure, DevOps, Glossary: from docs/architecture/architecture.toml ───

STATE_WORDS = {
    "built": "built", "now": "being built", "planned": "planned", "retired": "retired",
    "external": "outside Thalam", "missing": "not found", "parked": "parked", "up": "up",
    "unknown": "not checked", "live": "in use",
}
STATE_PILL = {
    "built": "done", "now": "now", "planned": "todo", "retired": "todo", "external": "kind",
    "missing": "bad", "parked": "done", "up": "warn", "unknown": "todo", "live": "done",
}
NODE_KINDS = {
    "source": "Source, read-only", "service": "Service", "store": "Store", "guard": "Guard",
    "model": "Model", "surface": "Where people meet it", "target": "Target, written by the executor",
    "platform": "Platform", "rg": "In the resource group", "outside": "Outside the resource group",
    "local": "On the laptop", "github": "GitHub", "check": "Required check", "gate": "Gate",
    "planned": "Planned",
}
Look = tuple[str, str]  # (state class, words for the pill)


def _phase_look(phase: Any, d: Data) -> Look:
    """built, being built, planned or outside Thalam, from the phase's marker in ROADMAP.md."""
    if phase is None or phase == "":
        return "external", STATE_WORDS["external"]
    state = "planned"
    for p in d.phases:
        if p.num == int(phase):
            state = {"x": "built", "~": "now", "-": "retired"}.get(p.marker, "planned")
    return state, STATE_WORDS[state]


def _azure_look(n: dict[str, Any], d: Data) -> Look:
    """Whether an Azure node exists, from the saved Azure copy (`make dashboard-azure`)."""
    if n.get("kind") == "outside":
        return _phase_look(n.get("phase"), d)
    live, snap = str(n.get("live", "")), d.azure
    if not live:
        return "unknown", "managed by Terraform, not checked"
    if not snap:
        return "unknown", "Azure not read"
    if live == "deployment":
        deps = snap.get("deployments")
        if deps is None:
            return "unknown", "not read"
        return ("parked", "parked") if not deps else ("up", f"up, capacity {deps[0].get('capacity')}")
    if live.startswith("type:"):
        types = snap.get("types")
        if types is None:
            return "unknown", "not read"
        count = sum(v for k, v in types.items() if k.lower() == live[5:].lower())
        return ("built", f"exists ×{count}") if count else ("missing", "not found")
    if live.startswith("budget:"):
        return ("built", "exists") if live[7:] in (snap.get("budgets") or {}) else (
            "missing", "not found")
    if live.startswith("check:"):
        for c in snap.get("checks") or []:
            if str(c.get("name", "")).startswith(live[6:]):
                return ("built", "check passes") if c.get("ok") else ("missing", "check fails")
    return "unknown", "not checked"


def _devops_look(n: dict[str, Any], d: Data) -> Look:
    return _phase_look(n.get("phase"), d) if n.get("phase") is not None else (
        "live", STATE_WORDS["live"])


def _nodes(section: str, d: Data, look: Callable[[dict[str, Any], Data], Look]
           ) -> list[diagrams.Node]:
    out = []
    for n in d.arch.get(section, {}).get("node", []):
        phase = n.get("phase")
        out.append(diagrams.Node(
            id=n["id"], label=n["label"], col=float(n["col"]), row=float(n["row"]),
            sub=n.get("sub", ""), kind=n.get("kind", ""), state=look(n, d)[0],
            badge="" if phase is None else str(phase), href=f"{section}-{n['id']}",
            title=f"{n['label']}: {n.get('definition', '')}"))
    return out


def _edges(section: str, d: Data) -> list[diagrams.Edge]:
    return [diagrams.Edge(e["from"], e["to"], e.get("label", ""), e.get("kind", "data"),
                          float(e.get("at", 0.5)))
            for e in d.arch.get(section, {}).get("edge", [])]


def _legend(states: list[str], badge: bool = True) -> str:
    lines = "".join(
        f'<li><svg class="key-line" viewBox="0 0 36 10" aria-hidden="true"><line class="edge '
        f'{k}" x1="1" y1="5" x2="35" y2="5"/></svg>{esc(w)}</li>'
        for k, w in (("data", "data or a call"), ("control", "a decision or a trigger"),
                     ("write", "a write that changes something")))
    boxes = "".join(f'<li><span class="key-box {s}" aria-hidden="true"></span>'
                    f"{esc(STATE_WORDS[s])}</li>" for s in states)
    mark = ('<li><span class="key-badge" aria-hidden="true">2</span>the roadmap phase that '
            "builds it</li>") if badge else ""
    return f'<ul class="legend diagram-legend">{lines}{boxes}{mark}</ul>'


def _figure(svg: str, caption: str) -> str:
    return (f'<figure class="diagram-wrap"><div class="diagram-scroll">{svg}</div>'
            f"<figcaption>{caption}</figcaption></figure>")


FACTS = {
    "architecture": (("access", "Access"),),
    "azure": (("type", "Azure type"), ("name", "Name"), ("created_by", "Created by"),
              ("cost", "Cost"), ("requirement", "Proved by")),
    "devops": (("file", "Defined in"),),
    "infra": (("file", "Defined in"),),
}


def _cards(section: str, d: Data, md: Md, look: Callable[[dict[str, Any], Data], Look]) -> str:
    """One card per node: what it is, what goes in and out, and which nodes it talks to."""
    nodes = d.arch.get(section, {}).get("node", [])
    names = {n["id"]: n["label"] for n in nodes}
    edges = d.arch.get(section, {}).get("edge", [])

    def link(nid: str, label: str) -> str:
        tail = f' <span class="muted">({esc(label)})</span>' if label else ""
        return f'<a href="#{esc(section)}-{esc(nid)}">{esc(names.get(nid, nid))}</a>{tail}'

    out = []
    for n in nodes:
        state, words = look(n, d)
        froms = [link(e["from"], e.get("label", "")) for e in edges if e["to"] == n["id"]]
        tos = [link(e["to"], e.get("label", "")) for e in edges if e["from"] == n["id"]]
        facts = "".join(f"<dt>{esc(title)}</dt><dd>{md(str(n[key]))}</dd>"
                        for key, title in FACTS.get(section, ()) if n.get(key))
        phase = f" · Phase {n['phase']}" if n.get("phase") is not None else ""
        ins = "".join(f"<li>{md(x)}</li>" for x in n.get("inputs", []))
        outs = "".join(f"<li>{md(x)}</li>" for x in n.get("outputs", []))
        talks = ""
        if froms or tos:
            talks = ('<p class="small talks">'
                     + (f"<span>From: {', '.join(froms)}</span>" if froms else "")
                     + (f"<span>To: {', '.join(tos)}</span>" if tos else "") + "</p>")
        out.append(f"""
<article class="ncard {esc(state)}" id="{esc(section)}-{esc(n['id'])}">
  <header><h4>{esc(n['label'])}</h4>{pill(STATE_PILL.get(state, 'todo'), words)}</header>
  <p class="muted small">{esc(NODE_KINDS.get(n.get('kind', ''), n.get('kind', '')))}{esc(phase)}</p>
  <p>{md(n.get('definition', ''))}</p>
  {f'<dl class="facts">{facts}</dl>' if facts else ''}
  <div class="io"><div><h5>In</h5><ul>{ins}</ul></div><div><h5>Out</h5><ul>{outs}</ul></div></div>
  {talks}
</article>""")
    return f'<div class="ncards">{"".join(out)}</div>'


def render_architecture(d: Data, md: Md) -> str:
    def look(n: dict[str, Any], dd: Data) -> Look:
        return _phase_look(n.get("phase"), dd)

    nodes = _nodes("architecture", d, look)
    graph = diagrams.graph(nodes, _edges("architecture", d), uid="arch",
                           aria="Thalam's components: sources feed the collector and the release "
                                "graph; the agent reads and proposes; policy and a person decide; "
                                "only the executor writes to outside systems.")
    o = d.overview
    life = diagrams.chain(o.cycle, o.ends, uid="life",
                          aria="A release's life cycle: " + " then ".join(o.cycle + o.ends[:1])
                          ) if o.cycle else ""
    entities = "".join(f"<tr><td>{md(a)}</td><td>{md(b)}</td></tr>" for a, b in o.entities)
    bounds = "".join(f"<li>{md(b)}</li>" for b in o.bounds)
    return f"""
<section class="view" id="view-architecture" aria-labelledby="h-arch" hidden>
  <h2 id="h-arch">Architecture</h2>
  <p class="lede">A release coordinator that is allowed to think, but not allowed to act. Read top to bottom: sources feed the release graph, the agent reads it and proposes, policy and a person decide, and only the executor writes to outside systems (CLAUDE.md rule 3). Each part's state comes from its phase in ROADMAP.md; select a part to read its definition and what flows in and out.</p>
  {_legend(["built", "now", "planned", "external"])}
  {_figure(graph, "Every arrow into an outside system starts at the executor, and every write the agent makes is a proposal. The hosted model's cost guardrails are on the Azure view.")}
  <h3 class="sect">Every part, defined</h3>
  {_cards("architecture", d, md, look)}
  <div class="two">
    <div class="card"><h3>A release's life cycle</h3>{_figure(life, "Each arrow that touches an outside system is a proposal.") if life else ""}</div>
    <div class="card"><h3>Trust boundaries</h3><ol class="plain-num">{bounds}</ol></div>
  </div>
  <h3 class="sect">What the release graph stores</h3>
  <div class="scroll"><table><thead><tr><th>Table</th><th>Meaning</th></tr></thead><tbody>{entities}</tbody></table></div>
</section>"""


def render_flows(d: Data, md: Md) -> str:
    flows = d.arch.get("flow", [])
    index, blocks = [], []
    for f in flows:
        state, words = _phase_look(f.get("phase"), d)
        lanes = [(str(a), str(b)) for a, b in f["lanes"]]
        label = dict(lanes)
        steps = [diagrams.Step(s["from"], s["to"], s["label"], s.get("kind", "call"))
                 for s in f["steps"]]
        svg = diagrams.sequence(lanes, steps, uid=f["id"],
                                aria=f"{f['title']}: {len(steps)} steps between "
                                     f"{', '.join(label.values())}.")
        rows = "".join(
            f'<li><strong>{esc(s["label"])}</strong> <span class="muted small">'
            f'{esc(label.get(s["from"], s["from"]))} → {esc(label.get(s["to"], s["to"]))}'
            f"</span><br>{md(s.get('note', ''))}</li>" for s in f["steps"])
        badge = pill(STATE_PILL.get(state, "todo"), f"Phase {f.get('phase')}: {words}")
        index.append(f'<li><a href="#{esc(f["id"])}">{esc(f["title"])}</a> {badge}</li>')
        blocks.append(f"""
<article class="card flow" id="{esc(f['id'])}">
  <div class="flow-head"><h3>{esc(f['title'])}</h3>{badge}</div>
  <p><strong>Starts when:</strong> {md(f.get('trigger', ''))}</p>
  {_figure(svg, "Solid arrows are calls, dashed arrows are replies, and the coloured ones change something outside the caller.")}
  <ol class="steps">{rows}</ol>
  <p class="outcome"><strong>Ends with:</strong> {md(f.get('outcome', ''))}</p>
</article>""")
    return f"""
<section class="view" id="view-flows" aria-labelledby="h-flows" hidden>
  <h2 id="h-flows">Flows</h2>
  <p class="lede">What happens, step by step, for each thing Thalam does: who calls whom, what passes between them, and where a person decides. The two Phase 0 flows run today; the others are the design each later phase builds to.</p>
  <ul class="flow-index">{"".join(index)}</ul>
  {"".join(blocks)}
</section>"""


def render_azure(d: Data, md: Md) -> str:
    n = d.numbers
    graph = diagrams.graph(_nodes("azure", d, _azure_look), _edges("azure", d), uid="az",
                           aria=f"Thalam's resources in {n['resource_group']}: the deployment's "
                                "charges reach two budgets; their brake lines notify the action "
                                "group, whose webhook starts the runbook that deletes the "
                                "deployment; a nightly schedule starts it too.")
    snap = d.azure or {}
    def check(c: dict[str, Any]) -> str:
        detail = f'<span class="muted">{esc(c["detail"])}</span>' if c.get("detail") else ""
        verdict = pill("done", "PASS") if c.get("ok") else pill("bad", "FAIL")
        return f'<li>{verdict}<span>{esc(c.get("name", ""))}</span>{detail}</li>'

    checks = "".join(check(c) for c in snap.get("checks") or [])
    types = "".join(f'<tr><td><code>{esc(k)}</code></td><td class="num">{v}</td></tr>'
                    for k, v in sorted((snap.get("types") or {}).items()))
    read = (f"Read {esc(snap.get('read', '?'))} with <code>make dashboard-azure</code>"
            + (f"; errors: {esc(snap['error'])}" if snap.get("error") else "") + "."
            ) if d.azure else "Azure has not been read: run <code>make dashboard-azure</code>."
    return f"""
<section class="view" id="view-azure" aria-labelledby="h-azure" hidden>
  <h2 id="h-azure">Azure</h2>
  <p class="lede">Everything Thalam has in Azure lives in one resource group, <code>{esc(n['resource_group'])}</code> in <code>{esc(n['region'])}</code>, on a pay-as-you-go subscription billed in rupees. Terraform creates the guardrails (<code>infra/modules/azure-guardrails</code>); <code>make foundry-up</code> creates the one deployment, and it is parked by default. {read}</p>
  {_legend(["built", "missing", "parked", "up", "unknown", "external"])}
  {_figure(graph, "Follow the loop clockwise from the deployment: charges, budgets, the brake line, the action group, the webhook, the runbook, and the DELETE back to the deployment. The policy fences what may exist at all.")}
  <div class="two">
    <div class="card"><h3>Guardrail checks</h3><p class="muted small">The lines <code>make foundry-up</code> prints before it creates anything.</p><ul class="checks">{checks or '<li class="muted">Not read yet.</li>'}</ul></div>
    <div class="card"><h3>Resource types in the group</h3><div class="scroll"><table class="narrow"><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>{types or '<tr><td colspan="2" class="muted">Not read yet.</td></tr>'}</tbody></table></div><p class="muted small">Types and counts only; names are never saved.</p></div>
  </div>
  <h3 class="sect">Every resource, defined</h3>
  {_cards("azure", d, md, _azure_look)}
</section>"""


def _required_checks(root: Path) -> list[str]:
    path = root / ".github" / "rulesets" / "main.json"
    ruleset = _load_json(path) or {}
    for rule in ruleset.get("rules", []):
        if rule.get("type") == "required_status_checks":
            return [str(c.get("context")) for c in
                    rule.get("parameters", {}).get("required_status_checks", [])]
    return []


def render_devops(d: Data, md: Md) -> str:
    pipeline = diagrams.graph(_nodes("devops", d, _devops_look), _edges("devops", d),
                              uid="dev", aria="From a story branch through two hooks and the "
                                              "local checks to a pull request, five required "
                                              "checks, the ruleset and a squash merge to main; "
                                              "Phase 7 adds build once, staging and production.")
    infra = diagrams.graph(_nodes("infra", d, _devops_look), _edges("infra", d), uid="infra",
                           aria="Azure changes by a saved Terraform plan that Roshan applies; "
                                "the sweep reads the result.")
    required = "".join(f"<li><code>{esc(c)}</code></li>" for c in _required_checks(ROOT))
    total = sum(d.tests.values())
    return f"""
<section class="view" id="view-devops" aria-labelledby="h-devops" hidden>
  <h2 id="h-devops">DevOps</h2>
  <p class="lede">How a change reaches <code>main</code>, and how Azure changes. Code goes by pull request only, behind five required checks; Azure goes by a Terraform plan that is read before it is applied. From Phase 7 the same <code>main</code> builds one signed image that is promoted, never rebuilt.</p>
  {_legend(["live", "planned"])}
  {_figure(pipeline, "Left to right: the laptop's hooks and checks, the pull request, the five checks the ruleset requires by name, the merge. The right-hand column is Phase 7.")}
  <div class="two">
    <div class="card"><h3>Required on main</h3><p class="muted small">Read from <code>.github/rulesets/main.json</code>.</p><ul class="plain">{required}</ul></div>
    <div class="card"><h3>What the checks run</h3><dl class="facts"><dt>Tests</dt><dd>{total} test functions; pytest runs each parametrized case</dd><dt>Lint</dt><dd>ruff and mypy --strict</dd><dt>Secrets</dt><dd>gitleaks, before each commit and over all history in CI</dd><dt>Scanning</dt><dd>CodeQL on Python and on the workflows; Dependabot weekly</dd></dl></div>
  </div>
  <h3 class="sect">Changing Azure</h3>
  {_figure(infra, "Nothing reaches Azure without a saved plan, and nothing is applied without Roshan's go. The sweep closes every session.")}
  <h3 class="sect">Every stage, defined</h3>
  {_cards("devops", d, md, _devops_look)}
  {_cards("infra", d, md, _devops_look)}
</section>"""


def render_glossary(d: Data, md: Md) -> str:
    groups: dict[str, list[dict[str, Any]]] = {}
    for g in d.arch.get("glossary", []):
        groups.setdefault(g.get("group", "Other"), []).append(g)
    parts = []
    for name, terms in groups.items():
        items = "".join(
            f'<div class="term" id="term-{esc(re.sub(r"[^a-z0-9]+", "-", t["term"].lower()).strip("-"))}">'
            f'<dt>{esc(t["term"])}</dt><dd>{md(t["definition"])}'
            f'<span class="muted small where">Seen in: {esc(t.get("where", ""))}</span></dd></div>'
            for t in terms)
        parts.append(f'<div class="card"><h3>{esc(name)}</h3><dl class="glossary">{items}</dl></div>')
    return f"""
<section class="view" id="view-glossary" aria-labelledby="h-glossary" hidden>
  <h2 id="h-glossary">Glossary</h2>
  <p class="lede">The words this project uses, each defined once, with where you meet it on this page.</p>
  <div class="gloss-grid">{"".join(parts)}</div>
</section>"""


def render_decisions(d: Data, md: Md) -> str:
    rows = "".join(
        f'<tr><td><a class="key" href="{esc(md.url(a.path) or "")}">ADR-{a.num:04d}</a></td>'
        f"<td>{md(a.title)}"
        + ("".join(f'<span class="muted small amended">Amended in part by ADR-{n:04d}</span>'
                   for n in a.amended_by))
        + f'</td><td class="num">{esc(a.day)}</td><td>{pill("done" if a.status == "Accepted" else "todo", a.status)}</td></tr>'
        for a in d.adrs)
    future = "".join(f'<li><span class="key">{esc(k)}</span> {md(t)}</li>' for k, t in d.future)
    return f"""
<section class="view" id="view-decisions" aria-labelledby="h-decisions" hidden>
  <h2 id="h-decisions">Decisions</h2>
  <p class="lede">Every decision that shaped Thalam, in the order it was made. A later ADR amends an earlier one with a dated note; nothing is rewritten (ADR-0001).</p>
  <div class="scroll"><table><thead><tr><th>ADR</th><th>Decision</th><th>Date</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>
  <div class="card"><h3>Beyond v1: future scope</h3><ul class="plain">{future}</ul></div>
</section>"""


def render(d: Data) -> str:
    project = d.config["project"]
    md = Md(project["repo"], project.get("branch", "main"))
    body = "".join([render_header(d), '<main class="wrap">', render_board(d, md),
                    render_delivery(d, md), render_requirements(d, md), render_cost(d, md),
                    render_architecture(d, md), render_flows(d, md), render_azure(d, md),
                    render_devops(d, md), render_decisions(d, md), render_glossary(d, md),
                    "</main>",
                    FOOTER.format(name=esc(project["name"]))])
    style = CONFIG.with_name("dashboard.css").read_text(encoding="utf-8")
    script = CONFIG.with_name("dashboard.js").read_text(encoding="utf-8")
    return f"{HEAD}<style>\n{style}</style>\n{body}\n<script>\n{script}</script>\n"


FONTS = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;"
         "12..96,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600"
         "&family=Manjari:wght@400;700&display=swap")
HEAD = f"""<meta charset="utf-8">
<title>Thalam Metronome</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
"""
FOOTER = (
    '<footer class="wrap"><p>{name}\'s dashboard, built by <code>scripts/tracking/dashboard.py'
    "</code> from ROADMAP.md, the specs, labs, ADRs and journal, git, and saved copies of Jira "
    "and Azure. It records no status of its own: when this page and ROADMAP.md disagree, "
    "ROADMAP.md is right and this page is stale. Rebuild with <code>make dashboard</code>."
    "</p></footer>"
)


def main(argv: list[str] | None = None, root: Path = ROOT,
         runner: azure_cli.Runner = azure_cli.real_az) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--azure", action="store_true",
                        help="read this month's spend and the deployment's state again (read-only)")
    parser.add_argument("--out", type=Path, default=None, help="where to write the page")
    args = parser.parse_args(argv)
    if args.azure:
        snap = fetch_azure(runner, load_numbers(root), azure_cli.read_env(root / ".env"),
                           date.today().isoformat())
        (root / AZURE_CACHE).write_text(json.dumps(snap, indent=1), encoding="utf-8")
        print(f"Azure: {'not read (' + snap['error'] + ')' if snap['error'] else 'read'}")
    data = collect(root)
    page = render(data)
    out = args.out or root / OUT
    out.write_text(page, encoding="utf-8")
    tally = _tally(data.reqs)
    print(f"wrote {out.name}: {len(data.phases)} phases, {len(data.reqs)} requirements "
          f"({tally['waiting']} waiting), {len(data.git.prs)} PRs, Jira "
          f"{'read ' + str(data.jira.get('read')) if data.jira else 'missing'}, Azure "
          f"{'read ' + str(data.azure.get('read')) if data.azure else 'missing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
