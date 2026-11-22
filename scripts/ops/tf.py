"""Run Terraform for infra/envs/azure (ADR-0014): `make guardrails-plan`, then `guardrails-apply`.

Three values reach Terraform as environment variables only, so none is in git or on a command line:
the subscription (`az account show`), the Foundry name (ANTHROPIC_FOUNDRY_RESOURCE) and the alert
e-mail (THALAM_ALERT_EMAIL), the last two read from .env as data, never run as shell. `apply` takes
only the plan `plan` saved, so what is applied is what was reviewed. There is no destroy here: run
it yourself if you ever mean it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable

import azure_cli

CHDIR = "-chdir=infra/envs/azure"
Run = Callable[[list[str], dict[str, str], bool], tuple[int, str]]


def real_run(args: list[str], env: dict[str, str], capture: bool) -> tuple[int, str]:
    exe = shutil.which(args[0]) or args[0]
    done = subprocess.run([exe, *args[1:]], env=env, cwd=azure_cli.ROOT, check=False,
                          capture_output=capture, text=True)
    return done.returncode, done.stdout if capture else ""


def main(argv: list[str] | None = None, run: Run = real_run, env: dict[str, str] | None = None,
         base_env: dict[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terraform for Thalam's Azure guardrails.")
    parser.add_argument("command", choices=["plan", "apply"])
    args = parser.parse_args(argv)
    values = azure_cli.read_env() if env is None else env
    name = values.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
    email = values.get("THALAM_ALERT_EMAIL", "")
    if not azure_cli.RESOURCE_NAME.match(name):
        print("FAIL  set ANTHROPIC_FOUNDRY_RESOURCE in .env to the Foundry name (not a URL)")
        return 1
    if "@" not in email:
        print("FAIL  set THALAM_ALERT_EMAIL in .env to where the budget alerts should go")
        return 1
    code, sub = run(["az", "account", "show", "--query", "id", "-o", "tsv"], {
        **(dict(os.environ) if base_env is None else base_env)}, True)
    if code != 0 or not sub.strip():
        print("FAIL  no Azure login: run `az login` first")
        return 1
    child = {
        **(dict(os.environ) if base_env is None else base_env),
        "ARM_SUBSCRIPTION_ID": sub.strip(),
        "TF_VAR_foundry_name": name,
        "TF_VAR_alert_email": email,
    }
    code, _ = run(["terraform", CHDIR, "init", "-input=false"], child, False)
    if code != 0:
        return code
    if args.command == "plan":
        return run(["terraform", CHDIR, "plan", "-input=false", "-out=tfplan"], child, False)[0]
    return run(["terraform", CHDIR, "apply", "-input=false", "tfplan"], child, False)[0]


if __name__ == "__main__":
    sys.exit(main())
