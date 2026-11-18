"""Tests for the sandbox access check (SPEC-001-R10 to R13). No network: a fake answers."""
# covers: SPEC-001-R10, SPEC-001-R11, SPEC-001-R12, SPEC-001-R13

from __future__ import annotations

import urllib.error
from collections.abc import Mapping
from pathlib import Path

from check_sandboxes import Result, load_env, render, run_all

# xxxx- values: gitleaks' allowlist clears them, and none is a real credential.
ENV = {
    "JIRA_SANDBOX_CLOUD_ID": "cloud-1234",
    "JIRA_SANDBOX_EMAIL": "bot@example.com",
    "JIRA_READ_TOKEN": "xxxx-jira-token",
    "SERVICENOW_BASE_URL": "https://pdi.example.test",
    "SERVICENOW_READ_USER": "thalam.read",
    "SERVICENOW_READ_PASSWORD": "xxxx-sn-password",
    "SLACK_BOT_TOKEN": "xxxx-slack-token",
    "ANTHROPIC_API_KEY": "xxxx-anthropic-key",
}

Answer = tuple[int, object] | Exception
READ_ONLY: dict[tuple[str, str], Answer] = {
    ("GET", "/project/search"): (200, {"values": []}),
    ("POST", "/rest/api/3/issue"): (401, {"message": "Unauthorized; scope does not match"}),
    ("GET", "/api/now/table/change_request?"): (
        200,
        {"result": [{"sys_id": "abc", "short_description": "Demo change"}]},
    ),
    ("PATCH", "/api/now/table/change_request/abc"): (403, {"error": {"message": "denied"}}),
    ("POST", "slack.com/api/auth.test"): (200, {"ok": True}),
    ("GET", "slack.com/api/users.conversations"): (
        200,
        {"ok": True, "channels": [{"name": "thalam"}]},
    ),
    ("GET", "api.anthropic.com/v1/models"): (200, {"data": []}),
}


class FakeHttp:
    def __init__(self, overrides: dict[tuple[str, str], Answer] | None = None) -> None:
        self.routes = {**READ_ONLY, **(overrides or {})}
        self.calls: list[tuple[str, str]] = []

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, object]:
        self.calls.append((method, url))
        for (verb, fragment), answer in self.routes.items():
            if verb == method and fragment in url:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        raise AssertionError(f"unexpected call {method} {url}")


def _one(results: list[Result], *words: str) -> Result:
    matches = [r for r in results if all(w in r.name for w in words)]
    assert len(matches) == 1, [r.name for r in results]
    return matches[0]


def test_every_check_passes_against_read_only_sandboxes() -> None:
    results = run_all(ENV, FakeHttp())
    assert len(results) == 7
    assert all(r.ok for r in results), render(results)


def test_a_jira_token_that_can_write_fails() -> None:
    results = run_all(ENV, FakeHttp({("POST", "/rest/api/3/issue"): (400, {"errors": {}})}))
    write = _one(results, "jira", "refused")
    assert not write.ok
    assert "CAN write" in write.detail


def test_a_servicenow_user_that_can_write_fails() -> None:
    results = run_all(
        ENV, FakeHttp({("PATCH", "/api/now/table/change_request/abc"): (200, {"result": {}})})
    )
    write = _one(results, "servicenow", "refused")
    assert not write.ok
    assert "CAN write" in write.detail


def test_servicenow_with_no_change_rows_cannot_prove_refusal() -> None:
    fake = FakeHttp({("GET", "/api/now/table/change_request?"): (200, {"result": []})})
    results = run_all(ENV, fake)
    assert not _one(results, "servicenow", "read change_request").ok
    assert not _one(results, "servicenow", "refused").ok
    assert not any(method == "PATCH" for method, _ in fake.calls)


def test_servicenow_address_must_be_https() -> None:
    results = run_all({**ENV, "SERVICENOW_BASE_URL": "http://pdi.example.test"}, FakeHttp())
    assert any("must start with https://" in r.detail for r in results if "servicenow" in r.name)


def test_a_slack_app_in_other_channels_fails() -> None:
    channels = {"ok": True, "channels": [{"name": "thalam"}, {"name": "general"}]}
    route = ("GET", "slack.com/api/users.conversations")
    results = run_all(ENV, FakeHttp({route: (200, channels)}))
    member = _one(results, "slack", "#thalam only")
    assert not member.ok
    assert member.detail == "channels: general, thalam"


def test_a_missing_or_placeholder_setting_fails_its_group_without_calling_it() -> None:
    env = {k: v for k, v in ENV.items() if k != "SLACK_BOT_TOKEN"}
    env["ANTHROPIC_API_KEY"] = "placeholder"
    fake = FakeHttp()
    results = run_all(env, fake)
    slack = _one(results, "R12")
    assert not slack.ok and slack.detail == "not set in .env: SLACK_BOT_TOKEN"
    assert not _one(results, "R13").ok
    assert not any("slack.com" in url or "anthropic.com" in url for _, url in fake.calls)


def test_an_unreachable_sandbox_fails_alone() -> None:
    results = run_all(
        ENV, FakeHttp({("GET", "/project/search"): urllib.error.URLError("down")})
    )
    jira = _one(results, "R10")
    assert not jira.ok and jira.detail == "unreachable (URLError)"
    assert all(r.ok for r in results if not r.name.startswith("R10"))


def test_the_output_never_contains_a_secret_or_an_address() -> None:
    results = run_all(
        ENV,
        FakeHttp({
            ("POST", "/rest/api/3/issue"): (400, {"errors": {}}),
            ("POST", "slack.com/api/auth.test"): (200, {"ok": False, "error": "invalid_auth"}),
        }),
    )
    text = "\n".join(render(results))
    for value in ENV.values():
        assert value not in text


def test_load_env_reads_values_and_skips_comments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('# a comment\n\nA=1\nB = "two"\nnot a setting\n', encoding="utf-8")
    assert load_env(env_file) == {"A": "1", "B": "two"}
    assert load_env(tmp_path / "missing.env") == {}
