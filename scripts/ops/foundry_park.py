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
import json
import re
import sys
import time
from collections.abc import Callable
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


COUNTRY = re.compile(r"^[A-Z]{2}$")
INDUSTRY = re.compile(r"^[a-z][a-z_ -]*$")
# The API version Microsoft's own Claude sample uses with modelProviderData (Azure-Samples/claude).
DEPLOYMENT_API = "2025-10-01-preview"
POLL_SECONDS, POLL_TIMES = 10, 60  # up to ten minutes
CREATING = {"Creating", "Accepted", "Updating", "Running"}
# A deletion is accepted at once and runs in the background: the brake's deployment stayed
# listed as Deleting for about half a minute in the live test (2026-11-22).
IN_FLIGHT = CREATING | {"Deleting"}


def _state(d: dict[str, Any]) -> str:
    return str(d.get("properties", {}).get("provisioningState", "?"))


def _provider_data(env: dict[str, str]) -> dict[str, str] | None:
    """Anthropic's attestation fields. Azure signs the Anthropic Marketplace offer with them on
    every Claude deployment, so they must describe the real organization (Lab 00 step 3)."""
    org = env.get("CLAUDE_ORGANIZATION_NAME", "").strip()
    country = env.get("CLAUDE_COUNTRY_CODE", "").strip()
    industry = env.get("CLAUDE_INDUSTRY", "").strip()
    problems = []
    if not org or "<" in org:
        problems.append("CLAUDE_ORGANIZATION_NAME (your organization's name)")
    if not COUNTRY.match(country):
        problems.append("CLAUDE_COUNTRY_CODE (two capital letters, such as IN)")
    if not INDUSTRY.match(industry):
        problems.append("CLAUDE_INDUSTRY (lower case, such as technology)")
    if problems:
        print("FAIL  set in .env: " + "; ".join(problems))
        return None
    return {"organizationName": org, "countryCode": country, "industry": industry}


def _describe(d: dict[str, Any]) -> str:
    sku = d.get("sku", {})
    model = d.get("properties", {}).get("model", {})
    return f"{model.get('name', '?')}, {sku.get('name', '?')}, capacity {sku.get('capacity', '?')}"


def up(runner: Runner, numbers: dict[str, Any], account: str, deployment: str,
       provider: dict[str, str], sleep: Callable[[float], None] = time.sleep) -> int:
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
        moving = sorted({_state(d) for d in existing} & IN_FLIGHT)
        if moving:
            print(f"WAIT  a deployment is {', '.join(moving)}; run `make foundry-up` again in a "
                  "minute")
            return 1
        mine = [d for d in existing if d.get("name") == deployment]
        approved = all(d.get("sku", {}).get("capacity") == model["capacity"]
                       and _state(d) == "Succeeded" for d in existing)
        if mine and approved and len(existing) == 1:
            print(f"UP  already ({_describe(mine[0])})")
            return 0
        print("REFUSED  the account holds a deployment that is not the approved, working one; "
              "run `make foundry-down` first")
        return 1
    # `az cognitiveservices account deployment create` cannot send modelProviderData, which
    # Anthropic models require, so the deployment is PUT through Resource Manager directly.
    url = (f"{azure_cli.ARM}{azure_cli.group_path(numbers)}/providers/"
           f"Microsoft.CognitiveServices/accounts/{account}/deployments/{deployment}"
           f"?api-version={DEPLOYMENT_API}")
    body = {
        "sku": {"name": model["sku"], "capacity": model["capacity"]},
        "properties": {
            "model": {"format": model["format"], "name": model["name"],
                      "version": model["version"]},
            "modelProviderData": provider,
        },
    }
    try:
        made = azure_cli.az_json(runner, ["rest", "--method", "put", "--url", url,
                                          "--body", json.dumps(body)]) or {}
        state = str(made.get("properties", {}).get("provisioningState", "Creating"))
        for _ in range(POLL_TIMES):
            if state not in CREATING:
                break
            sleep(POLL_SECONDS)
            made = azure_cli.az_json(runner, ["rest", "--method", "get", "--url", url]) or {}
            state = str(made.get("properties", {}).get("provisioningState", "?"))
    except AzError as err:
        print(f"FAIL  creating the deployment: {err}")
        return 1
    if state != "Succeeded":
        code = made.get("properties", {}).get("error", {}).get("code", "no error code")
        print(f"FAIL  the deployment ended {state} ({code}); run `make foundry-down` to clear it")
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
        state = _state(d)
        print(f"{'up' if state == 'Succeeded' else state.lower()}  {_describe(d)}")
    return 0


def main(argv: list[str] | None = None, runner: Runner = azure_cli.real_az,
         env: dict[str, str] | None = None,
         sleep: Callable[[float], None] = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("command", choices=["up", "down", "status"])
    args = parser.parse_args(argv)
    values = azure_cli.read_env() if env is None else env
    names = _names(values)
    if names is None:
        return 1
    account, deployment = names
    numbers = azure_cli.load_numbers()
    if args.command == "up":
        provider = _provider_data(values)
        if provider is None:
            return 1
        return up(runner, numbers, account, deployment, provider, sleep)
    if args.command == "down":
        return down(runner, numbers, account)
    return status(runner, numbers, account)


if __name__ == "__main__":
    sys.exit(main())
