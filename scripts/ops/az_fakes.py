"""A fake `az` for the scripts/ops tests (not a test file itself).

It answers the calls the scripts make the way the real CLI does (JSON on stdout, an error code
on stderr) and records every call. Its default state is healthy and parked; a test breaks one
thing at a time. Every ID and name here is a placeholder (all-zero GUID, xxxx names).
"""

from __future__ import annotations

import json
from typing import Any

import azure_cli

NUMBERS = azure_cli.load_numbers()
RG = NUMBERS["resource_group"]
SUB = "00000000-0000-0000-0000-000000000000"
ACCOUNT_NAME = "xxxx-foundry"
DEPLOYMENT = "xxxx-haiku"
ORG = "xxxx Org"
ENV = {
    "ANTHROPIC_FOUNDRY_RESOURCE": ACCOUNT_NAME,
    "LLM_HOSTED_MODEL": DEPLOYMENT,
    # Anthropic's attestation fields (placeholders): sent with every Claude deployment.
    "CLAUDE_ORGANIZATION_NAME": ORG,
    "CLAUDE_COUNTRY_CODE": "XX",
    "CLAUDE_INDUSTRY": "technology",
}
GROUP = f"/subscriptions/{SUB}/resourceGroups/{RG}"
ACTION_GROUP = NUMBERS["brake"]["action_group"]
ACTION_GROUP_ID = f"{GROUP}/providers/microsoft.insights/actionGroups/{ACTION_GROUP}"


def budget(name: str, spend: float = 0.0, **change: Any) -> dict[str, Any]:
    spec = NUMBERS["budgets"][name]
    notes = {
        f"Actual_GreaterThanOrEqualTo_{t}_Percent": {
            "enabled": True,
            "operator": "GreaterThanOrEqualTo",
            "threshold": t,
            "thresholdType": "Actual",
            "contactEmails": ["you@example.com"],
            "contactGroups": [ACTION_GROUP_ID] if t == spec["brake_at"] else [],
        }
        for t in spec["alerts"]
    }
    props: dict[str, Any] = {
        "amount": spec["amount"],
        "timeGrain": "Monthly",
        "notifications": notes,
        "currentSpend": {"amount": spend, "unit": NUMBERS["currency"]},
    }
    props.update(change)
    return {"name": name, "properties": props}


def deployment(capacity: int = 1, model: str = "claude-haiku-5-5",
               state: str = "Succeeded") -> dict[str, Any]:
    return {
        "name": DEPLOYMENT,
        "sku": {"name": "GlobalStandard", "capacity": capacity},
        "properties": {"model": {"format": "Anthropic", "name": model, "version": "2"},
                       "provisioningState": state},
    }


class FakeAz:
    """The healthy state by default; tests break one thing at a time."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.assignment: dict[str, Any] | None = {
            "name": NUMBERS["policy"]["assignment"],
            "properties": {"enforcementMode": "Default"},
        }
        self.budgets = [budget("thalam-total"), budget("thalam-model")]
        self.action_group: dict[str, Any] | None = {
            "properties": {"enabled": True, "automationRunbookReceivers": [{"name": "brake"}]}
        }
        self.job_schedules = [{"properties": {
            "runbook": {"name": NUMBERS["brake"]["runbook"]},
            "schedule": {"name": NUMBERS["brake"]["schedule"]},
        }}]
        self.deployments: list[dict[str, Any]] = []
        self.fail_create: str | None = None
        self.puts: list[dict[str, Any]] = []
        self.poll_states: list[str] = ["Creating", "Succeeded"]
        self.resources: list[dict[str, Any]] | None = [
            {"type": t, "resourceGroup": RG, "tags": dict(NUMBERS["tags"]),
             "name": ACCOUNT_NAME if t == "Microsoft.CognitiveServices/accounts" else "xxxx"}
            for t in NUMBERS["sweep"]["allowed_types"]
        ]
        self.tagged_elsewhere: list[dict[str, Any]] = []

    def __call__(self, args: list[str]) -> tuple[int, str, str]:
        self.calls.append(args)
        if args[:2] == ["rest", "--method"]:
            url = args[args.index("--url") + 1]
            if "/Microsoft.CognitiveServices/accounts/" in url and "/deployments/" in url:
                body = json.loads(args[args.index("--body") + 1]) if "--body" in args else None
                return self._deployment_rest(args[2], url, body)
            return self._rest(url)
        if args[:4] == ["cognitiveservices", "account", "deployment", "list"]:
            return self._ok(self.deployments)
        if args[:4] == ["cognitiveservices", "account", "deployment", "delete"]:
            name = args[args.index("--deployment-name") + 1]
            self.deployments = [d for d in self.deployments if d["name"] != name]
            return 0, "", ""
        if args[:3] == ["resource", "list", "--resource-group"]:
            if self.resources is None:
                return 3, "", f"ERROR: (ResourceGroupNotFound) {GROUP}"
            return self._ok(self.resources)
        if args[:3] == ["resource", "list", "--tag"]:
            return self._ok([*(self.resources or []), *self.tagged_elsewhere])
        raise AssertionError(f"unexpected az call: {args}")

    def _rest(self, url: str) -> tuple[int, str, str]:
        assert url.startswith("https://management.azure.com/subscriptions/{subscriptionId}/"), url
        if "/policyAssignments/" in url:
            if self.assignment is None:
                return self._missing("PolicyAssignmentNotFound")
            return self._ok(self.assignment)
        if url.split("?")[0].endswith("/Microsoft.Consumption/budgets"):
            return self._ok({"value": self.budgets})
        if "/actionGroups/" in url:
            if self.action_group is None:
                return self._missing("ResourceNotFound")
            return self._ok(self.action_group)
        if url.split("?")[0].endswith("/jobSchedules"):
            return self._ok({"value": self.job_schedules})
        raise AssertionError(f"unexpected url: {url}")

    def _deployment_rest(self, method: str, url: str,
                         body: dict[str, Any] | None) -> tuple[int, str, str]:
        """PUT creates the deployment (provisioning starts); GET reports the next state."""
        assert url.startswith("https://management.azure.com/subscriptions/{subscriptionId}/"), url
        name = url.split("?")[0].rsplit("/", 1)[1]
        if method == "put":
            assert body is not None
            self.puts.append(body)
            if self.fail_create:
                return 1, "", f"(RequestDisallowedByPolicy) {self.fail_create} {GROUP}"
            made = {**deployment(int(body["sku"]["capacity"])), "name": name}
            made["properties"]["provisioningState"] = "Creating"
            self.deployments.append(made)
            return self._ok(made)
        if method == "get":
            state = self.poll_states.pop(0) if self.poll_states else "Succeeded"
            found = next((d for d in self.deployments if d["name"] == name), None)
            if found is None:
                return self._missing("DeploymentNotFound")
            found["properties"]["provisioningState"] = state
            if state == "Failed":
                found["properties"]["error"] = {"code": "AnthropicOrganizationCreationException"}
            return self._ok(found)
        raise AssertionError(f"unexpected deployment call: {method} {url}")

    @staticmethod
    def _ok(body: object) -> tuple[int, str, str]:
        return 0, json.dumps(body), ""

    @staticmethod
    def _missing(code: str) -> tuple[int, str, str]:
        return 3, "", f"ERROR: ({code}) not found under {GROUP}"

    def made(self, verb: str) -> list[list[str]]:
        prefix = ["cognitiveservices", "account", "deployment", verb]
        return [c for c in self.calls if c[:4] == prefix]
