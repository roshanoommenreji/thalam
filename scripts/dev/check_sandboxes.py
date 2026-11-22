#!/usr/bin/env python3
"""Read-only access to every sandbox, proved (SPEC-001-R10 to R13).

    uv run python scripts/dev/check_sandboxes.py      # reads .env at the repository root

One line per check, PASS or FAIL. It never prints a token, a password or a site address. A
sandbox that is down fails its own lines while the others still run. Exit 1 if anything failed.

The refused-write probes are shaped so that even a credential that CAN write changes nothing:
  Jira        POST an issue with no fields: a writer gets 400 (validation), read-only 401 or 403
  ServiceNow  PATCH the first change with its own short description: a writer gets 200 (a no-op
              update), read-only gets 403
The model check (Claude on Microsoft Foundry, ADR-0012) only counts tokens; it never asks the
model to write anything.
Stdlib only.
"""
# covers: SPEC-001-R10, SPEC-001-R11, SPEC-001-R12, SPEC-001-R13

from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.client import HTTPException, HTTPMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
Http = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, object]]
REFUSED = (401, 403)


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool
    detail: str


def load_env(path: Path) -> dict[str, str]:
    """KEY=value lines from a .env file; blank lines, comments and other lines skipped."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():  # PowerShell 5.1 adds a BOM
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[re.sub(r"^export\s+", "", key.strip())] = _clean_value(value)
    return values


def _clean_value(raw: str) -> str:
    """A quoted value runs to its closing quote; an unquoted one stops at ' #' (a comment)."""
    value = raw.strip()
    if value[:1] in ("\"", "'"):
        end = value.find(value[0], 1)
        return value[1:end] if end != -1 else value[1:]
    return re.split(r"(?:^|\s)#", raw, maxsplit=1)[0].strip()


def _is_set(value: str | None) -> bool:
    """Empty, 'placeholder', a whole <...> or an https://<... address is not a real setting."""
    if not value or "placeholder" in value.lower():
        return False
    return not (re.fullmatch(r"<[^<>]*>", value) or value.startswith("https://<"))


def _basic(user: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib would forward the Authorization header to wherever a 3xx points. Never follow."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        return None


def _send(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None
) -> tuple[int, object]:
    """Send one request: (status, parsed JSON or None). HTTP errors and 3xx are answers."""
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={**headers, "User-Agent": "thalam-check-sandboxes"},
    )
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=20) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        payload: object = json.loads(raw) if raw else None
    except ValueError:
        payload = None
    return status, payload


def urllib_http(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None
) -> tuple[int, object]:
    """The real transport. Only https:// addresses are called."""
    if not url.startswith("https://"):
        raise ValueError("only https:// addresses are called")
    return _send(method, url, headers, body)


def check_jira(env: Mapping[str, str], http: Http) -> list[Result]:
    # Scoped API tokens are called through api.atlassian.com with the site's cloud ID.
    base = f"https://api.atlassian.com/ex/jira/{env['JIRA_SANDBOX_CLOUD_ID']}/rest/api/3"
    headers = {
        "Authorization": _basic(env["JIRA_SANDBOX_EMAIL"], env["JIRA_READ_TOKEN"]),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    status, _ = http("GET", f"{base}/project/search?maxResults=1", headers, None)
    read = Result("R10 jira sandbox: read with the read token", status == 200, f"HTTP {status}")
    write_name = "R10 jira sandbox: a write with the read token is refused"
    if status != 200:
        return [read, Result(write_name, False, f"skipped: read failed (HTTP {status})")]
    status, _ = http("POST", f"{base}/issue", headers, b'{"fields": {}}')
    hint = " (400 means this token CAN write)" if status == 400 else ""
    return [read, Result(write_name, status in REFUSED, f"HTTP {status}{hint}")]


def check_servicenow(env: Mapping[str, str], http: Http) -> list[Result]:
    base = env["SERVICENOW_BASE_URL"].rstrip("/")
    read_name = "R11 servicenow: read change_request with the read user"
    write_name = "R11 servicenow: a write with the read user is refused"
    if not base.startswith("https://"):
        detail = "SERVICENOW_BASE_URL must start with https://"
        return [Result(read_name, False, detail), Result(write_name, False, detail)]
    headers = {
        "Authorization": _basic(env["SERVICENOW_READ_USER"], env["SERVICENOW_READ_PASSWORD"]),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    query = "sysparm_limit=1&sysparm_fields=sys_id,short_description"
    status, payload = http("GET", f"{base}/api/now/table/change_request?{query}", headers, None)
    rows = payload.get("result") if isinstance(payload, dict) else None
    first = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
    if first is None:
        why = f"HTTP {status}" + (", but no change_request row to probe" if status == 200 else "")
        return [Result(read_name, False, why), Result(write_name, False, "skipped: " + why)]
    read = Result(read_name, status == 200, f"HTTP {status}")
    echo = first.get("short_description")
    if not isinstance(echo, str):
        skipped = "skipped: the row has no short_description to echo back"
        return [read, Result(write_name, False, skipped)]
    body = json.dumps({"short_description": echo}).encode()
    sys_id = first.get("sys_id")
    if not isinstance(sys_id, str) or not re.fullmatch(r"[0-9a-f]{32}", sys_id):
        skipped = "skipped: the row's sys_id is not a valid id"
        return [read, Result(write_name, False, skipped)]
    status, _ = http("PATCH", f"{base}/api/now/table/change_request/{sys_id}", headers, body)
    hint = " (2xx means this user CAN write)" if 200 <= status < 300 else ""
    return [read, Result(write_name, status in REFUSED, f"HTTP {status}{hint}")]


def _slack_error(payload: object) -> str:
    if isinstance(payload, dict) and payload.get("ok") is not True:
        error = payload.get("error")
        safe = isinstance(error, str) and re.fullmatch(r"[a-z_]{1,40}", error)
        return f", error {error if safe else '?'}"
    return ""


def check_slack(env: Mapping[str, str], http: Http) -> list[Result]:
    headers = {"Authorization": f"Bearer {env['SLACK_BOT_TOKEN']}"}
    status, payload = http("POST", "https://slack.com/api/auth.test", headers, b"")
    ok = status == 200 and isinstance(payload, dict) and payload.get("ok") is True
    auth = Result(
        "R12 slack: the bot token passes auth.test", ok, f"HTTP {status}" + _slack_error(payload)
    )
    url = (
        "https://slack.com/api/users.conversations"
        "?types=public_channel,private_channel&exclude_archived=true&limit=200"
    )
    status, payload = http("GET", url, headers, None)
    name = "R12 slack: the app is in #thalam only"
    channels = payload.get("channels") if isinstance(payload, dict) and payload.get("ok") else None
    if not isinstance(channels, list):
        return [auth, Result(name, False, f"HTTP {status}" + _slack_error(payload))]
    names = sorted(str(c.get("name", "?")) for c in channels if isinstance(c, dict))
    return [auth, Result(name, names == ["thalam"], "channels: " + (", ".join(names) or "none"))]


# An Azure resource name: 2 to 64 lowercase letters, digits and hyphens, no hyphen at either end.
RESOURCE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}[a-z0-9]")
FOUNDRY_HINTS = {
    401: " (check ANTHROPIC_FOUNDRY_API_KEY)",
    403: " (check ANTHROPIC_FOUNDRY_API_KEY)",
    404: " (check the resource and deployment names)",
}


def check_foundry(env: Mapping[str, str], http: Http) -> list[Result]:
    """Claude on Microsoft Foundry (ADR-0012): count the tokens of a one-word prompt.

    The address is built here from the resource name, never taken from config, so nothing in .env
    can point the key at another host. Token counting generates nothing.
    """
    name = "R13 foundry: the Claude deployment answers a token count"
    resource = env["ANTHROPIC_FOUNDRY_RESOURCE"]
    if not RESOURCE_NAME.fullmatch(resource):
        detail = (
            "ANTHROPIC_FOUNDRY_RESOURCE must be the resource name only: "
            "lowercase letters, digits and hyphens"
        )
        return [Result(name, False, detail)]
    url = f"https://{resource}.services.ai.azure.com/anthropic/v1/messages/count_tokens"
    headers = {
        "x-api-key": env["ANTHROPIC_FOUNDRY_API_KEY"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = json.dumps(
        {"model": env["LLM_HOSTED_MODEL"], "messages": [{"role": "user", "content": "ping"}]}
    ).encode()
    status, payload = http("POST", url, headers, body)
    if status != 200:
        return [Result(name, False, f"HTTP {status}{FOUNDRY_HINTS.get(status, '')}")]
    count = payload.get("input_tokens") if isinstance(payload, dict) else None
    if not isinstance(count, int) or isinstance(count, bool):
        return [Result(name, False, "HTTP 200, but the answer has no input_tokens count")]
    return [Result(name, True, "HTTP 200")]


Check = Callable[[Mapping[str, str], Http], list[Result]]
JIRA_KEYS = ("JIRA_SANDBOX_CLOUD_ID", "JIRA_SANDBOX_EMAIL", "JIRA_READ_TOKEN")
SERVICENOW_KEYS = ("SERVICENOW_BASE_URL", "SERVICENOW_READ_USER", "SERVICENOW_READ_PASSWORD")
FOUNDRY_KEYS = ("ANTHROPIC_FOUNDRY_RESOURCE", "ANTHROPIC_FOUNDRY_API_KEY", "LLM_HOSTED_MODEL")
GROUPS: tuple[tuple[str, tuple[str, ...], Check], ...] = (
    ("R10 jira sandbox", JIRA_KEYS, check_jira),
    ("R11 servicenow", SERVICENOW_KEYS, check_servicenow),
    ("R12 slack", ("SLACK_BOT_TOKEN",), check_slack),
    ("R13 foundry", FOUNDRY_KEYS, check_foundry),
)
KEYS = {key for _, keys, _ in GROUPS for key in keys}


def run_all(env: Mapping[str, str], http: Http) -> list[Result]:
    results: list[Result] = []
    for name, keys, check in GROUPS:
        missing = [key for key in keys if not _is_set(env.get(key))]
        if missing:
            results.append(Result(name, False, "not set in .env: " + ", ".join(missing)))
            continue
        try:
            results.extend(check(env, http))
        except (OSError, ValueError, HTTPException) as err:  # URLError is an OSError
            results.append(Result(name, False, f"unreachable ({type(err).__name__})"))
        except Exception as err:  # backstop: one group's bug must not hide the others
            results.append(Result(name, False, f"error ({type(err).__name__})"))  # type only
    return results


def render(results: list[Result]) -> list[str]:
    return [f"{'PASS' if r.ok else 'FAIL'}  {r.name}  ({r.detail})" for r in results]


def main() -> int:
    env = load_env(ROOT / ".env")
    env.update({key: value for key, value in os.environ.items() if key in KEYS})
    results = run_all(env, urllib_http)
    print("\n".join(render(results)))
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
