"""scripts/tracking/dashboard.py: the page reflects the repository and keeps no status of its own.

It reads ROADMAP.md, the specs and labs, and two saved copies (Jira, Azure). These tests pin the
parsing, the escaping of everything it quotes, and that the Azure copy keeps no name, address or
ID (CLAUDE.md rule 6).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import dashboard
import diagrams
import pytest

GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
SUB = "00000000-0000-0000-0000-00000000abcd"
ACCOUNT = "xxxx-foundry"
DEPLOYMENT = "xxxx-haiku"

ROADMAP = """# Roadmap

Legend: `[ ]` not started

## Phase 0 — Foundations · `[~]`

- [x] Charter and roadmap (2026-11-18)
- [x] **Decisions closed:**
  - D-1 Cost: plan $50,
    since 2026-11-22 in rupees
  - D-2 Name
- [ ] Sign up: Jira, ServiceNow,
      and Slack
- [ ] <script>alert(1)</script> stays text

**Exit gate:** sandboxes reachable; the model
deployment parked.

## Phase 1 — The release graph, local · `[ ]`

- [ ] Data model

## Phase 7 — Kubernetes and Azure · `[ ]`

Kaval's path, moved to Azure:

1. Extend the budgets. Inside
   the ceiling nothing runs all month.
2. k3d, then k3s.
"""

LAB = """# Lab

## 1. Planning space — SPEC-001-R9

**Evidence (2026-11-18):** space THL exists.

## 5. Foundry — SPEC-001-R13 to R16

**Evidence SPEC-001-R15 (fence, 2026-11-22):** refused.

**Evidence SPEC-001-R16 (meter):** _not run yet_

**Evidence R13:** in section 8.

## 8. Sandbox check — SPEC-001-R10 to R13

**Evidence (2026-11-22):** seven PASS lines.
"""


def _roadmap(tmp_path: Path) -> list[dashboard.Phase]:
    path = tmp_path / "ROADMAP.md"
    path.write_text(ROADMAP, encoding="utf-8")
    return dashboard.read_roadmap(path)


def test_the_roadmap_gives_phases_tasks_and_the_exit_gate(tmp_path: Path) -> None:
    phases = _roadmap(tmp_path)
    assert [p.num for p in phases] == [0, 1, 7]
    zero = phases[0]
    assert (zero.state, zero.done, zero.total) == ("in progress", 2, 4)
    assert zero.tasks[1].subs == ["D-1 Cost: plan $50, since 2026-11-22 in rupees", "D-2 Name"]
    assert zero.tasks[2].text == "Sign up: Jira, ServiceNow, and Slack"
    assert zero.gate == "sandboxes reachable; the model deployment parked."
    seven = phases[2]
    assert seven.tasks == []
    assert seven.notes == [
        "Kaval's path, moved to Azure:",
        "1. Extend the budgets. Inside the ceiling nothing runs all month.",
        "2. k3d, then k3s.",
    ]


def test_the_current_phase_is_the_one_in_progress(tmp_path: Path) -> None:
    phases = _roadmap(tmp_path)
    assert dashboard.current_phase(phases) is phases[0]
    phases[0].marker = "x"
    assert dashboard.current_phase(phases) is phases[1]


def test_lab_evidence_belongs_to_the_ids_it_names_or_its_section_names() -> None:
    found = dashboard.read_evidence(LAB)
    assert found["SPEC-001-R9"] == dashboard.Evidence(
        "recorded", "2026-11-18", "1. Planning space — SPEC-001-R9")
    assert found["SPEC-001-R15"].state == "recorded"
    assert found["SPEC-001-R16"].state == "pending"  # `_not run yet_` is not a proof
    # R13 says "see section 8"; section 8's undated-ID line covers R10 to R13 and has the date.
    assert found["SPEC-001-R13"] == dashboard.Evidence(
        "recorded", "2026-11-22", "8. Sandbox check — SPEC-001-R10 to R13")
    assert {found[f"SPEC-001-R{n}"].state for n in (10, 11, 12)} == {"recorded"}
    assert "SPEC-001-R14" not in found  # its section names it, but no evidence line is its own


def test_quoted_text_is_escaped_and_only_safe_links_are_made() -> None:
    md = dashboard.Md("https://github.com/o/r", "main")
    out = md("[ADR-0012](docs/adr/0012-x.md), `make up`, **bold** <script>alert(1)</script>")
    assert '<a href="https://github.com/o/r/blob/main/docs/adr/0012-x.md">ADR-0012</a>' in out
    assert "<code>make up</code>" in out and "<strong>bold</strong>" in out
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert md("[x](javascript:void)") == "x"
    assert md("[up](../adr/0013.md)", "docs/specs").endswith(
        'href="https://github.com/o/r/blob/main/docs/adr/0013.md">up</a>')
    assert md("[out](../../../etc/passwd)", "docs") == "out"


def _fake_az(fail: bool = False) -> Callable[[list[str]], tuple[int, str, str]]:
    group = f"/subscriptions/{SUB}/resourceGroups/rg-thalam"

    def run(args: list[str]) -> tuple[int, str, str]:
        if fail:
            return 1, "", f"ERROR: (AuthorizationFailed) no access to {group}"
        if args[:2] == ["rest", "--method"]:
            budget = {"id": f"{group}/providers/Microsoft.Consumption/budgets/thalam-total",
                      "name": "thalam-total",
                      "properties": {"currentSpend": {"amount": 12.5, "unit": "INR"}}}
            other = {"id": f"{group}/x", "name": "someone-elses",
                     "properties": {"currentSpend": {"amount": 99.0, "unit": "INR"}}}
            return 0, json.dumps({"value": [budget, other]}), ""
        if args[:3] == ["resource", "list", "--resource-group"]:
            listed = [{"type": "Microsoft.CognitiveServices/accounts", "name": ACCOUNT,
                       "id": f"{group}/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT}"}]
            return 0, json.dumps(listed), ""
        if args[:4] == ["cognitiveservices", "account", "deployment", "list"]:
            dep = {"id": f"{group}/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT}"
                         f"/deployments/{DEPLOYMENT}",
                   "name": DEPLOYMENT, "sku": {"name": "GlobalStandard", "capacity": 1},
                   "properties": {"provisioningState": "Succeeded",
                                  "model": {"name": "claude-haiku-5-5"}}}
            return 0, json.dumps([dep]), ""
        raise AssertionError(f"unexpected az call: {args}")

    return run


def test_the_azure_copy_keeps_amounts_and_states_but_no_name_or_id() -> None:
    numbers = dashboard.load_numbers(dashboard.ROOT)
    snap = dashboard.fetch_azure(_fake_az(), numbers,
                                 {"ANTHROPIC_FOUNDRY_RESOURCE": ACCOUNT}, "2026-11-22")
    assert snap["budgets"] == {"thalam-total": {"spend": 12.5, "unit": "INR"}}
    assert snap["deployments"] == [
        {"state": "Succeeded", "capacity": 1, "model": "claude-haiku-5-5"}]
    assert snap["types"] == {"Microsoft.CognitiveServices/accounts": 1}
    assert snap["checks"] and all({"name", "ok", "detail"} == set(c) for c in snap["checks"])
    saved = json.dumps(snap)
    assert not GUID.search(saved)
    for secret in (ACCOUNT, DEPLOYMENT, "subscriptions", "someone-elses"):
        assert secret not in saved


def test_an_azure_failure_is_saved_as_its_code_only() -> None:
    snap = dashboard.fetch_azure(_fake_az(fail=True), dashboard.load_numbers(dashboard.ROOT),
                                 {"ANTHROPIC_FOUNDRY_RESOURCE": ACCOUNT}, "2026-11-22")
    assert snap["error"] == "AuthorizationFailed"
    assert not GUID.search(json.dumps(snap))


def test_the_real_repository_renders_every_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No saved copies: the page says so and everything else is still built from the repo.
    monkeypatch.setattr(dashboard, "read_jira", lambda root: None)
    monkeypatch.setattr(dashboard, "read_azure", lambda root: None)
    out = tmp_path / "dashboard.html"
    assert dashboard.main(["--out", str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    for view, _ in dashboard.VIEWS:
        assert f'id="view-{view}"' in page
    assert "No saved copy of Jira" in page and "Azure has not been read" in page
    for card in ("architecture-agent", "azure-runbook", "devops-ruleset", "flow-brake"):
        assert f'id="{card}"' in page  # what the diagrams' links point at
    assert not GUID.search(page)


def test_the_cost_view_quotes_guardrails_json_and_nothing_else() -> None:
    data = dashboard.collect(dashboard.ROOT)
    page = dashboard.render_cost(data, dashboard.Md("https://github.com/o/r", "main"))
    total = data.numbers["budgets"]["thalam-total"]
    brake = total["amount"] * total["brake_at"] / 100
    assert dashboard.rupees(data.numbers["ceiling"]) in page
    assert dashboard.rupees(brake) in page
    assert f"cap of {data.numbers['model']['capacity_cap']}" in page


ARCH = dashboard.read_architecture(dashboard.ROOT, dashboard.load_numbers(dashboard.ROOT))


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    return []


def test_the_architecture_file_holds_together() -> None:
    # A diagram must not point at a part that does not exist, and every part says what it is
    # and what flows in and out (the cards are built from these fields).
    assert not GUID.search((dashboard.ROOT / dashboard.ARCH).read_text(encoding="utf-8"))
    for section in ("architecture", "azure", "devops", "infra"):
        nodes = ARCH[section]["node"]
        ids = [n["id"] for n in nodes]
        assert len(ids) == len(set(ids)), section
        for n in nodes:
            assert n["definition"] and n["inputs"] and n["outputs"], (section, n["id"])
        for e in ARCH[section]["edge"]:
            assert e["from"] in ids and e["to"] in ids, (section, e)
            assert e.get("kind", "data") in diagrams.EDGE_KINDS, (section, e)
    for flow in ARCH["flow"]:
        lanes = {lane for lane, _ in flow["lanes"]}
        for step in flow["steps"]:
            assert step["from"] in lanes and step["to"] in lanes, (flow["id"], step)
            assert step.get("kind", "call") in diagrams.STEP_KINDS
            assert step["note"], (flow["id"], step["label"])
    assert {g["term"] for g in ARCH["glossary"]} >= {"Proposal", "Executor", "Brake line"}


def test_every_placeholder_is_filled_from_guardrails_json() -> None:
    assert [s for s in _strings(ARCH) if dashboard.PLACEHOLDER.search(s)] == []
    numbers = dashboard.load_numbers(dashboard.ROOT)
    total = numbers["budgets"]["thalam-total"]
    brake = dashboard.rupees(total["amount"] * total["brake_at"] / 100)
    assert any(brake in s for s in _strings(ARCH["flow"]))  # the brake line, from the json


def test_a_graph_draws_every_node_and_edge_with_its_text_escaped() -> None:
    d = diagrams
    svg = d.graph([d.Node("a", "<A>", 0, 0), d.Node("b", "B", 1, 0, href="x", badge="2")],
                  [d.Edge("a", "b", "calls & returns", "write")], uid="t", aria="a to b")
    assert svg.count("<rect") == 2 and 'marker-end="url(#t-write)"' in svg
    assert "&lt;A&gt;" in svg and "calls &amp; returns" in svg and 'href="#x"' in svg
    assert 'id="t-data"' in svg  # arrowheads are this diagram's own


def test_a_sequence_numbers_its_steps() -> None:
    d = diagrams
    svg = d.sequence([("a", "A"), ("b", "B")],
                     [d.Step("a", "b", "ask"), d.Step("b", "a", "answer", "return"),
                      d.Step("b", "b", "think", "self")], uid="s", aria="a asks b")
    assert "1 · ask" in svg and "2 · answer" in svg and "3 · think" in svg
    assert "url(#s-return)" in svg
