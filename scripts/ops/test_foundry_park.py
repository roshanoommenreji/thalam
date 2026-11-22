"""`make foundry-up` / `foundry-down`: the deployment exists only while needed, behind guardrails.

A fake `az` stands in for Azure. It answers the calls the scripts make, the way the real CLI
does (JSON on stdout, an error code on stderr), and records every call.
"""
# covers: SPEC-001-R14

from __future__ import annotations

from pathlib import Path

import azure_cli
import foundry_park
import pytest
from az_fakes import ACCOUNT_NAME, DEPLOYMENT, ENV, GROUP, NUMBERS, ORG, RG, SUB, FakeAz
from az_fakes import budget as _budget
from az_fakes import deployment as _deployment


def _park(fake: FakeAz, command: str, env: dict[str, str] = ENV) -> int:
    code: int = foundry_park.main([command], runner=fake, env=env, sleep=lambda _: None)
    return code


def _no_secrets(out: str) -> None:
    for secret in (ACCOUNT_NAME, DEPLOYMENT, SUB, GROUP, ORG):
        assert secret not in out


def test_up_creates_the_approved_deployment_when_the_guardrails_hold(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeAz()
    assert _park(fake, "up") == 0
    (body,) = fake.puts
    model = NUMBERS["model"]
    assert body["sku"] == {"name": model["sku"], "capacity": model["capacity"]}
    assert body["properties"]["model"] == {
        "format": model["format"], "name": model["name"], "version": model["version"],
    }
    (put,) = [c for c in fake.calls if c[:3] == ["rest", "--method", "put"]]
    url = put[put.index("--url") + 1]
    assert f"/resourceGroups/{RG}/" in url and url.split("?")[0].endswith(
        f"/accounts/{ACCOUNT_NAME}/deployments/{DEPLOYMENT}")
    assert "api-version=" in url
    out = capsys.readouterr().out
    assert "UP" in out and "capacity 1" in out
    _no_secrets(out)


def test_up_sends_anthropic_s_attestation_fields_from_env() -> None:
    # Azure signs the Anthropic Marketplace offer with these (Lab 00 step 3); they live in .env.
    fake = FakeAz()
    assert _park(fake, "up") == 0
    assert fake.puts[0]["properties"]["modelProviderData"] == {
        "organizationName": ORG, "countryCode": "XX", "industry": "technology",
    }


@pytest.mark.parametrize(("key", "bad"), [
    ("CLAUDE_ORGANIZATION_NAME", ""),
    ("CLAUDE_COUNTRY_CODE", "India"),
    ("CLAUDE_INDUSTRY", "Technology"),
])
def test_up_refuses_without_valid_attestation_fields(
    key: str, bad: str, capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeAz()
    assert _park(fake, "up", {**ENV, key: bad}) == 1
    assert fake.calls == []
    assert key in capsys.readouterr().out


def test_up_waits_until_the_deployment_has_succeeded(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.poll_states = ["Creating", "Creating", "Succeeded"]
    assert _park(fake, "up") == 0
    polls = [c for c in fake.calls if c[:3] == ["rest", "--method", "get"] and "/deployments/" in
             c[c.index("--url") + 1]]
    assert len(polls) == 3
    assert "UP" in capsys.readouterr().out


def test_up_reports_a_failed_provisioning_by_its_code(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.poll_states = ["Creating", "Failed"]
    assert _park(fake, "up") == 1
    out = capsys.readouterr().out
    assert "AnthropicOrganizationCreationException" in out and "make foundry-down" in out
    _no_secrets(out)


def test_up_is_a_no_op_when_already_up() -> None:
    fake = FakeAz()
    fake.deployments = [_deployment()]
    assert _park(fake, "up") == 0
    assert fake.puts == []


@pytest.mark.parametrize("state", ["Deleting", "Creating"])
def test_up_waits_while_a_deployment_is_in_flight(
    state: str, capsys: pytest.CaptureFixture[str],
) -> None:
    # Found by the live brake test (2026-11-22): the brake's DELETE is accepted at once, and the
    # deployment stays listed as Deleting for about half a minute. It is not "up already".
    fake = FakeAz()
    fake.deployments = [_deployment(state=state)]
    assert _park(fake, "up") == 1
    assert fake.puts == []
    out = capsys.readouterr().out
    assert "WAIT" in out and state in out and "UP" not in out
    _no_secrets(out)


def test_up_refuses_a_failed_deployment_until_it_is_parked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeAz()
    fake.deployments = [_deployment(state="Failed")]
    assert _park(fake, "up") == 1
    assert fake.puts == []
    out = capsys.readouterr().out
    assert "REFUSED" in out and "make foundry-down" in out


def test_up_refuses_when_an_existing_deployment_is_over_the_approved_capacity() -> None:
    fake = FakeAz()
    fake.deployments = [_deployment(capacity=3)]
    assert _park(fake, "up") == 1
    assert fake.puts == []


def _refused(fake: FakeAz, capsys: pytest.CaptureFixture[str], reason: str) -> None:
    assert _park(fake, "up") == 1
    assert fake.puts == []
    out = capsys.readouterr().out
    assert "REFUSED" in out and reason in out, out
    _no_secrets(out)


def test_up_refuses_without_the_policy(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.assignment = None
    _refused(fake, capsys, "policy")


def test_up_refuses_when_the_policy_is_not_enforced(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    assert fake.assignment is not None
    fake.assignment["properties"]["enforcementMode"] = "DoNotEnforce"
    _refused(fake, capsys, "policy")


def test_up_refuses_without_a_budget(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.budgets = [_budget("thalam-total")]
    _refused(fake, capsys, "thalam-model")


def test_up_refuses_a_budget_with_the_wrong_amount(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.budgets = [_budget("thalam-total", amount=15000), _budget("thalam-model")]
    _refused(fake, capsys, "thalam-total")


def test_up_refuses_a_budget_missing_an_alert(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    broken = _budget("thalam-total")
    broken["properties"]["notifications"].pop("Actual_GreaterThanOrEqualTo_70_Percent")
    fake.budgets = [broken, _budget("thalam-model")]
    _refused(fake, capsys, "thalam-total")


def test_up_refuses_when_the_brake_line_does_not_reach_the_action_group(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeAz()
    broken = _budget("thalam-model")
    broken["properties"]["notifications"]["Actual_GreaterThanOrEqualTo_100_Percent"][
        "contactGroups"] = []
    fake.budgets = [_budget("thalam-total"), broken]
    _refused(fake, capsys, "thalam-model")


def test_up_refuses_without_the_action_group(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.action_group = None
    _refused(fake, capsys, "brake")


def test_up_refuses_without_the_nightly_run(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.job_schedules = []
    _refused(fake, capsys, "nightly")


def test_up_refuses_once_a_budget_has_reached_its_brake_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The brake fired this month: a restart would only spend again (Kaval ADR-0064's open gap).
    fake = FakeAz()
    fake.budgets = [_budget("thalam-total", spend=1425.0), _budget("thalam-model")]
    _refused(fake, capsys, "brake line")


def test_up_refuses_a_resource_name_that_is_an_address(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    env = {**ENV, "ANTHROPIC_FOUNDRY_RESOURCE": "https://xxxx.services.ai.azure.com"}
    assert _park(fake, "up", env) == 1
    assert fake.calls == []
    assert "resource name" in capsys.readouterr().out


def test_up_reports_azure_s_error_code_and_nothing_else(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeAz()
    fake.fail_create = "the policy said no"
    assert _park(fake, "up") == 1
    out = capsys.readouterr().out
    assert "RequestDisallowedByPolicy" in out
    _no_secrets(out)


def test_down_deletes_every_deployment(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    stray = {**_deployment(), "name": "xxxx-stray"}
    fake.deployments = [_deployment(), stray]
    assert _park(fake, "down") == 0
    assert len(fake.made("delete")) == 2 and fake.deployments == []
    out = capsys.readouterr().out
    assert "PARKED" in out
    _no_secrets(out)


def test_down_is_a_no_op_when_parked_and_needs_no_guardrails_check() -> None:
    fake = FakeAz()
    fake.assignment = None  # down must work even with the guardrails broken
    assert _park(fake, "down") == 0
    assert fake.made("delete") == []
    assert not any(c[:1] == ["rest"] for c in fake.calls)


def test_status_says_up_or_parked(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    assert _park(fake, "status") == 0
    assert "parked" in capsys.readouterr().out
    fake.deployments = [_deployment()]
    assert _park(fake, "status") == 0
    out = capsys.readouterr().out
    assert "up" in out and "capacity 1" in out
    _no_secrets(out)


def test_status_names_a_deployment_that_is_not_ready(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.deployments = [_deployment(state="Deleting")]
    assert _park(fake, "status") == 0
    out = capsys.readouterr().out
    assert out.startswith("deleting") and "up " not in out


def test_env_is_read_as_the_sandbox_check_reads_it(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "﻿# comment\n"
        "ANTHROPIC_FOUNDRY_RESOURCE=xxxx-foundry   # the name only\n"
        "export LLM_HOSTED_MODEL=xxxx-haiku\n"
        'THALAM_ALERT_EMAIL="you@example.com"\n'
        "SERVICENOW_READ_PASSWORD='a$(b) #c'\n",
        encoding="utf-8",
    )
    assert azure_cli.read_env(env) == {
        "ANTHROPIC_FOUNDRY_RESOURCE": "xxxx-foundry",
        "LLM_HOSTED_MODEL": "xxxx-haiku",
        "THALAM_ALERT_EMAIL": "you@example.com",
        "SERVICENOW_READ_PASSWORD": "a$(b) #c",
    }


def test_an_unknown_command_is_refused() -> None:
    with pytest.raises(SystemExit):
        foundry_park.main(["sideways"], runner=FakeAz(), env=ENV)
