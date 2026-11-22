"""Tests for the sandbox access check (SPEC-001-R10 to R13). No network: a fake answers."""
# covers: SPEC-001-R10, SPEC-001-R11, SPEC-001-R12, SPEC-001-R13

from __future__ import annotations

import http.client
import http.server
import json
import threading
import urllib.error
import urllib.parse
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest
from check_sandboxes import (
    Result,
    _is_set,
    _send,
    check_foundry,
    load_env,
    render,
    run_all,
    urllib_http,
)

# xxxx- values: gitleaks' allowlist clears them, and none is a real credential.
ENV = {
    "JIRA_SANDBOX_CLOUD_ID": "cloud-1234",
    "JIRA_SANDBOX_EMAIL": "bot@example.com",
    "JIRA_READ_TOKEN": "xxxx-jira-token",
    "SERVICENOW_BASE_URL": "https://pdi.example.test",
    "SERVICENOW_READ_USER": "thalam.read",
    "SERVICENOW_READ_PASSWORD": "xxxx-sn-password",
    "SLACK_BOT_TOKEN": "xxxx-slack-token",
    "ANTHROPIC_FOUNDRY_RESOURCE": "xxxx-foundry",
    "ANTHROPIC_FOUNDRY_API_KEY": "xxxx-foundry-key",
    "LLM_HOSTED_MODEL": "xxxx-claude-deployment",
}

SYS_ID = "0123456789abcdef0123456789abcdef"
COUNT_TOKENS_URL = "https://xxxx-foundry.services.ai.azure.com/anthropic/v1/messages/count_tokens"
FOUNDRY_ROUTE = ("POST", COUNT_TOKENS_URL)
PATCH_PATH = f"/api/now/table/change_request/{SYS_ID}"
Answer = tuple[int, object] | Exception
READ_ONLY: dict[tuple[str, str], Answer] = {
    ("GET", "/project/search"): (200, {"values": []}),
    ("POST", "/rest/api/3/issue"): (401, {"message": "Unauthorized; scope does not match"}),
    ("GET", "/api/now/table/change_request?"): (
        200,
        {"result": [{"sys_id": SYS_ID, "short_description": "Demo change"}]},
    ),
    ("PATCH", PATCH_PATH): (403, {"error": {"message": "denied"}}),
    ("POST", "slack.com/api/auth.test"): (200, {"ok": True}),
    ("GET", "slack.com/api/users.conversations"): (
        200,
        {"ok": True, "channels": [{"name": "thalam-releases"}]},
    ),
    FOUNDRY_ROUTE: (200, {"input_tokens": 8}),
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
        ENV, FakeHttp({("PATCH", PATCH_PATH): (200, {"result": {}})})
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
    channels = {"ok": True, "channels": [{"name": "thalam-releases"}, {"name": "general"}]}
    route = ("GET", "slack.com/api/users.conversations")
    results = run_all(ENV, FakeHttp({route: (200, channels)}))
    member = _one(results, "slack", "#thalam-releases only")
    assert not member.ok
    assert member.detail == "channels: general, thalam-releases"


def test_a_missing_or_placeholder_setting_fails_its_group_without_calling_it() -> None:
    env = {k: v for k, v in ENV.items() if k != "SLACK_BOT_TOKEN"}
    env["ANTHROPIC_FOUNDRY_API_KEY"] = "placeholder"
    fake = FakeHttp()
    results = run_all(env, fake)
    slack = _one(results, "R12")
    assert not slack.ok and slack.detail == "not set in .env: SLACK_BOT_TOKEN"
    foundry = _one(results, "R13")
    assert not foundry.ok and foundry.detail == "not set in .env: ANTHROPIC_FOUNDRY_API_KEY"
    hosts = {urllib.parse.urlsplit(url).hostname or "" for _, url in fake.calls}
    skipped = ("slack.com", "services.ai.azure.com")
    assert not [h for h in hosts for d in skipped if h == d or h.endswith("." + d)], hosts


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


def test_load_env_strips_inline_comments_but_keeps_quoted_and_embedded_hashes(
    tmp_path: Path,
) -> None:
    site = "<your-sandbox>" + ".atlassian" + ".net"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "A=abc   # note\n"
        'B="x # y"   # trailing\n'
        "C='p#q'\n"
        "D=a#b\n"
        "E=   # only a comment\n"
        f"JIRA_SANDBOX_CLOUD_ID=1234abcd          # from https://{site}/_edge/tenant_info\n",
        encoding="utf-8",
    )
    assert load_env(env_file) == {
        "A": "abc",
        "B": "x # y",
        "C": "p#q",
        "D": "a#b",
        "E": "",
        "JIRA_SANDBOX_CLOUD_ID": "1234abcd",
    }


def test_a_jira_server_error_on_the_write_probe_fails_without_claiming_write_access() -> None:
    results = run_all(ENV, FakeHttp({("POST", "/rest/api/3/issue"): (500, None)}))
    write = _one(results, "jira", "refused")
    assert not write.ok
    assert write.detail == "HTTP 500"


def test_a_servicenow_server_error_on_the_write_probe_fails_without_claiming_write_access() -> (
    None
):
    route = ("PATCH", PATCH_PATH)
    results = run_all(ENV, FakeHttp({route: (500, None)}))
    write = _one(results, "servicenow", "refused")
    assert not write.ok
    assert write.detail == "HTTP 500"


def test_servicenow_row_without_a_short_description_is_never_patched() -> None:
    route = ("GET", "/api/now/table/change_request?")
    fake = FakeHttp({route: (200, {"result": [{"sys_id": SYS_ID}]})})
    results = run_all(ENV, fake)
    assert _one(results, "servicenow", "read change_request").ok
    write = _one(results, "servicenow", "refused")
    assert not write.ok
    assert write.detail == "skipped: the row has no short_description to echo back"
    assert not any(method == "PATCH" for method, _ in fake.calls)


def test_load_env_reads_a_utf8_bom_and_an_export_prefix(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_bytes(b"\xef\xbb\xbfFIRST=1\nexport SECOND=2\nexport   THIRD = 3\n")
    assert load_env(env_file) == {"FIRST": "1", "SECOND": "2", "THIRD": "3"}


def test_a_jira_read_that_fails_skips_the_write_probe() -> None:
    fake = FakeHttp({("GET", "/project/search"): (401, None)})
    results = run_all(ENV, fake)
    write = _one(results, "jira", "refused")
    assert not write.ok
    assert write.detail == "skipped: read failed (HTTP 401)"
    assert not any(method == "POST" and "/issue" in url for method, url in fake.calls)


def test_a_bug_or_a_bad_request_in_one_group_leaks_nothing_and_spares_the_others() -> None:
    leak = "bad /path/with-secret-host"
    invalid = http.client.InvalidURL(leak)
    results = run_all(ENV, FakeHttp({("GET", "/project/search"): invalid}))
    assert _one(results, "R10").detail == "unreachable (InvalidURL)"
    assert all(r.ok for r in results if not r.name.startswith("R10"))
    bug = RuntimeError("xxxx-foundry-key blew up")
    results = run_all(ENV, FakeHttp({FOUNDRY_ROUTE: bug}))
    assert _one(results, "R13").detail == "error (RuntimeError)"
    assert len([r for r in results if r.ok]) == 6
    text = "\n".join(render(results))
    assert leak not in text and "blew up" not in text
    for value in ENV.values():
        assert value not in text


def test_only_a_whole_angle_bracket_value_counts_as_a_placeholder() -> None:
    assert not _is_set(None)
    assert not _is_set("")
    assert not _is_set("Placeholder")
    assert not _is_set("<cloud-id>")
    assert not _is_set("https://<your-pdi>.service-now.com")
    assert _is_set("pa<ss>word")
    assert _is_set("xxxx<yz")
    assert _is_set("https://pdi.example.test")


def test_a_slack_error_is_printed_only_if_it_looks_like_a_slack_error_code() -> None:
    route = ("POST", "slack.com/api/auth.test")
    bad = FakeHttp({route: (200, {"ok": False, "error": "\x1b[31mred\x1b[0m"})})
    assert _one(run_all(ENV, bad), "R12", "auth.test").detail == "HTTP 200, error ?"
    good = FakeHttp({route: (200, {"ok": False, "error": "invalid_auth"})})
    assert _one(run_all(ENV, good), "R12", "auth.test").detail == "HTTP 200, error invalid_auth"


def test_servicenow_row_with_an_odd_sys_id_is_never_patched() -> None:
    route = ("GET", "/api/now/table/change_request?")
    row = {"sys_id": "../../x", "short_description": "Demo change"}
    fake = FakeHttp({route: (200, {"result": [row]})})
    write = _one(run_all(ENV, fake), "servicenow", "refused")
    assert not write.ok
    assert write.detail == "skipped: the row's sys_id is not a valid id"
    assert not any(method == "PATCH" for method, _ in fake.calls)


def test_the_foundry_check_only_counts_tokens_on_the_named_deployment() -> None:
    sent: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def http(
        method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, object]:
        sent.append((method, url, dict(headers), body))
        return 200, {"input_tokens": 8}

    [result] = check_foundry(ENV, http)
    assert result.ok and result.detail == "HTTP 200"
    [(method, url, headers, body)] = sent
    assert (method, url) == FOUNDRY_ROUTE
    assert headers["x-api-key"] == "xxxx-foundry-key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert json.loads(body or b"") == {
        "model": "xxxx-claude-deployment",
        "messages": [{"role": "user", "content": "ping"}],
    }


@pytest.mark.parametrize(
    "resource",
    [
        "https://xxxx-foundry.services.ai.azure.com/anthropic",
        "xxxx-foundry.services.ai.azure.com",
        "xxxx_foundry",
        "-xxxx",
        "x",
    ],
)
def test_a_foundry_resource_that_is_not_a_bare_name_fails_without_sending_the_key(
    resource: str,
) -> None:
    fake = FakeHttp()
    [result] = check_foundry({**ENV, "ANTHROPIC_FOUNDRY_RESOURCE": resource}, fake)
    assert not result.ok
    assert result.detail == (
        "ANTHROPIC_FOUNDRY_RESOURCE must be the resource name only: "
        "lowercase letters, digits and hyphens"
    )
    assert fake.calls == []


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (401, "HTTP 401 (check ANTHROPIC_FOUNDRY_API_KEY)"),
        (403, "HTTP 403 (check ANTHROPIC_FOUNDRY_API_KEY)"),
        (404, "HTTP 404 (check the resource and deployment names)"),
        (429, "HTTP 429"),
    ],
)
def test_a_refused_foundry_call_fails_with_a_hint(status: int, detail: str) -> None:
    results = run_all(ENV, FakeHttp({FOUNDRY_ROUTE: (status, {"type": "error"})}))
    foundry = _one(results, "R13")
    assert not foundry.ok
    assert foundry.detail == detail


@pytest.mark.parametrize(
    "payload", [None, {}, {"input_tokens": "8"}, {"input_tokens": True}, {"type": "message"}]
)
def test_a_foundry_answer_without_a_token_count_fails(payload: object) -> None:
    results = run_all(ENV, FakeHttp({FOUNDRY_ROUTE: (200, payload)}))
    foundry = _one(results, "R13")
    assert not foundry.ok
    assert foundry.detail == "HTTP 200, but the answer has no input_tokens count"


Seen = list[tuple[str, str | None]]


class _Server(http.server.ThreadingHTTPServer):
    """A local server that remembers every (path, User-Agent) it was asked for."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.seen: Seen = []


class _Handler(http.server.BaseHTTPRequestHandler):
    def _answer(self) -> None:
        server = self.server
        assert isinstance(server, _Server)
        server.seen.append((self.path, self.headers.get("User-Agent")))
        if self.path == "/redirect":
            # Back to this same server (its own port, never the request's Host header), so a
            # followed redirect would show up in `seen` as /target.
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{server.server_port}/target")
            self.end_headers()
            return
        body = b'{"error": "boom"}' if self.path == "/json500" else b"<html>not json</html>"
        self.send_response(500 if self.path == "/json500" else 200)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (name set by BaseHTTPRequestHandler)
        self._answer()

    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._answer()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture(autouse=True)
def _no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local-server tests must reach 127.0.0.1 directly, whatever the machine's proxy says."""
    proxies = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
    for name in proxies:
        monkeypatch.delenv(name, raising=False)
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(name, "127.0.0.1,localhost")


@contextmanager
def _local_server() -> Iterator[tuple[str, Seen]]:
    server = _Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server.seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_a_redirect_is_returned_as_an_answer_and_never_followed() -> None:
    with _local_server() as (base, seen):
        status, _ = _send("GET", f"{base}/redirect", {"Authorization": "xxxx-secret"}, None)
    assert status == 302
    assert [path for path, _ in seen] == ["/redirect"]


def test_an_http_error_with_a_json_body_is_an_answer() -> None:
    with _local_server() as (base, seen):
        assert _send("GET", f"{base}/json500", {}, None) == (500, {"error": "boom"})
    assert seen == [("/json500", "thalam-check-sandboxes")]


def test_a_body_that_is_not_json_gives_no_payload() -> None:
    with _local_server() as (base, _):
        assert _send("GET", f"{base}/html", {}, None) == (200, None)


def test_a_post_redirect_is_returned_as_an_answer_and_never_followed() -> None:
    with _local_server() as (base, seen):
        status, _ = _send("POST", f"{base}/redirect", {"Authorization": "xxxx-secret"}, b"{}")
    assert status == 302
    assert [path for path, _ in seen] == ["/redirect"]


def test_the_real_transport_refuses_a_plain_http_address() -> None:
    with pytest.raises(ValueError):
        urllib_http("GET", "http://127.0.0.1/x", {}, None)
