# SPEC-001 — Phase 0 foundations: repo, CI, requirement check, sandboxes

- **Status:** Approved
- **Roadmap phase / Jira:** Phase 0 · THL epic for Phase 0 (created by R9)
- **Approved by / date:** Roshan, 2026-11-18
- **Amended in planning:** 2026-11-18. R5's key rule applies on story branches; the R8 fixtures are built by the test in a temporary directory (approved with the plan)
- **Amended after the pre-publication review:** 2026-11-18, approved by Roshan. R8 also fails a Built or Amended spec whose live lab still says `_not run yet_`: naming a requirement was enough for a lab to count as proof, so Built could pass with blank evidence
- **Amended for the platform switch:** 2026-11-22, approved by Roshan. The hosted model moves to Claude on Microsoft Foundry ([ADR-0012](../adr/0012-microsoft-foundry-and-azure.md)); R13, open question 3, Out of scope, Numbers, Done when and the Phase 0 model note change
- **Amended for the rupee ceiling:** 2026-11-22, approved by Roshan. The account bills in INR and the most he can spend is ₹1,500 a month, so the budgets are ₹1,500 and ₹1,000 ([ADR-0013](../adr/0013-cost-ceiling-1500-inr.md)); R13, open question 3 and Numbers change
- **Amended during the sandbox sign-ups:** 2026-11-22, approved by Roshan. R12's channel is `#thalam-releases`: Slack refuses a channel named like a user, the bot user is named `thalam`, and Slack does not rename a bot user that already exists. The rule is unchanged: one channel only
- **Amended for the cost guardrails:** 2026-11-22, approved by Roshan. Six guardrails are built and proven before the Claude deployment ([ADR-0014](../adr/0014-azure-cost-guardrails.md)): R14–R20 are added; Out of scope, Numbers, open question 3, Failure and safety, Done when and the folders R8 scans (`infra/` added) change
- **Amended for SPEC-002's Inception:** 2026-11-23, approved by Roshan. R8 no longer fails a Draft or Approved spec whose proof files are not written yet: Inception writes the spec before the code ([ADR-0010](../adr/0010-ai-dlc-spec-driven-workflow.md)), and SPEC-002 failed the check on 17 such paths. The table lists them, their shape is still checked, and from Built a missing file fails as before

> One page. `CLAUDE.md` wins over anything written here. Drafted through `superpowers:brainstorming`
> on 2026-11-18 ([ADR-0010](../adr/0010-ai-dlc-spec-driven-workflow.md)).

## Intent

Give Thalam a public repository whose `main` only changes through green CI, a check that keeps every
spec requirement tied to its proof, and read-only access to every sandbox Phase 1–2 will read. After
this, Phase 1 can start writing code without revisiting any of it.

## Out of scope

- **Azure beyond Thalam's resource group, one Foundry resource and project, one model deployment,
  the two budgets and the guardrails** (ADR-0012, ADR-0014). Hosting comes in Phase 7, with its own
  park-and-brake. No AWS at all.
- Docker, compose, Postgres, Ollama, Langfuse (Phase 1).
- Write credentials and executor bot accounts (Phase 3). Phase 0 creates read-only access only.
- Renaming the local folder: it stays `Release Agent`; the repository is `thalam`.

## Numbers

Cost **about $0**:
- GitHub Free (public repo), two Jira Free sites, a ServiceNow Personal Developer Instance, Slack Free.
- A Claude deployment on Microsoft Foundry, on a card-backed pay-as-you-go Azure subscription.
- Two Azure budgets in the billing currency, INR: **₹1,500 / month** with alerts at 70 / 85 / 95 %,
  and **₹1,000 / month** on the model (ADR-0013).
- The guardrails, about ₹0: Azure Policy, the budgets, an action group, and an Automation account
  inside its 500 free minutes a month (ADR-0014). The worst case at the capacity cap is about ₹246
  a day.
- Phase 0's model calls: a token count on every check run, and one paid call of a few tokens (well
  under ₹0.01) to prove R20.

Data: fixture data only; no real company data, URLs, tenant IDs or resource names in any committed
file (CLAUDE.md rule 6).

## Open questions (the AI asks, Roshan answers)

| # | Question | Answer | Date |
|---|---|---|---|
| 1 | Branch protection and free CodeQL need a public repo on GitHub Free. Public now, private, or Pro? | Public from day one, like Kaval. Phase 8 "repo public" becomes a final access review | 2026-11-18 |
| 2 | Jira Free cannot restrict project access. Where do planning and the sandbox live? | Two sites: THL planning on the existing site (no bots); a new sandbox site holding fixture data and the bots | 2026-11-18 |
| 3 | Thalam spends nothing on AWS before Phase 7. What guards cost in Phase 0? | The Anthropic console limit only; AWS budget item moves to the start of Phase 7. *Amended 2026-11-22 (ADR-0012): two Azure budgets, ₹1,500 (alerts 70 / 85 / 95 %) and ₹1,000 on the model (ADR-0013), created before the deployment; the hosting brake comes with hosting in Phase 7*. *Amended again 2026-11-22 (ADR-0014): the budgets plus parking, a rate cap, Azure Policy, an automated brake and a sweep, all before the deployment* | 2026-11-18 |
| 4 | How do requirements link to their proof? | `covers: SPEC-NNN-Rn` text tags in any file, checked by pytest; live proofs name a lab doc | 2026-11-18 |

## Requirements

| ID | Requirement | Proved by (test or live check) |
|---|---|---|
| SPEC-001-R1 | GitHub repo `thalam` exists, is public, default branch `main` | live: `docs/labs/00-foundations.md` |
| SPEC-001-R2 | A ruleset on `main`: changes by PR only, required checks `lint`, `test`, `secrets`, `codeql (python)`, `codeql (actions)` green, no force-push, no deletion, linear history, 0 required approvals (solo). A direct push to `main` is refused | live: `docs/labs/00-foundations.md` |
| SPEC-001-R3 | `uv sync --locked` succeeds and the empty package `thalam_shared` imports and reports a version | `services/shared/tests/test_bootstrap.py` |
| SPEC-001-R4 | ruff and `mypy --strict` run clean in the `lint` job | `.github/workflows/ci.yml` |
| SPEC-001-R5 | Commit messages are conventional; on a story branch (`type/THL-<n>-slug`) the subject carries that THL key, and a message without it fails | `scripts/dev/test_check_commits.py` |
| SPEC-001-R6 | gitleaks blocks secrets in pre-commit and in CI over the full history; a planted fake key is caught | `.github/workflows/ci.yml`, live: `docs/labs/00-foundations.md` |
| SPEC-001-R7 | CodeQL (Python, Actions) runs on PRs and `main`; Dependabot watches `uv` and Actions | `.github/workflows/codeql.yml`, `.github/dependabot.yml` |
| SPEC-001-R8 | The requirement check fails on a duplicate ID, a cited ID that is unknown or belongs to a Retired spec, a badly shaped "Proved by" path, or an unparseable spec; for a Built or Amended spec, also on a "Proved by" file that does not exist, a requirement that no file cites and no existing `live:` lab mentions, and a `live:` lab that still says `_not run yet_`. Draft and Approved specs are exempt from those three rules, and the table lists the files they name but have not written yet | `scripts/dev/test_spec_coverage.py` |
| SPEC-001-R9 | A `THL` planning project exists on the existing Jira site with one epic per roadmap phase, and no bot account on that site | live: `docs/labs/00-foundations.md` |
| SPEC-001-R10 | The sandbox Jira site's read token (scoped to read, or an OAuth app with read scopes if scoped tokens are unavailable) can read the site, and a write with it is refused | `scripts/dev/check_sandboxes.py` |
| SPEC-001-R11 | The ServiceNow read user (`snc_read_only`) can read `change_request`, and a write with it is refused | `scripts/dev/check_sandboxes.py` |
| SPEC-001-R12 | The Slack app's token passes `auth.test` and the app is a member of `#thalam-releases` only | `scripts/dev/check_sandboxes.py` |
| SPEC-001-R13 | The Claude deployment on Microsoft Foundry answers a token-count call with the key in `.env`, and Azure budgets exist before it: ₹1,500 / month on Thalam's resource group (alerts 70 / 85 / 95 %) and ₹1,000 / month on the model | `scripts/dev/check_sandboxes.py`, live: `docs/labs/00-foundations.md` |
| SPEC-001-R14 | `make foundry-up` creates the one model deployment (Claude Haiku 5.5, Global Standard, capacity 1) only when the guardrails check passes: the policy is assigned, both budgets exist with the agreed amounts, the brake is wired, and neither budget has reached its brake line this month. `make foundry-down` deletes it. Both are safe to repeat and print no resource name or ID | `scripts/ops/test_foundry_park.py`, live: `docs/labs/00-foundations.md` |
| SPEC-001-R15 | One Azure Policy assignment on Thalam's resource group refuses a region other than East US 2 (or `global`); a model deployment that is not Claude Haiku 5.5, not Global Standard, or above capacity 3; a Foundry account not of kind `AIServices`; AI Search above Free; and virtual machines, scale sets, AKS, NAT gateways, application gateways, Front Door, CDN profiles, managed PostgreSQL and SQL. A deployment at capacity 4 is refused live | `infra/modules/azure-guardrails/tests/test_azure_policy.py`, live: `docs/labs/00-foundations.md` |
| SPEC-001-R16 | When `thalam-total` reaches 95 % (₹1,425) or `thalam-model` 100 % (₹1,000), the action group `thalam-brake` runs a runbook that deletes every model deployment on Thalam's Foundry resource; the same runbook runs every night at 02:00 IST. Its identity can read the account and read and delete its deployments, on that resource only. Tests without Azure show that a dry run deletes nothing, nothing to delete and "already gone" are success, and one failed deletion fails the run after the rest are tried. Fired live through the action group | `infra/modules/azure-guardrails/tests/test_brake_runbook.py`, live: `docs/labs/00-foundations.md` |
| SPEC-001-R17 | `make azure-sweep` changes nothing and fails when a model deployment exists while parked, a resource in the group has a type not on its list, a resource tagged `project=thalam` is outside the group, or the policy assignment, a budget or the brake is missing. It is clean at the end of Lab 00 | `scripts/ops/test_azure_sweep.py`, live: `docs/labs/00-foundations.md` |
| SPEC-001-R18 | A test fails unless the ceiling (₹1,500), the brake line (₹1,425), the model budget (₹1,000), both budgets' alert thresholds, the capacity cap (3), the deployment's capacity (1) and the model (Claude Haiku 5.5) agree across ADR-0013, ADR-0014, CLAUDE.md, `docs/cost/README.md`, the Terraform, the policy files and the scripts, and unless three days at the cap, at ₹82 a unit a day, stay under ₹750 | `scripts/dev/test_budget_wiring.py` |
| SPEC-001-R19 | `.claude/settings.json` denies Claude Code deleting the policy assignment, creating a policy exemption, deleting a budget or the action group, running `terraform destroy`, and listing Foundry keys | `scripts/dev/test_budget_wiring.py` |
| SPEC-001-R20 | A real Claude call's charge shows under Thalam's resource group in Cost Management within 72 hours, so both budgets see the model's spend | live: `docs/labs/00-foundations.md` |

**How the check works (R8).** `scripts/dev/spec_coverage.py` reads `docs/specs/SPEC-*.md` (not the
template): the Status line and every `| SPEC-NNN-Rn |` row. It looks for `covers: SPEC-…` tags in
`services/`, `scripts/`, `.github/`, `policy/`, `evals/` and `infra/`, whatever the comment syntax. Run as a
command, it prints one row per requirement (cited by / live proof / missing), which is also the CI
job summary. Its test runs it on the real repo and on small broken trees it builds in a temporary
directory. It also fails closed on a malformed row, an empty specs folder, a live proof outside
docs/labs/, and a proof path outside the repo or naming a test the file does not contain. A lab
marks evidence it has not recorded yet with `_not run yet_`; a Built spec cannot name such a lab.
A Draft or Approved spec may name proof files that are not written yet; the table lists them, and
from Built they must exist.

**`check_sandboxes.py` (R10–R13).** Reads `.env`, prints pass or fail per line, never prints a token
or a site URL, keeps going when one sandbox is down. Run by hand in Phase 0; Phase 2 reuses it as a
health check. Its negative cases (refused writes) run against the sandboxes only.

## Failure and safety

- **Public from the first push:** gitleaks runs over the existing files and the pre-commit hook is
  installed before anything is pushed. ADR-0010's links to the real Jira site become plain
  "Kaval KAV-120" text (rule 6). Lab docs use placeholders such as `<your-sandbox>.atlassian.net`.
- **Read-only is enforced by the credential, not by trust:** Jira Free makes every user a project
  admin, so the token's scope is what makes it read-only; ServiceNow uses `snc_read_only`. Each has a
  refused-write test. Token expiry dates go in the lab doc.
- **Fails closed:** an unparseable spec fails the check. **Off switch:** drop the check from CI in one
  commit; ADR-0010's stop rule covers it becoming a burden.
- **A sandbox down or reclaimed** (PDIs sleep when idle and can be reclaimed; exact rules verified on
  the day): that line fails, the rest run; the lab says how to wake or re-request it.
- **Cost cannot run away while an alert waits** (ADR-0014): the deployment is parked by default,
  runs at capacity 1, sits behind a policy cap of 3, and is deleted by a brake that also runs every
  night. Budgets alert late, so the brake is the backstop and the cap is the limit. **Off switch:**
  `make foundry-down`; the brake does the same on its own.
- Non-negotiables touched: secrets (rule 6) and the read-only agent (rule 3). The model generates
  almost nothing in Phase 0: R13 only counts tokens, and R20's single call asks for one token. That call is free on Anthropic's API; on Foundry it is
  confirmed free on the first run (Lab 00 §5), or this line is amended.

## Done when

ROADMAP Phase 0 exit gate: sandboxes reachable with read-only tokens; CI green on an empty package.
Concretely: R3–R8 and R18–R19 green in CI on `main`; the guardrails (R14–R17) proven live; one run of
`check_sandboxes.py` passing R10–R13; then `make foundry-down` and a clean `make azure-sweep`; R20 seen
within 72 hours. All of it is recorded in the lab. Docs follow: ADR-0011 (public repo, two Jira
sites), ADR-0012 (Microsoft Foundry and Azure) and ADR-0014 (the guardrails); ROADMAP (Azure budgets in Phase 0, Phase 7 on Azure, Phase 8 wording); journal;
`vault/projects/thalam.md`; this spec set to Built.

## Measured (filled in at the end)

Hours · pages reviewed · defects after merge · tokens used · did the spec catch anything the old way
would have missed? (So far: three issues found before any code, namely the GitHub Free and Jira Free
limits and the AWS item sitting too early. Whether a chat-only plan would also have caught them is
not known.)
