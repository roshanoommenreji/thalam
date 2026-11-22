"""The brake runbook deletes every model deployment on Thalam's Foundry account, and nothing else.

No Azure here: a fake HTTP function stands in for the managed identity endpoint and Resource
Manager. The live proof (the action group fires it) is in docs/labs/00-foundations.md.
"""
# covers: SPEC-001-R16

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

MODULE = Path(__file__).resolve().parents[1]
RUNBOOK = MODULE / "brake" / "brake_runbook.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("brake_runbook", RUNBOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


brake = _load()

# All-zero IDs: the repository's placeholders (gitleaks allowlist, the 12-digit hook).
SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
ACCOUNT = f"{SUB}/resourceGroups/rg-thalam/providers/Microsoft.CognitiveServices/accounts/xxxx"
ARM = "https://management.azure.com"
ENV = {"IDENTITY_ENDPOINT": "http://localhost:42356/msi/token", "IDENTITY_HEADER": "xxxx-header"}
LIST = f"{ARM}{ACCOUNT}/deployments?api-version={brake.API}"


class FakeHttp:
    """Answers by (method, URL without its query string); records every call."""

    def __init__(self, routes: dict[tuple[str, str], tuple[int, object]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url, headers))
        status, body = self.routes.get((method, url.split("?")[0]), (599, {"error": "no route"}))
        return status, json.dumps(body).encode()

    def methods(self, method: str) -> list[str]:
        return [url for m, url, _ in self.calls if m == method]


def _fake(deployments: list[str], deletes: dict[str, int] | None = None) -> FakeHttp:
    routes: dict[tuple[str, str], tuple[int, object]] = {
        ("GET", ENV["IDENTITY_ENDPOINT"]): (200, {"access_token": "xxxx-token"}),
        ("GET", LIST.split("?")[0]): (200, {"value": [{"name": n} for n in deployments]}),
    }
    for name, status in (deletes or {}).items():
        routes[("DELETE", f"{ARM}{ACCOUNT}/deployments/{name}")] = (status, {})
    return FakeHttp(routes)


def _run(fake: FakeHttp, *argv: str, account: str = ACCOUNT) -> int:
    code: int = brake.run(list(argv), ENV, fake, account)
    return code


def test_it_deletes_every_deployment_on_the_account(capsys: pytest.CaptureFixture[str]) -> None:
    fake = _fake(["thalam-haiku", "stray"], {"thalam-haiku": 202, "stray": 204})
    assert _run(fake) == 0
    assert [u.split("?")[0].rsplit("/", 1)[1] for u in fake.methods("DELETE")] == [
        "thalam-haiku", "stray",
    ]
    assert "deleted thalam-haiku" in capsys.readouterr().out


def test_a_dry_run_deletes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    fake = _fake(["thalam-haiku"], {"thalam-haiku": 202})
    assert _run(fake, "--dry-run") == 0
    assert fake.methods("DELETE") == []
    assert "would delete thalam-haiku" in capsys.readouterr().out


def test_nothing_to_delete_is_success(capsys: pytest.CaptureFixture[str]) -> None:
    fake = _fake([])
    assert _run(fake) == 0
    assert fake.methods("DELETE") == []
    assert "parked" in capsys.readouterr().out


def test_already_gone_is_success() -> None:
    assert _run(_fake(["thalam-haiku"], {"thalam-haiku": 404})) == 0


def test_one_failed_delete_fails_the_run_after_the_rest_are_tried(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = _fake(["a", "b", "c"], {"a": 500, "b": 202, "c": 202})
    assert _run(fake) == 1
    assert len(fake.methods("DELETE")) == 3
    out = capsys.readouterr().out
    assert "FAIL deleting a: HTTP 500" in out and "deleted c" in out


def test_a_failed_listing_fails_the_run() -> None:
    fake = _fake([])
    fake.routes[("GET", LIST.split("?")[0])] = (403, {"error": "AuthorizationFailed"})
    assert _run(fake) == 1
    assert fake.methods("DELETE") == []


def test_a_failed_token_fails_the_run() -> None:
    fake = _fake(["thalam-haiku"], {"thalam-haiku": 202})
    fake.routes[("GET", ENV["IDENTITY_ENDPOINT"])] = (500, {})
    assert _run(fake) == 1
    assert fake.methods("DELETE") == []


def test_the_listing_follows_next_links() -> None:
    fake = _fake([], {"a": 202, "b": 202})
    page2 = f"{ARM}{ACCOUNT}/deployments/page2"
    fake.routes[("GET", LIST.split("?")[0])] = (200, {"value": [{"name": "a"}], "nextLink": page2})
    fake.routes[("GET", page2)] = (200, {"value": [{"name": "b"}]})
    assert _run(fake) == 0
    assert len(fake.methods("DELETE")) == 2


def test_it_uses_the_managed_identity_token_on_every_resource_manager_call() -> None:
    fake = _fake(["a"], {"a": 202})
    _run(fake)
    token_call, *arm_calls = fake.calls
    assert token_call[2] == {"X-IDENTITY-HEADER": "xxxx-header", "Metadata": "True"}
    assert "resource=https://management.azure.com/" in token_call[1]
    assert arm_calls and all(h == {"Authorization": "Bearer xxxx-token"} for _, _, h in arm_calls)


def test_it_refuses_to_run_while_the_placeholder_is_still_there() -> None:
    fake = _fake(["a"], {"a": 202})
    assert _run(fake, account=brake.PLACEHOLDER) == 1
    assert fake.calls == []


@pytest.mark.parametrize(
    "bad", ["", "xxxx", "https://management.azure.com/x", f"{ACCOUNT}/../../x"]
)
def test_it_refuses_an_account_id_that_is_not_one(bad: str) -> None:
    fake = _fake(["a"], {"a": 202})
    assert _run(fake, account=bad) == 1
    assert fake.calls == []


def test_the_file_holds_the_placeholder_once_for_terraform_to_replace() -> None:
    # Terraform's replace() swaps every copy; the constant that detects it is built in pieces.
    text = RUNBOOK.read_text(encoding="utf-8")
    assert text.count("__ACCOUNT_ID__") == 1
    assert brake.ACCOUNT_ID == brake.PLACEHOLDER


def test_it_uses_the_standard_library_only() -> None:
    # Automation's Python runtime is used without extra packages.
    text = RUNBOOK.read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", text, re.M)
    allowed = {"__future__", "json", "os", "re", "sys", "urllib.error", "urllib.parse",
               "urllib.request", "collections.abc", "typing"}
    assert set(imports) <= allowed, set(imports) - allowed


def _block(tf: str, kind: str, name: str) -> str:
    found = re.search(rf'resource "{kind}" "{name}" \{{(.*?)\n\}}', tf, re.S)
    assert found, f"brake.tf defines {kind}.{name}"
    return found.group(1)


def test_the_brake_role_can_only_read_and_delete_deployments_on_the_one_account() -> None:
    # Azure lets a custom role be assignable at a resource group, not at one resource, so the role
    # is defined on Thalam's group and assigned on the Foundry account only.
    tf = (MODULE / "brake.tf").read_text(encoding="utf-8")
    role = _block(tf, "azurerm_role_definition", "brake")
    actions = re.findall(r'"(Microsoft\.[^"]+)"', role)
    assert sorted(actions) == [
        "Microsoft.CognitiveServices/accounts/deployments/delete",
        "Microsoft.CognitiveServices/accounts/deployments/read",
        "Microsoft.CognitiveServices/accounts/read",
    ]
    assert "not_actions" not in role and "data_actions" not in role
    assert re.search(r"assignable_scopes\s*=\s*\[azurerm_resource_group\.thalam\.id\]", role)
    assignment = _block(tf, "azurerm_role_assignment", "brake")
    assert re.search(r"\bscope\s*=\s*azurerm_cognitive_account\.foundry\.id\b", assignment)
    assert re.search(r"principal_id\s*=\s*azurerm_automation_account\.brake\.identity", assignment)
    # No other role is granted to the brake's identity anywhere in the module.
    module_tf = "".join(p.read_text(encoding="utf-8") for p in MODULE.glob("*.tf"))
    assert module_tf.count('resource "azurerm_role_assignment"') == 1
