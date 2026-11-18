# SPEC-001 — Phase 0 foundations: repo, CI, requirement check, sandboxes

- **Status:** Approved
- **Roadmap phase / Jira:** Phase 0 · THL epic for Phase 0 (created by R9)
- **Approved by / date:** Roshan, 2026-11-18
- **Amended in planning:** 2026-11-18. R5's key rule applies on story branches; the R8 fixtures are built by the test in a temporary directory (approved with the plan)

> One page. `CLAUDE.md` wins over anything written here. Drafted through `superpowers:brainstorming`
> on 2026-11-18 ([ADR-0010](../adr/0010-ai-dlc-spec-driven-workflow.md)).

## Intent

Give Thalam a public repository whose `main` only changes through green CI, a check that keeps every
spec requirement tied to its proof, and read-only access to every sandbox Phase 1–2 will read. After
this, Phase 1 can start writing code without revisiting any of it.

## Out of scope

- **AWS of any kind.** No AWS spend before Phase 7, so the budget alarms and hard stop move to the
  start of Phase 7, when the account question (Kaval's or a new one) is decided.
- Docker, compose, Postgres, Ollama, Langfuse (Phase 1).
- Write credentials and executor bot accounts (Phase 3). Phase 0 creates read-only access only.
- Renaming the local folder: it stays `Release Agent`; the repository is `thalam`.

## Numbers

Cost **$0**: GitHub Free (public repo), two Jira Free sites, a ServiceNow Personal Developer Instance,
Slack Free, an Anthropic key with a console spend limit of **≤ $20 / month** (ADR-0008's model cap;
Phase 0 spends nothing on it). Data: fixture data only; no real company data, URLs or tenant IDs in
any committed file (CLAUDE.md rule 6).

## Open questions (the AI asks, Roshan answers)

| # | Question | Answer | Date |
|---|---|---|---|
| 1 | Branch protection and free CodeQL need a public repo on GitHub Free. Public now, private, or Pro? | Public from day one, like Kaval. Phase 8 "repo public" becomes a final access review | 2026-11-18 |
| 2 | Jira Free cannot restrict project access. Where do planning and the sandbox live? | Two sites: THL planning on the existing site (no bots); a new sandbox site holding fixture data and the bots | 2026-11-18 |
| 3 | Thalam spends nothing on AWS before Phase 7. What guards cost in Phase 0? | The Anthropic console limit only; AWS budget item moves to the start of Phase 7 | 2026-11-18 |
| 4 | How do requirements link to their proof? | `covers: SPEC-NNN-Rn` text tags in any file, checked by pytest; live proofs name a lab doc | 2026-11-18 |

## Requirements

| ID | Requirement | Proved by (test or live check) |
|---|---|---|
| SPEC-001-R1 | GitHub repo `thalam` exists, is public, default branch `main` | live: `docs/labs/00-foundations.md` |
| SPEC-001-R2 | A ruleset on `main`: changes by PR only, required checks `lint`, `test`, `secrets`, `codeql` green, no force-push, no deletion, linear history, 0 required approvals (solo). A direct push to `main` is refused | live: `docs/labs/00-foundations.md` |
| SPEC-001-R3 | `uv sync --locked` succeeds and the empty package `thalam_shared` imports and reports a version | `services/shared/tests/test_bootstrap.py` |
| SPEC-001-R4 | ruff and `mypy --strict` run clean in the `lint` job | `.github/workflows/ci.yml` |
| SPEC-001-R5 | Commit messages are conventional; on a story branch (`type/THL-<n>-slug`) the subject carries that THL key, and a message without it fails | `scripts/dev/test_check_commits.py` |
| SPEC-001-R6 | gitleaks blocks secrets in pre-commit and in CI over the full history; a planted fake key is caught | `.github/workflows/ci.yml`, live: `docs/labs/00-foundations.md` |
| SPEC-001-R7 | CodeQL (Python, Actions) runs on PRs and `main`; Dependabot watches `uv` and Actions | `.github/workflows/codeql.yml`, `.github/dependabot.yml` |
| SPEC-001-R8 | The requirement check fails on a duplicate ID, a cited ID that is unknown or belongs to a Retired spec, a missing "Proved by" path, or an unparseable spec; for a Built or Amended spec, also on a requirement that no file cites and no existing `live:` lab mentions. Draft and Approved specs are exempt from that last rule | `scripts/dev/test_spec_coverage.py` |
| SPEC-001-R9 | A `THL` planning project exists on the existing Jira site with one epic per roadmap phase, and no bot account on that site | live: `docs/labs/00-foundations.md` |
| SPEC-001-R10 | The sandbox Jira site's read token (scoped to read, or an OAuth app with read scopes if scoped tokens are unavailable) can read the site, and a write with it is refused | `scripts/dev/check_sandboxes.py` |
| SPEC-001-R11 | The ServiceNow read user (`snc_read_only`) can read `change_request`, and a write with it is refused | `scripts/dev/check_sandboxes.py` |
| SPEC-001-R12 | The Slack app's token passes `auth.test` and the app is a member of `#thalam` only | `scripts/dev/check_sandboxes.py` |
| SPEC-001-R13 | The Anthropic key lists models (a free call) and its console spend limit is ≤ $20 / month | `scripts/dev/check_sandboxes.py`, live: `docs/labs/00-foundations.md` |

**How the check works (R8).** `scripts/dev/spec_coverage.py` reads `docs/specs/SPEC-*.md` (not the
template): the Status line and every `| SPEC-NNN-Rn |` row. It looks for `covers: SPEC-…` tags in
`services/`, `scripts/`, `.github/`, `policy/` and `evals/`, whatever the comment syntax. Run as a
command, it prints one row per requirement (cited by / live proof / missing), which is also the CI
job summary. Its test runs it on the real repo and on small broken trees it builds in a temporary
directory. It also fails closed on a malformed row, an empty specs folder, a live proof outside
docs/labs/, and a proof path outside the repo or naming a test the file does not contain.

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
- Non-negotiables touched: secrets (rule 6) and the read-only agent (rule 3). No model runs in Phase 0.

## Done when

ROADMAP Phase 0 exit gate: sandboxes reachable with read-only tokens; CI green on an empty package.
Concretely: R3–R8 green in CI on `main`, and one run of `check_sandboxes.py` passing R10–R13, recorded
in the lab. Docs follow: an ADR for the public repo, the two Jira sites and the AWS move; ROADMAP
(AWS line to Phase 7, Phase 8 wording); journal; `vault/projects/thalam.md`; this spec set to Built.

## Measured (filled in at the end)

Hours · pages reviewed · defects after merge · tokens used · did the spec catch anything the old way
would have missed? (So far: three issues found before any code, namely the GitHub Free and Jira Free
limits and the AWS item sitting too early. Whether a chat-only plan would also have caught them is
not known.)
