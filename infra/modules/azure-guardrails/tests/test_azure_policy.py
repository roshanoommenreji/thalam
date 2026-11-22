"""The guardrail policy rules refuse what ADR-0014 says they refuse.

The rules use a small subset of Azure Policy's language. This file evaluates that subset against
resource bodies shaped like the ARM requests, with the parameters taken from guardrails.json (the
values Terraform assigns), so a wrong operator, a wrong alias or a wrong number fails here before it
fails live. The live proof (a capacity-4 deployment refused) is in docs/labs/00-foundations.md.
"""
# covers: SPEC-001-R15

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

MODULE = Path(__file__).resolve().parents[1]
NUMBERS: dict[str, Any] = json.loads((MODULE / "guardrails.json").read_text(encoding="utf-8"))
RULES = {
    p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (MODULE / "policy").glob("*.json")
}

# Where each alias the rules use lives in a resource body (ARM's request shape).
ALIASES: dict[str, tuple[str, ...]] = {
    "type": ("type",),
    "kind": ("kind",),
    "Microsoft.CognitiveServices/accounts/deployments/model.name": ("properties", "model", "name"),
    "Microsoft.CognitiveServices/accounts/deployments/sku.name": ("sku", "name"),
    "Microsoft.CognitiveServices/accounts/deployments/sku.capacity": ("sku", "capacity"),
    "Microsoft.Search/searchServices/sku.name": ("sku", "name"),
}
PARAM = re.compile(r"^\[parameters\('(\w+)'\)\]$")
MISSING = object()

# The parameter values Terraform passes to each rule (infra/modules/azure-guardrails/main.tf).
PARAMS: dict[str, dict[str, Any]] = {
    "deployments": {
        "allowedModels": [NUMBERS["model"]["name"]],
        "allowedSkus": [NUMBERS["model"]["sku"]],
        "maxCapacity": NUMBERS["model"]["capacity_cap"],
    },
    "accounts": {"allowedKinds": NUMBERS["policy"]["allowed_account_kinds"]},
    "search": {"allowedSkus": NUMBERS["policy"]["allowed_search_skus"]},
}


def _field(resource: dict[str, Any], alias: str) -> Any:
    value: Any = resource
    for key in ALIASES[alias]:
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def _value(raw: Any, params: dict[str, Any]) -> Any:
    if isinstance(raw, str) and (m := PARAM.match(raw)):
        return params[m.group(1)]
    return raw


def _lower(value: Any) -> Any:
    return value.lower() if isinstance(value, str) else value


def _holds(cond: dict[str, Any], resource: dict[str, Any], params: dict[str, Any]) -> bool:
    if "allOf" in cond:
        return all(_holds(c, resource, params) for c in cond["allOf"])
    if "anyOf" in cond:
        return any(_holds(c, resource, params) for c in cond["anyOf"])
    if "not" in cond:
        return not _holds(cond["not"], resource, params)
    actual = _field(resource, cond["field"])
    (op,) = (k for k in cond if k != "field")
    want = _value(cond[op], params)
    if op == "exists":  # Azure Policy compares strings without regard to case
        return (actual is not MISSING) == (str(want).lower() == "true")
    if actual is MISSING:  # a missing field: equals/in/greater are false, notEquals/notIn true
        return op in {"notEquals", "notIn"}
    if op == "equals":
        return bool(_lower(actual) == _lower(want))
    if op == "notEquals":
        return bool(_lower(actual) != _lower(want))
    if op in {"in", "notIn"}:
        inside = _lower(actual) in [_lower(w) for w in want]
        return inside if op == "in" else not inside
    if op == "greater":
        return bool(actual > want)
    raise AssertionError(f"operator {op!r} is outside the subset this test evaluates")


def denied(rule: str, resource: dict[str, Any]) -> bool:
    body = RULES[rule]
    assert body["policyRule"]["then"]["effect"] == "deny"
    return _holds(body["policyRule"]["if"], resource, PARAMS[rule])


def deployment(model: str = "claude-haiku-5-5", sku: str = "GlobalStandard",
               capacity: int | None = 1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "Microsoft.CognitiveServices/accounts/deployments",
        "sku": {"name": sku},
        "properties": {"model": {"format": "Anthropic", "name": model, "version": "2"}},
    }
    if capacity is not None:
        body["sku"]["capacity"] = capacity
    return body


def test_the_three_rule_files_exist() -> None:
    assert sorted(RULES) == ["accounts", "deployments", "search"]


@pytest.mark.parametrize("capacity", [1, 2, 3])
def test_the_approved_deployment_is_allowed_up_to_the_cap(capacity: int) -> None:
    assert not denied("deployments", deployment(capacity=capacity))


def test_a_deployment_over_the_cap_is_refused() -> None:
    # The live proof in Lab 00 uses this exact case.
    assert denied("deployments", deployment(capacity=4))


def test_a_deployment_without_a_capacity_is_refused() -> None:
    # Azure would give it the default of 10 units, over the cap.
    assert denied("deployments", deployment(capacity=None))


@pytest.mark.parametrize(
    "model", ["claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2", "gpt-4.1"]
)
def test_any_other_model_is_refused(model: str) -> None:
    assert denied("deployments", deployment(model=model))


@pytest.mark.parametrize(
    "sku", ["DataZoneStandard", "Standard", "ProvisionedManaged", "GlobalBatch"]
)
def test_any_other_deployment_type_is_refused(sku: str) -> None:
    assert denied("deployments", deployment(sku=sku))


def test_the_model_name_is_compared_without_regard_to_case() -> None:
    assert not denied("deployments", deployment(model="Claude-Haiku-5-5"))


def test_the_deployment_rule_ignores_other_resource_types() -> None:
    storage = {"type": "Microsoft.Storage/storageAccounts", "sku": {"name": "x"}}
    assert not denied("deployments", storage)


def test_only_a_foundry_account_is_allowed() -> None:
    account = {"type": "Microsoft.CognitiveServices/accounts"}
    assert not denied("accounts", {**account, "kind": "AIServices"})
    assert denied("accounts", {**account, "kind": "OpenAI"})
    assert denied("accounts", {**account, "kind": "CognitiveServices"})


def test_ai_search_is_free_tier_only() -> None:
    search = {"type": "Microsoft.Search/searchServices"}
    assert not denied("search", {**search, "sku": {"name": "free"}})
    assert denied("search", {**search, "sku": {"name": "basic"}})
    assert denied("search", {**search, "sku": {"name": "standard"}})


@pytest.mark.parametrize("rule", ["accounts", "deployments", "search"])
def test_every_parameter_is_declared_used_and_holds_no_number(rule: str) -> None:
    body = RULES[rule]
    declared = set(body["parameters"])
    text = json.dumps(body["policyRule"])
    used = set(re.findall(r"parameters\('(\w+)'\)", text))
    assert declared == used == set(PARAMS[rule])
    assert body["mode"] == "All"
    # The numbers live in guardrails.json only (SPEC-001-R18): no digits inside the rule itself.
    assert not re.search(r"\d", text.replace("Microsoft.CognitiveServices", "")), text


def test_every_alias_the_rules_use_is_one_this_test_knows() -> None:
    # A new alias must be added to ALIASES (and checked against `az provider show`) on purpose.
    for body in RULES.values():
        for alias in re.findall(r'"field": "([^"]+)"', json.dumps(body["policyRule"])):
            assert alias in ALIASES, alias
