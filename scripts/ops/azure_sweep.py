"""The Azure sweep (ADR-0014, SPEC-001-R17): read-only, the exit gate after every session.

    make azure-sweep              # expects the deployment parked
    make azure-sweep ARGS=--expect-up

It fails when:
  * a model deployment exists while it should be parked (or, with --expect-up, one that is not the
    approved model, type and capacity);
  * a resource in Thalam's group has a type not on guardrails.json's list;
  * a resource tagged project=thalam sits outside the group;
  * the policy assignment, a budget or the brake is missing, or a budget is past its brake line.

It only reads (az ... list / show / rest --method get) and prints types and counts, never a name,
address or ID. It needs no .env: it finds the Foundry accounts in the group itself.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import azure_cli
from azure_cli import AzError, Result, Runner

ACCOUNT_TYPE = "microsoft.cognitiveservices/accounts"


def _approved(d: dict[str, Any], model: dict[str, Any]) -> bool:
    sku = d.get("sku", {})
    name = str(d.get("properties", {}).get("model", {}).get("name", "")).lower()
    capacity = sku.get("capacity")
    return (name == model["name"].lower() and sku.get("name") == model["sku"]
            and isinstance(capacity, int) and capacity <= model["capacity_cap"])


def _resources(runner: Runner, numbers: dict[str, Any]) -> tuple[list[Result], list[str]]:
    """Results for the group's contents, plus the names of its Foundry accounts (not printed)."""
    group = numbers["resource_group"]
    try:
        found = azure_cli.az_json(runner, ["resource", "list", "--resource-group", group,
                                           "-o", "json"]) or []
    except AzError as err:
        return [Result("group: Thalam's resource group exists", False, str(err))], []
    allowed = {t.lower() for t in numbers["sweep"]["allowed_types"]}
    types = {str(r.get("type")) for r in found}
    strange = sorted(t for t in types if t.lower() not in allowed)
    results = [Result(f"group: {len(found)} resources, every type on the list", not strange,
                      "not on the list: " + ", ".join(strange) if strange else "")]
    accounts = [str(r["name"]) for r in found if str(r.get("type")).lower() == ACCOUNT_TYPE]
    return results, accounts


def _outside(runner: Runner, numbers: dict[str, Any]) -> Result:
    key, value = next(iter(numbers["tags"].items()))
    name = f"tags: nothing tagged {key}={value} outside the group"
    try:
        tagged = azure_cli.az_json(runner, ["resource", "list", "--tag", f"{key}={value}",
                                            "-o", "json"]) or []
    except AzError as err:
        return Result(name, False, str(err))
    group = numbers["resource_group"].lower()
    stray = sorted({str(r.get("type")) for r in tagged
                    if str(r.get("resourceGroup", "")).lower() != group})
    return Result(name, not stray, "outside the group: " + ", ".join(stray) if stray else "")


def _deployments(runner: Runner, numbers: dict[str, Any], accounts: list[str],
                 expect_up: bool) -> Result:
    model = numbers["model"]
    found: list[dict[str, Any]] = []
    try:
        for account in accounts:
            found += azure_cli.deployments(runner, numbers, account)
    except AzError as err:
        return Result("deployments: readable", False, str(err))
    if not expect_up:
        return Result("deployments: parked (none exist)", not found,
                      f"{len(found)} up: run `make foundry-down`" if found else "")
    bad = [d for d in found if not _approved(d, model)]
    name = f"deployments: only the approved one, at capacity {model['capacity_cap']} or less"
    return Result(name, bool(found) and not bad and len(found) == 1,
                  f"{len(found)} found, {len(bad)} not approved" if bad or len(found) != 1 else "")


def sweep(runner: Runner, numbers: dict[str, Any], expect_up: bool) -> list[Result]:
    group_results, accounts = _resources(runner, numbers)
    return [
        *group_results,
        _outside(runner, numbers),
        _deployments(runner, numbers, accounts, expect_up),
        *azure_cli.guardrails(runner, numbers),
    ]


def main(argv: list[str] | None = None, runner: Runner = azure_cli.real_az) -> int:
    parser = argparse.ArgumentParser(description="Read-only Azure sweep (SPEC-001-R17).")
    parser.add_argument("--expect-up", action="store_true",
                        help="one approved deployment is expected (during a working session)")
    args = parser.parse_args(argv)
    results = sweep(runner, azure_cli.load_numbers(), args.expect_up)
    for result in results:
        print(result.line())
    failed = [r for r in results if not r.ok]
    print(f"{'CLEAN' if not failed else 'NOT CLEAN'}  {len(results) - len(failed)} of "
          f"{len(results)} checks pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
