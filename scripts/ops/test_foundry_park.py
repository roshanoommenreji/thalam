"""`make foundry-up` / `foundry-down`: the deployment exists only while needed, behind guardrails.

A fake `az` stands in for Azure. It answers the calls the scripts make, the way the real CLI
does (JSON on stdout, an error code on stderr), and records every call.
"""
# covers: SPEC-001-R14

from __future__ import annotations

import foundry_park
import pytest
from az_fakes import ACCOUNT_NAME, DEPLOYMENT, ENV, GROUP, NUMBERS, RG, SUB, FakeAz
from az_fakes import budget as _budget
from az_fakes import deployment as _deployment


def _park(fake: FakeAz, command: str, env: dict[str, str] = ENV) -> int:
    code: int = foundry_park.main([command], runner=fake, env=env)
    return code


def _no_secrets(out: str) -> None:
    for secret in (ACCOUNT_NAME, DEPLOYMENT, SUB, GROUP):
        assert secret not in out


def test_up_creates_the_approved_deployment_when_the_guardrails_hold(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeAz()
    assert _park(fake, "up") == 0
    (create,) = fake.made("create")
    flags = dict(zip(create[4::2], create[5::2], strict=False))
    model = NUMBERS["model"]
    assert flags["--resource-group"] == RG
    assert flags["--name"] == ACCOUNT_NAME
    assert flags["--deployment-name"] == DEPLOYMENT
    assert flags["--model-name"] == model["name"]
    assert flags["--model-version"] == model["version"]
    assert flags["--model-format"] == model["format"]
    assert flags["--sku-name"] == model["sku"]
    assert flags["--sku-capacity"] == str(model["capacity"])
    out = capsys.readouterr().out
    assert "UP" in out and "capacity 1" in out
    _no_secrets(out)


def test_up_is_a_no_op_when_already_up() -> None:
    fake = FakeAz()
    fake.deployments = [_deployment()]
    assert _park(fake, "up") == 0
    assert fake.made("create") == []


def test_up_refuses_when_an_existing_deployment_is_over_the_approved_capacity() -> None:
    fake = FakeAz()
    fake.deployments = [_deployment(capacity=3)]
    assert _park(fake, "up") == 1
    assert fake.made("create") == []


def _refused(fake: FakeAz, capsys: pytest.CaptureFixture[str], reason: str) -> None:
    assert _park(fake, "up") == 1
    assert fake.made("create") == []
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


def test_an_unknown_command_is_refused() -> None:
    with pytest.raises(SystemExit):
        foundry_park.main(["sideways"], runner=FakeAz(), env=ENV)
