"""Thalam's brake: delete every model deployment on Thalam's Foundry account (ADR-0014).

It runs in Azure Automation on the Python 3.10 runtime, with the standard library only. Two things
start it: the action group `thalam-brake`, when a budget reaches its brake line, and a schedule
every night at 02:00 IST. Deleting a Global Standard deployment loses nothing (it bills per
token), and `make foundry-up` puts it back.

The account's resource ID is not in git: Terraform writes it over the placeholder in ACCOUNT_ID
when it uploads this file. The runbook's managed identity can read the account and read and
delete its deployments, nothing more (brake.tf).

Pass --dry-run to list what would be deleted without deleting it.
"""
# covers: SPEC-001-R16

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

ACCOUNT_ID = "__ACCOUNT_ID__"
PLACEHOLDER = "__" + "ACCOUNT_ID" + "__"  # built in pieces, so Terraform's replace() skips it
ARM = "https://management.azure.com"
API = "2024-10-01"
DELETED = {200, 202, 204}
ACCOUNT = re.compile(
    r"^/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[\w.()-]+"
    r"/providers/Microsoft\.CognitiveServices/accounts/[a-zA-Z0-9-]{2,64}$"
)

Http = Callable[[str, str, dict[str, str]], tuple[int, bytes]]


def http(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as err:
        return int(err.code), bytes(err.read())


def _token(env: dict[str, str], send: Http) -> str | None:
    url = env.get("IDENTITY_ENDPOINT", "") + "?resource=" + urllib.parse.quote(ARM + "/", safe=":/")
    status, body = send("GET", url, {"X-IDENTITY-HEADER": env.get("IDENTITY_HEADER", ""),
                                     "Metadata": "True"})
    if status != 200:
        print(f"FAIL the managed identity gave no token: HTTP {status}")
        return None
    token = json.loads(body or b"{}").get("access_token")
    return str(token) if token else None


def _deployments(account: str, auth: dict[str, str], send: Http) -> list[str] | None:
    names: list[str] = []
    url: str | None = f"{ARM}{account}/deployments?api-version={API}"
    while url:
        status, body = send("GET", url, auth)
        if status != 200:
            print(f"FAIL listing the deployments: HTTP {status}")
            return None
        page = json.loads(body or b"{}")
        names += [str(d["name"]) for d in page.get("value", [])]
        url = page.get("nextLink")
    return names


def run(argv: list[str], env: dict[str, str], send: Http, account: str = ACCOUNT_ID) -> int:
    """Return 0 when nothing is left deployed (or a dry run listed it), 1 on any failure."""
    dry_run = "--dry-run" in argv
    if account == PLACEHOLDER or not ACCOUNT.match(account):
        print("FAIL the account ID was not filled in by Terraform; nothing was deleted")
        return 1
    token = _token(env, send)
    if token is None:
        return 1
    auth = {"Authorization": f"Bearer {token}"}
    names = _deployments(account, auth, send)
    if names is None:
        return 1
    if not names:
        print("OK nothing to delete: the deployment is parked")
        return 0
    failed = 0
    for name in names:
        if dry_run:
            print(f"DRY-RUN would delete {name}")
            continue
        url = f"{ARM}{account}/deployments/{urllib.parse.quote(name, safe='')}?api-version={API}"
        status, _ = send("DELETE", url, auth)
        if status in DELETED:
            print(f"OK deleted {name}")
        elif status == 404:
            print(f"OK {name} was already gone")
        else:
            print(f"FAIL deleting {name}: HTTP {status}")
            failed += 1
    return 1 if failed else 0


def main() -> None:
    if run(sys.argv[1:], dict(os.environ), http) != 0:
        # An exception marks the Automation job Failed, so the failure shows in the job history.
        raise RuntimeError("the brake did not finish; see the lines above")


if __name__ == "__main__":
    main()
