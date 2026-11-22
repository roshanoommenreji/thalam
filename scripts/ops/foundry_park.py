"""Park and unpark Thalam's Claude deployment (ADR-0014, SPEC-001-R14).

    make foundry-up       # create it, only if every guardrail holds
    make foundry-down     # delete every deployment on the account (always allowed)
    make foundry-status   # up or parked

A Global Standard deployment bills per token, so deleting it costs nothing and creating it again
takes about a minute. The brake runbook does the same as `down`, by itself, at a budget's brake
line and every night at 02:00 IST.

Reads the account and deployment names from .env (ANTHROPIC_FOUNDRY_RESOURCE, LLM_HOSTED_MODEL) and
the model and capacity from guardrails.json. Prints no resource name, address or ID.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import azure_cli
from azure_cli import AzError, Runner


def _names(env: dict[str, str]) -> tuple[str, str] | None:
    account = env.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
    deployment = env.get("LLM_HOSTED_MODEL", "")
    if not azure_cli.RESOURCE_NAME.match(account):
        print("FAIL  ANTHROPIC_FOUNDRY_RESOURCE in .env must be the resource name only, not a URL")
        return None
    if not azure_cli.DEPLOYMENT_NAME.match(deployment):
        print("FAIL  LLM_HOSTED_MODEL in .env must be the deployment's name")
        return None
    return account, deployment


def _describe(d: dict[str, Any]) -> str:
    sku = d.get("sku", {})
    model = d.get("properties", {}).get("model", {})
    return f"{model.get('name', '?')}, {sku.get('name', '?')}, capacity {sku.get('capacity', '?')}"


def up(runner: Runner, numbers: dict[str, Any], account: str, deployment: str) -> int:
    results = azure_cli.guardrails(runner, numbers)
    for result in results:
        print(result.line())
    failed = [r for r in results if not r.ok]
    if failed:
        reasons = "; ".join(r.name for r in failed)
        print(f"REFUSED  the deployment stays parked until every guardrail holds: {reasons}")
        return 1
    model = numbers["model"]
    existing = azure_cli.deployments(runner, numbers, account)
    if existing:
        mine = [d for d in existing if d.get("name") == deployment]
        approved = all(d.get("sku", {}).get("capacity") == model["capacity"] for d in existing)
        if mine and approved and len(existing) == 1:
            print(f"UP  already ({_describe(mine[0])})")
            return 0
        print("REFUSED  the account holds a deployment that is not the approved one; run "
              "`make foundry-down` first")
        return 1
    try:
        made = azure_cli.az_json(runner, [
            "cognitiveservices", "account", "deployment", "create",
            "--resource-group", numbers["resource_group"],
            "--name", account,
            "--deployment-name", deployment,
            "--model-name", model["name"],
            "--model-version", model["version"],
            "--model-format", model["format"],
            "--sku-name", model["sku"],
            "--sku-capacity", str(model["capacity"]),
            "-o", "json",
        ]) or {}
    except AzError as err:
        print(f"FAIL  creating the deployment: {err}")
        return 1
    print(f"UP  {_describe(made)}. Park it with `make foundry-down` when you are done.")
    return 0


def down(runner: Runner, numbers: dict[str, Any], account: str) -> int:
    try:
        existing = azure_cli.deployments(runner, numbers, account)
    except AzError as err:
        print(f"FAIL  listing the deployments: {err}")
        return 1
    failed = 0
    for d in existing:
        try:
            azure_cli.az_json(runner, [
                "cognitiveservices", "account", "deployment", "delete",
                "--resource-group", numbers["resource_group"], "--name", account,
                "--deployment-name", str(d["name"]),
            ])
        except AzError as err:
            print(f"FAIL  deleting a deployment: {err}")
            failed += 1
    if failed:
        return 1
    print(f"PARKED  {'deleted ' + str(len(existing)) if existing else 'already'}"
          f"{' deployment(s)' if existing else ''}")
    return 0


def status(runner: Runner, numbers: dict[str, Any], account: str) -> int:
    try:
        existing = azure_cli.deployments(runner, numbers, account)
    except AzError as err:
        print(f"FAIL  listing the deployments: {err}")
        return 1
    if not existing:
        print("parked  (no deployment)")
    for d in existing:
        print(f"up  {_describe(d)}")
    return 0


def main(argv: list[str] | None = None, runner: Runner = azure_cli.real_az,
         env: dict[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("command", choices=["up", "down", "status"])
    args = parser.parse_args(argv)
    names = _names(azure_cli.read_env() if env is None else env)
    if names is None:
        return 1
    account, deployment = names
    numbers = azure_cli.load_numbers()
    if args.command == "up":
        return up(runner, numbers, account, deployment)
    if args.command == "down":
        return down(runner, numbers, account)
    return status(runner, numbers, account)


if __name__ == "__main__":
    sys.exit(main())
