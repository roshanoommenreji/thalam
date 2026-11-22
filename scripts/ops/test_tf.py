"""`make guardrails-plan` / `guardrails-apply` run Terraform, nothing secret on a command line."""
# covers: SPEC-001-R14

from __future__ import annotations

import pytest
import tf

SUB = "00000000-0000-0000-0000-000000000000"
ENV = {"ANTHROPIC_FOUNDRY_RESOURCE": "xxxx-foundry", "THALAM_ALERT_EMAIL": "you@example.com"}


class FakeRun:
    def __init__(self, sub_code: int = 0) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.sub_code = sub_code

    def __call__(self, args: list[str], env: dict[str, str], capture: bool) -> tuple[int, str]:
        self.calls.append((args, env))
        if args[1:3] == ["account", "show"]:
            return self.sub_code, (SUB + "\n") if self.sub_code == 0 else ""
        return 0, ""


def _tf(fake: FakeRun, command: str, env: dict[str, str] = ENV) -> int:
    code: int = tf.main([command], run=fake, env=env, base_env={})
    return code


def test_plan_passes_the_three_values_as_environment_variables_only() -> None:
    fake = FakeRun()
    assert _tf(fake, "plan") == 0
    terraform = [(a, e) for a, e in fake.calls if a[0].endswith("terraform")]
    assert [a[2] for a, _ in terraform] == ["init", "plan"]
    for args, env in terraform:
        assert args[1] == "-chdir=infra/envs/azure"
        assert env["ARM_SUBSCRIPTION_ID"] == SUB
        assert env["TF_VAR_foundry_name"] == "xxxx-foundry"
        assert env["TF_VAR_alert_email"] == "you@example.com"
        joined = " ".join(args)
        assert SUB not in joined and "xxxx-foundry" not in joined and "you@" not in joined
    assert terraform[1][0][3:] == ["-input=false", "-out=tfplan"]


def test_apply_applies_only_the_saved_plan() -> None:
    fake = FakeRun()
    assert _tf(fake, "apply") == 0
    applied = [a for a, _ in fake.calls if a[0].endswith("terraform") and a[2] == "apply"]
    assert applied == [["terraform", "-chdir=infra/envs/azure", "apply", "-input=false", "tfplan"]]


@pytest.mark.parametrize("missing", ["ANTHROPIC_FOUNDRY_RESOURCE", "THALAM_ALERT_EMAIL"])
def test_a_missing_value_stops_before_terraform(missing: str) -> None:
    fake = FakeRun()
    env = {k: v for k, v in ENV.items() if k != missing}
    assert _tf(fake, "plan", env) == 1
    assert fake.calls == []


def test_an_address_instead_of_a_name_stops_before_terraform() -> None:
    fake = FakeRun()
    assert _tf(fake, "plan", {**ENV, "ANTHROPIC_FOUNDRY_RESOURCE": "https://xxxx.x"}) == 1
    assert fake.calls == []


def test_no_az_login_stops_before_terraform(capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeRun(sub_code=1)
    assert _tf(fake, "plan") == 1
    assert [a[1:3] for a, _ in fake.calls] == [["account", "show"]]
    assert "az login" in capsys.readouterr().out


def test_destroy_is_not_offered() -> None:
    with pytest.raises(SystemExit):
        tf.main(["destroy"], run=FakeRun(), env=ENV, base_env={})
