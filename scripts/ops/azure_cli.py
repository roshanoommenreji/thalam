"""The Azure CLI, wrapped for scripts/ops (ADR-0014): the guardrails check, shared by
`foundry_park.py` and `azure_sweep.py`.

Every call goes through a runner, so tests swap `az` for a fake. Output is parsed and never
printed, because it holds subscription IDs and resource addresses (CLAUDE.md rule 6); a failure is
reduced to Azure's error code. Resource Manager calls go through `az rest` with the literal
`{subscriptionId}` in the URL, which the CLI fills in, so the ID never passes through this code.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
NUMBERS_FILE = ROOT / "infra" / "modules" / "azure-guardrails" / "guardrails.json"
ENV_FILE = ROOT / ".env"
ARM = "https://management.azure.com/subscriptions/{subscriptionId}"
RESOURCE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")
DEPLOYMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

Runner = Callable[[list[str]], tuple[int, str, str]]


class AzError(Exception):
    """An `az` call failed; the message is Azure's error code only."""


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool
    detail: str = ""

    def line(self) -> str:
        tail = f"  ({self.detail})" if self.detail else ""
        return f"{'PASS' if self.ok else 'FAIL'}  {self.name}{tail}"


def load_numbers() -> dict[str, Any]:
    numbers: dict[str, Any] = json.loads(NUMBERS_FILE.read_text(encoding="utf-8"))
    return numbers


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    """KEY=VALUE lines; comments and blanks skipped; quotes stripped. Missing file: empty."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip("\"'")
    return out


def real_az(args: list[str]) -> tuple[int, str, str]:
    exe = shutil.which("az")  # az.cmd on Windows
    if exe is None:
        return 127, "", "(AzureCliNotInstalled) az was not found on PATH"
    done = subprocess.run([exe, *args, "--only-show-errors"], capture_output=True, text=True,
                          check=False)
    return done.returncode, done.stdout, done.stderr


def error_code(code: int, stderr: str) -> str:
    for pattern in (r'"code"\s*:\s*"([A-Za-z]+)"', r"\(([A-Za-z]+)\)"):
        if found := re.search(pattern, stderr):
            return found.group(1)
    return f"az exited {code}"


def az_json(runner: Runner, args: list[str]) -> Any:
    code, out, err = runner(args)
    if code != 0:
        raise AzError(error_code(code, err))
    return json.loads(out) if out.strip() else None


def arm_get(runner: Runner, path: str, api: str) -> Any:
    return az_json(runner, ["rest", "--method", "get", "--url", f"{ARM}{path}?api-version={api}"])


def group_path(numbers: dict[str, Any]) -> str:
    return f"/resourceGroups/{numbers['resource_group']}"


def deployments(runner: Runner, numbers: dict[str, Any], account: str) -> list[dict[str, Any]]:
    found = az_json(runner, ["cognitiveservices", "account", "deployment", "list",
                             "--resource-group", numbers["resource_group"], "--name", account,
                             "-o", "json"])
    return list(found or [])


# ── the guardrails check (SPEC-001-R14, R17) ─────────────────────────────────────────────────


def _policy(runner: Runner, numbers: dict[str, Any]) -> Result:
    name = f"policy: {numbers['policy']['assignment']} is assigned and enforced"
    path = (f"{group_path(numbers)}/providers/Microsoft.Authorization/policyAssignments/"
            f"{numbers['policy']['assignment']}")
    try:
        found = arm_get(runner, path, "2023-04-01") or {}
    except AzError as err:
        return Result(name, False, f"missing: {err}")
    mode = found.get("properties", {}).get("enforcementMode", "Default")
    return Result(name, mode == "Default", f"enforcement {mode}")


def _budget(name: str, spec: dict[str, Any], found: dict[str, Any] | None,
            action_group: str) -> list[Result]:
    title = f"budget {name}: {spec['amount']} {{c}} with alerts at {spec['alerts']} %"
    if found is None:
        return [Result(title, False, "missing")]
    props = found.get("properties", {})
    problems: list[str] = []
    if float(props.get("amount", -1)) != float(spec["amount"]):
        problems.append(f"amount is {props.get('amount')}")
    notes = list(props.get("notifications", {}).values())
    for threshold in spec["alerts"]:
        match = [n for n in notes if float(n.get("threshold", -1)) == float(threshold)
                 and n.get("enabled", True) and n.get("thresholdType", "Actual") == "Actual"]
        if not match:
            problems.append(f"no alert at {threshold} %")
        elif threshold == spec["brake_at"] and not any(
            str(g).lower().endswith(f"/actiongroups/{action_group}".lower())
            for n in match for g in n.get("contactGroups", [])
        ):
            problems.append(f"the {threshold} % alert does not start the brake")
    results = [Result(title, not problems, "; ".join(problems))]
    line = float(spec["amount"]) * float(spec["brake_at"]) / 100
    spent = float(props.get("currentSpend", {}).get("amount", 0))
    results.append(Result(f"budget {name}: below its brake line this month", spent < line,
                          "spend at or past the brake line" if spent >= line else ""))
    return results


def _budgets(runner: Runner, numbers: dict[str, Any]) -> list[Result]:
    path = f"{group_path(numbers)}/providers/Microsoft.Consumption/budgets"
    try:
        found = {b["name"]: b for b in (arm_get(runner, path, "2023-11-01") or {}).get("value", [])}
    except AzError as err:
        return [Result("budgets: readable", False, str(err))]
    out: list[Result] = []
    for name, spec in numbers["budgets"].items():
        for result in _budget(name, spec, found.get(name), numbers["brake"]["action_group"]):
            out.append(Result(result.name.replace("{c}", numbers["currency"]), result.ok,
                              result.detail))
    return out


def _brake(runner: Runner, numbers: dict[str, Any]) -> list[Result]:
    brake = numbers["brake"]
    group = group_path(numbers)
    wired = Result("brake: the action group starts the runbook", False)
    try:
        ag = arm_get(runner, f"{group}/providers/Microsoft.Insights/actionGroups/"
                             f"{brake['action_group']}", "2023-01-01") or {}
        props = ag.get("properties", {})
        ok = bool(props.get("enabled", True) and props.get("automationRunbookReceivers"))
        wired = Result(wired.name, ok, "" if ok else "no runbook receiver")
    except AzError as err:
        wired = Result(wired.name, False, f"missing: {err}")
    nightly = Result("brake: the runbook runs every night", False)
    try:
        path = (f"{group}/providers/Microsoft.Automation/automationAccounts/"
                f"{brake['automation_account']}/jobSchedules")
        links = (arm_get(runner, path, "2023-11-01") or {}).get("value", [])
        ok = any(j.get("properties", {}).get("runbook", {}).get("name") == brake["runbook"]
                 and j.get("properties", {}).get("schedule", {}).get("name") == brake["schedule"]
                 for j in links)
        nightly = Result(nightly.name, ok, "" if ok else "no nightly schedule linked")
    except AzError as err:
        nightly = Result(nightly.name, False, f"missing: {err}")
    return [wired, nightly]


def guardrails(runner: Runner, numbers: dict[str, Any]) -> list[Result]:
    """Everything that must be true before a deployment may exist (ADR-0014)."""
    return [_policy(runner, numbers), *_budgets(runner, numbers), *_brake(runner, numbers)]
