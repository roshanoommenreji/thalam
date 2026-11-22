"""The cost numbers say the same thing everywhere, and the agent cannot remove the guardrails.

Kaval's test_budget_wiring.py, for Thalam (ADR-0014). The numbers live once, in
infra/modules/azure-guardrails/guardrails.json: Terraform and scripts/ops read that file, and this
test checks that the documents quote it and that no code types a number again. Changing a number
means changing the file and every document in one commit, or this test fails.
"""
# covers: SPEC-001-R18, SPEC-001-R19

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "infra" / "modules" / "azure-guardrails"
N: dict[str, Any] = json.loads((MODULE / "guardrails.json").read_text(encoding="utf-8"))

DOCS = {
    "ADR-0013": ROOT / "docs" / "adr" / "0013-cost-ceiling-1500-inr.md",
    "ADR-0014": ROOT / "docs" / "adr" / "0014-azure-cost-guardrails.md",
    "CLAUDE.md": ROOT / "CLAUDE.md",
    "docs/cost": ROOT / "docs" / "cost" / "README.md",
}
CODE = [*MODULE.glob("*.tf"), *(ROOT / "scripts" / "ops").glob("*.py")]
CODE = [p for p in CODE if not p.name.startswith("test_") and p.name != "az_fakes.py"]


def _rupees(amount: float) -> str:
    return f"₹{round(amount):,}"


def _text(doc: str) -> str:
    # Markdown emphasis and line breaks must not hide a number from the test.
    return re.sub(r"\s+", " ", DOCS[doc].read_text(encoding="utf-8").replace("**", ""))


def _alerts(thresholds: list[int]) -> str:
    """70 / 85 / 95 %, or 70, 85 and 95 %: the same three numbers, in order."""
    return r"\D{1,8}".join(str(t) for t in thresholds) + r" ?%"


def _model_title(name: str) -> str:
    family, *version = name.removeprefix("claude-").split("-")
    return f"Claude {family.capitalize()} {'.'.join(version)}"


TOTAL, MODEL = N["budgets"]["thalam-total"], N["budgets"]["thalam-model"]
BRAKE_LINE = TOTAL["amount"] * TOTAL["brake_at"] / 100
R = N["runaway"]
PER_UNIT_DAY = (R["tokens_per_minute_per_unit"] * 60 * 24
                * (R["usd_per_million_input"] + R["usd_per_million_output"]) / 1e6
                * R["inr_per_usd"])
CAP = N["model"]["capacity_cap"]

# What each document must say. Every entry is derived from guardrails.json.
QUOTES: dict[str, list[str]] = {
    "ADR-0013": [
        re.escape(_rupees(N["ceiling"])), re.escape(_rupees(BRAKE_LINE)),
        re.escape(_rupees(MODEL["amount"])), _alerts(TOTAL["alerts"]), _alerts(MODEL["alerts"]),
    ],
    "ADR-0014": [
        re.escape(_rupees(BRAKE_LINE)), re.escape(_rupees(MODEL["amount"])),
        re.escape(_model_title(N["model"]["name"])), rf"capacity {N['model']['capacity']}\b",
        rf"\bcap of {CAP}\b", re.escape(_rupees(PER_UNIT_DAY)),
        re.escape(_rupees(round(PER_UNIT_DAY) * CAP)),
        re.escape(_rupees(round(PER_UNIT_DAY) * CAP * R["lag_days"])),
        re.escape(_rupees(N["ceiling"] - N["plan"])),
        re.escape(f"{N['brake']['nightly_at']} IST"),
    ],
    "CLAUDE.md": [
        re.escape(_rupees(N["ceiling"])), re.escape(_rupees(N["plan"])),
        re.escape(_rupees(BRAKE_LINE)), re.escape(_rupees(MODEL["amount"])),
        _alerts(TOTAL["alerts"]), _alerts(MODEL["alerts"]),
        rf"capacity {N['model']['capacity']}\b", rf"\bcap of {CAP}\b",
    ],
    "docs/cost": [
        re.escape(_rupees(N["ceiling"])), re.escape(_rupees(N["plan"])),
        re.escape(_rupees(BRAKE_LINE)), re.escape(_rupees(MODEL["amount"])),
        _alerts(TOTAL["alerts"]), _alerts(MODEL["alerts"]),
        re.escape(_model_title(N["model"]["name"])),
        rf"capacity {N['model']['capacity']}\b", rf"\bcap of {CAP}\b",
        re.escape(_rupees(round(PER_UNIT_DAY) * CAP)),
    ],
}


@pytest.mark.parametrize("doc", sorted(QUOTES))
def test_each_document_quotes_the_numbers(doc: str) -> None:
    text = _text(doc)
    missing = [q for q in QUOTES[doc] if not re.search(q, text, re.IGNORECASE)]
    assert not missing, f"{doc} does not say: {missing}"


def test_the_lines_are_in_order() -> None:
    assert N["plan"] < BRAKE_LINE < N["ceiling"] == TOTAL["amount"]
    assert MODEL["amount"] < N["ceiling"]
    for budget in (TOTAL, MODEL):
        assert budget["alerts"] == sorted(budget["alerts"])
        assert budget["brake_at"] in budget["alerts"]
    assert 1 <= N["model"]["capacity"] <= CAP


def test_three_days_at_the_cap_fit_between_the_plan_and_the_ceiling() -> None:
    # ADR-0014's table: about ₹82 a unit a day at worst; budgets can lag three days.
    assert round(PER_UNIT_DAY) == 82
    assert round(PER_UNIT_DAY) * CAP * R["lag_days"] <= N["ceiling"] - N["plan"]
    assert PER_UNIT_DAY * CAP * R["lag_days"] <= N["ceiling"] - N["plan"]


def test_terraform_and_the_scripts_read_the_one_file() -> None:
    main_tf = (MODULE / "main.tf").read_text(encoding="utf-8")
    assert 'jsondecode(file("${path.module}/guardrails.json"))' in main_tf
    azure_cli = (ROOT / "scripts" / "ops" / "azure_cli.py").read_text(encoding="utf-8")
    assert '"infra" / "modules" / "azure-guardrails" / "guardrails.json"' in azure_cli


@pytest.mark.parametrize("path", CODE, ids=lambda p: p.name)
def test_no_code_types_a_number_or_the_model_again(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    amounts = {N["ceiling"], N["plan"], round(BRAKE_LINE), MODEL["amount"]}
    for amount in amounts:
        assert not re.search(rf"\b{amount}\b|\b{amount:,}\b", text), (path.name, amount)
    for word in (N["model"]["name"], N["model"]["sku"], N["region"]):
        assert word not in text, (path.name, word)
    assert not re.search(r"(capacity|capacity_cap)\s*=\s*\d", text), path.name


def test_the_policy_assignment_gets_its_parameters_from_the_file() -> None:
    policy_tf = (MODULE / "policy.tf").read_text(encoding="utf-8")
    for ref in ("local.n.model.name", "local.n.model.sku", "local.n.model.capacity_cap",
                "local.n.policy.allowed_locations", "local.n.policy.not_allowed_types",
                "local.n.policy.allowed_account_kinds", "local.n.policy.allowed_search_skus"):
        assert ref in policy_tf, ref


def test_each_brake_line_alert_starts_the_brake() -> None:
    budgets_tf = (MODULE / "budgets.tf").read_text(encoding="utf-8")
    brake = "notification.value == each.value.brake_at ? [azurerm_monitor_action_group.brake.id]"
    assert brake in budgets_tf
    assert "for_each = local.n.budgets" in budgets_tf


# ── SPEC-001-R19: Claude Code cannot take the guardrails down ────────────────────────────────

DENIED = [
    "Bash(az policy assignment delete:*)",
    "Bash(az policy exemption create:*)",
    "Bash(az consumption budget delete:*)",
    "Bash(az monitor action-group delete:*)",
    "Bash(az rest --method delete:*)",
    "Bash(az rest --method DELETE:*)",
    "Bash(terraform destroy:*)",
    "Bash(terraform -chdir=infra/envs/azure destroy:*)",
    "Bash(az cognitiveservices account keys list:*)",
]


def _permissions() -> dict[str, list[str]]:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    perms: dict[str, list[str]] = settings["permissions"]
    return perms


@pytest.mark.parametrize("rule", DENIED)
def test_the_agent_is_denied(rule: str) -> None:
    assert rule in _permissions()["deny"]


def test_nothing_denied_is_also_allowed_or_asked() -> None:
    perms = _permissions()
    for rule in perms["deny"]:
        assert rule not in perms.get("allow", []) and rule not in perms.get("ask", []), rule
