"""`make azure-sweep`: read-only, and it fails on anything billable left behind (ADR-0014).

Kaval's lab-sweep, in Azure terms: the exit gate after every session.
"""
# covers: SPEC-001-R17

from __future__ import annotations

import azure_sweep
import pytest
from az_fakes import ACCOUNT_NAME, GROUP, SUB, FakeAz
from az_fakes import budget as _budget
from az_fakes import deployment as _deployment


def _sweep(fake: FakeAz, *argv: str) -> int:
    code: int = azure_sweep.main(list(argv), runner=fake)
    return code


def _out(capsys: pytest.CaptureFixture[str]) -> str:
    out = capsys.readouterr().out
    for secret in (ACCOUNT_NAME, SUB, GROUP):
        assert secret not in out
    return out


def test_a_clean_parked_group_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert _sweep(FakeAz()) == 0
    out = _out(capsys)
    assert "FAIL" not in out and "CLEAN" in out


def test_the_sweep_changes_nothing() -> None:
    fake = FakeAz()
    fake.deployments = [_deployment()]
    _sweep(fake)
    writes = {"create", "delete", "update", "set", "put", "post", "patch"}
    for call in fake.calls:
        assert not writes & {c.lower() for c in call}, call


def test_a_deployment_left_up_fails(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.deployments = [_deployment()]
    assert _sweep(fake) == 1
    assert "make foundry-down" in _out(capsys)


def test_an_approved_deployment_passes_when_one_is_expected() -> None:
    fake = FakeAz()
    fake.deployments = [_deployment()]
    assert _sweep(fake, "--expect-up") == 0


@pytest.mark.parametrize("bad", [_deployment(capacity=4), _deployment(model="claude-opus-5-5")])
def test_an_unapproved_deployment_fails_even_when_one_is_expected(bad: dict[str, object]) -> None:
    fake = FakeAz()
    fake.deployments = [bad]
    assert _sweep(fake, "--expect-up") == 1


def test_a_resource_of_a_type_not_on_the_list_fails(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    assert fake.resources is not None
    fake.resources.append({"type": "Microsoft.Compute/disks", "resourceGroup": "rg-thalam"})
    assert _sweep(fake) == 1
    assert "Microsoft.Compute/disks" in _out(capsys)


def test_the_type_list_is_compared_without_regard_to_case() -> None:
    fake = FakeAz()
    assert fake.resources is not None
    fake.resources.append({"type": "MICROSOFT.INSIGHTS/ACTIONGROUPS", "resourceGroup": "rg-thalam"})
    assert _sweep(fake) == 0


def test_a_thalam_resource_outside_the_group_fails(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.tagged_elsewhere = [{"type": "Microsoft.Storage/storageAccounts", "resourceGroup": "rg-x"}]
    assert _sweep(fake) == 1
    assert "outside" in _out(capsys)


def test_a_missing_group_fails(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeAz()
    fake.resources = None
    assert _sweep(fake) == 1
    assert "ResourceGroupNotFound" in _out(capsys)


def test_a_missing_policy_fails() -> None:
    fake = FakeAz()
    fake.assignment = None
    assert _sweep(fake) == 1


def test_a_missing_budget_fails() -> None:
    fake = FakeAz()
    fake.budgets = [_budget("thalam-model")]
    assert _sweep(fake) == 1


def test_a_missing_brake_fails() -> None:
    fake = FakeAz()
    fake.action_group = None
    assert _sweep(fake) == 1


def test_expecting_a_deployment_when_there_is_none_fails() -> None:
    assert _sweep(FakeAz(), "--expect-up") == 1


def test_it_checks_the_deployments_of_every_foundry_account_in_the_group() -> None:
    # The sweep needs no .env: it finds the accounts itself.
    fake = FakeAz()
    _sweep(fake)
    prefix = ["cognitiveservices", "account", "deployment", "list"]
    lists = [c for c in fake.calls if c[:4] == prefix]
    assert len(lists) == 1
