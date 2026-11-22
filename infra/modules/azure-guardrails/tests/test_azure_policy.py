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
MISSING = object()
TOKEN = re.compile(r"\s*(?:(?P<name>[A-Za-z]+)\(|'(?P<text>[^']*)'|(?P<num>-?\d+)|(?P<punct>[,)]))")


class PolicyError(Exception):
    """What Azure reports as InvalidPolicyEvaluation: the rule could not be evaluated."""

# The parameter values Terraform passes to each rule (infra/modules/azure-guardrails/policy.tf).
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


def _call(name: str, args: list[Any], resource: dict[str, Any], params: dict[str, Any]) -> Any:
    """The template functions the rules use, as Azure Policy evaluates them."""
    if name == "parameters":
        return params[args[0]]
    if name == "field":
        found = _field(resource, args[0])
        return None if found is MISSING else found
    if name == "coalesce":
        return next((a for a in args if a is not None), None)
    if name == "string":
        return str(args[0]).lower() if isinstance(args[0], bool) else str(args[0])
    if name == "int":
        try:
            return int(args[0])
        except (TypeError, ValueError) as err:
            raise PolicyError(f"int() of {args[0]!r}") from err
    raise AssertionError(f"function {name!r} is outside the subset this test evaluates")


def _expression(text: str, resource: dict[str, Any], params: dict[str, Any]) -> Any:
    """Evaluate a policy expression such as [int(string(coalesce(field('x'), 0)))]."""
    tokens = [m.groupdict() for m in TOKEN.finditer(text[1:-1])]
    position = 0

    def parse() -> Any:
        nonlocal position
        token = tokens[position]
        position += 1
        if token["text"] is not None:
            return token["text"]
        if token["num"] is not None:
            return int(token["num"])
        assert token["name"], f"cannot parse {text!r}"
        args: list[Any] = []
        while tokens[position]["punct"] != ")":
            args.append(parse())
            if tokens[position]["punct"] == ",":
                position += 1
        position += 1
        return _call(token["name"], args, resource, params)

    return parse()


def _value(raw: Any, resource: dict[str, Any], params: dict[str, Any]) -> Any:
    if isinstance(raw, str) and raw.startswith("[") and raw.endswith("]"):
        return _expression(raw, resource, params)
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
    if "field" in cond:
        actual = _field(resource, cond["field"])
    else:
        actual = _value(cond["value"], resource, params)
        actual = MISSING if actual is None else actual
    (op,) = (k for k in cond if k not in {"field", "value"})
    want = _value(cond[op], resource, params)
    if op == "exists":  # Azure Policy compares strings without regard to case
        return (actual is not MISSING) == (str(want).lower() == "true")
    if op in {"greater", "less", "greaterOrEquals", "lessOrEquals"}:
        # Azure refuses to compare different types (InvalidPolicyEvaluation, found live).
        if actual is MISSING or type(actual) is not type(want):
            raise PolicyError(f"{op} on {actual!r} and {want!r}")
        return bool(actual > want) if op == "greater" else bool(actual >= want)
    if actual is MISSING:  # a missing field: equals/in are false, notEquals/notIn true
        return op in {"notEquals", "notIn"}
    if op == "equals":
        return bool(_lower(actual) == _lower(want))
    if op == "notEquals":
        return bool(_lower(actual) != _lower(want))
    if op in {"in", "notIn"}:
        inside = _lower(actual) in [_lower(w) for w in want]
        return inside if op == "in" else not inside
    raise AssertionError(f"operator {op!r} is outside the subset this test evaluates")


def denied(rule: str, resource: dict[str, Any]) -> bool:
    body = RULES[rule]
    assert body["policyRule"]["then"]["effect"] == "deny"
    return _holds(body["policyRule"]["if"], resource, PARAMS[rule])


def deployment(model: str = "claude-haiku-5-5", sku: str = "GlobalStandard",
               capacity: int | str | None = 1) -> dict[str, Any]:
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


@pytest.mark.parametrize(("capacity", "refused"), [("1", False), ("3", False), ("4", True)])
def test_a_capacity_sent_as_text_is_compared_as_a_number(capacity: str, refused: bool) -> None:
    # Found by the live proof (2026-11-22): the request carried the capacity so that a plain
    # `greater` on the field could not be evaluated (InvalidPolicyEvaluation), which refused
    # even the approved deployment. The rule converts it to a number first.
    assert denied("deployments", deployment(capacity=capacity)) is refused


def test_a_plain_greater_on_text_cannot_be_evaluated() -> None:
    # The trap itself, so the evaluator above is known to model it.
    rule = {"field": "Microsoft.CognitiveServices/accounts/deployments/sku.capacity",
            "greater": "[parameters('maxCapacity')]"}
    with pytest.raises(PolicyError):
        _holds(rule, deployment(capacity="4"), PARAMS["deployments"])


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
    # The numbers live in guardrails.json only (SPEC-001-R18): no digits inside the rule itself,
    # apart from coalesce's fallback of 0 for a missing capacity (refused by its own clause).
    stripped = text.replace("Microsoft.CognitiveServices", "").replace("), 0)", "))")
    assert not re.search(r"\d", stripped), text


def test_every_alias_the_rules_use_is_one_this_test_knows() -> None:
    # A new alias must be added to ALIASES (and checked against `az provider show`) on purpose.
    for body in RULES.values():
        text = json.dumps(body["policyRule"])
        aliases = re.findall(r'"field": "([^"]+)"', text) + re.findall(r"field\('([^']+)'\)", text)
        assert aliases
        for alias in aliases:
            assert alias in ALIASES, alias
