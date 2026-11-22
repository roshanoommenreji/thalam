# Lab 00 — Foundations: a public repo, CI, and read-only sandboxes

Proves SPEC-001's live requirements ([spec](../specs/SPEC-001-phase-0-foundations.md)). Written so
a stranger can repeat it from zero. **Never write any of these here** (CLAUDE.md rule 6): a real
site address, tenant ID, email address or token, or an Azure subscription ID, tenant ID or resource
name (a Foundry resource's name is its address). Use the placeholders shown, and keep real values
in `.env`.

**You need:**
- Git and uv.
- gitleaks 8.30.1: `scoop install gitleaks` or `winget install gitleaks` on Windows, a release binary elsewhere.
- The GitHub CLI, logged in.
- GNU Make: `scoop install make` on Windows.
- The Azure CLI.
- A card-backed **pay-as-you-go** Azure subscription. Claude on Foundry refuses free-trial,
  student and credit-only subscriptions.
- A browser.

**Cost:** about $0. Idle Foundry resources cost nothing, and the check only counts tokens.

## 1. Jira planning space — SPEC-001-R9

1. On your existing Jira site: sidebar → Spaces → **Create space** → Kanban → team-managed, name
   **Thalam**, key **THL** (`THLM` if taken, ADR-0009). Type the key; the wizard may suggest
   another. Make sure the space is empty before step 2: sample work items use up key numbers.
2. Create one epic per roadmap phase, Phase 0 first, so the Phase 0 epic is `THL-1`.
3. Settings → User management: confirm no bot account exists on this site. Bots live only on
   the sandbox site (section 2, ADR-0011).

**Evidence (2026-11-18):** space THL (team-managed, Kanban). Epics THL-1 to THL-9 are Phases 0
to 8, in order, created through the Jira REST API with the owner's own token. User management
lists 1 user (the owner, organization admin), 0 managed accounts and 0 service accounts: no bot
account on the planning site.

## 2. Sandbox Jira site and its read-only token — SPEC-001-R10

1. Create a **new** free Jira site, `<your-sandbox>.atlassian.net`, separate from the planning
   site. Create one space in it (any name; Phase 1 adds the fixture company).
2. Invite a bot account (for example a `+thalam-bot` alias of your email), accept, sign in as it.
3. As the bot, at id.atlassian.com → Security → API tokens → **Create API token with scopes**
   (Atlassian may first send a one-time code to the bot's email): app **Jira**, select only
   **`read:jira-work`** (enough for the check; `read:jira-user` is not needed). Expiry: the
   maximum, 365 days; write the date in the table at the end.
   If scoped tokens are not offered, stop: the fallback is an OAuth app with read scopes, which
   needs a change to `check_sandboxes.py`.
4. Cloud ID: open `https://<your-sandbox>.atlassian.net/_edge/tenant_info` and copy `cloudId`. This endpoint is undocumented but long-standing; if it fails, stop and record it here.
5. In `.env`: `JIRA_SANDBOX_CLOUD_ID`, `JIRA_SANDBOX_EMAIL`, `JIRA_READ_TOKEN`.

## 3. ServiceNow developer instance and its read-only user — SPEC-001-R11

1. developer.servicenow.com → sign in → **Request instance**. Rules as ServiceNow states them
   (checked 2026-11-18): an idle instance hibernates and wakes when you sign in to it. Since
   2026-07-11, an instance at least 90 days old is reclaimed if nobody signs in **to the instance
   itself** for 10 days; API calls (including `make sandboxes`) and visits to the developer site
   do not count. Set a weekly reminder to sign in.
2. As admin, type `Users` in the filter navigator → Users → New. User ID `thalam.read`, set a
   password, **Identity type = Machine** (this switches on *Web service access only*, which can no
   longer be ticked by hand). Roles: `itil` (to read `change_request`) and **`snc_read_only`**
   (blocks every write, whatever other roles allow). Confirm on the user's Roles tab that both are
   listed.
3. Open Change → All and confirm at least one change request exists (a new instance ships demo
   records); the write probe needs one.
4. In `.env`: `SERVICENOW_BASE_URL=https://<your-pdi>.service-now.com`,
   `SERVICENOW_READ_USER`, `SERVICENOW_READ_PASSWORD`. Quote the password if it contains ` #`.

The write probe patches the first change with its own short description. For a read-only user it
is refused (403). For a user that can write, it changes no data, but the instance may still
record an update (for example `sys_mod_count`); acceptable on a throwaway developer instance. A
403 alone does not prove `snc_read_only` is what refused the write; the Roles-tab check in step 2
is the control.

## 4. Slack app — SPEC-001-R12

1. api.slack.com/apps → Create New App → From scratch → name **Thalam** → your workspace. (Slack's free plan allows 10 apps in total.)
2. OAuth & Permissions → Bot Token Scopes: `channels:read` and `groups:read` only (so it can list
   its own channels; without them the check fails with `missing_scope`). Posting comes in Phase 3.
3. Install to Workspace, then copy the Bot User OAuth Token to `.env` as `SLACK_BOT_TOKEN`.
4. Create `#thalam` and run `/invite @Thalam` in it. Invite it nowhere else.

## 5. Microsoft Foundry: a Claude deployment behind two budgets — SPEC-001-R13

The hosted model is Claude on Microsoft Foundry, billed on the Azure invoice
([ADR-0012](../adr/0012-microsoft-foundry-and-azure.md)). Azure pay-as-you-go has **no hard
spending limit**: a budget only sends alerts, and cost data can lag a day or more. So the order
matters: **budgets first, the model last.** Portal labels below were checked on 2026-11-22; if one
has moved, follow the step's intent and note the new label here.

1. **Sign in:** `az login`. Add `--tenant <your-tenant-id>` if your account has more than one
   directory. Device-code login is blocked when Entra security defaults are on. Never paste the
   tenant or subscription ID into a file or a chat.
2. **Resource group:** `az group create --name rg-thalam --location eastus2`. West US 3 also works:
   both offer Claude Haiku and Opus as Global Standard (checked 2026-11-22). Thalam gets its own
   group so the budgets see Thalam alone.
3. **Budget `thalam-total`:** Cost Management → Budgets → Add, scope `rg-thalam`, monthly, **$100**.
   Actual-cost alerts at **70 %, 85 % and 95 %** ($70 / $85 / $95, ADR-0008), to your email.
4. **Foundry resource and project:** ai.azure.com → Create project. Under the advanced options,
   choose `rg-thalam` and the same region. This creates a Foundry resource (kind AIServices) and a
   project in it.
   - Name the resource `<your-resource>`. Its name becomes its address,
     `https://<your-resource>.services.ai.azure.com`, so it goes in `.env` only.
   - If asked about agents, choose the **basic** setup, never standard. Standard provisions
     Cosmos DB, AI Search and Storage, all billed by the hour.

   An idle resource with no deployment costs nothing.
5. **Budget `thalam-model`:** monthly, **$20** (ADR-0008's model cap), scope `rg-thalam` with a
   filter on the Foundry resource. Alerts at 50 %, 80 % and 100 %.
6. **Deploy Claude:** in the project → Model catalog → the current **Claude Haiku** → Deploy →
   **Global Standard**.
   - Accept the Azure Marketplace offer when asked. Claude is billed in Claude Consumption Units
     at Anthropic's prices.
   - If the offer is refused because of the billing country, stop here: ADR-0012's fallback (an
     OpenAI model on the same resource) needs a new R13 amendment first.
   - If the deployment offers a rate limit (tokens per minute), set the lowest value offered.
7. **Key:** project overview → endpoint and keys → copy Key 1. Do not run
   `az cognitiveservices account keys list`: it prints both keys to the terminal, and Claude Code
   is denied it.
8. **In `.env`:**
   - `ANTHROPIC_FOUNDRY_RESOURCE=<your-resource>`: the name only, not the address. The check
     builds the address itself.
   - `ANTHROPIC_FOUNDRY_API_KEY`: Key 1.
   - `LLM_HOSTED_MODEL=<deployment-name>`: the deployment's name, as shown on its page.

The check (section 8) sends one request, a **token count**, which generates no text.

**A day after the first run**, open Cost analysis for `rg-thalam`:
- Confirm that count_tokens added no Claude charge. If it did, SPEC-001's "no model generates
  text" note is amended.
- Confirm that Claude charges (once there are any) appear under the resource group. If they
  don't, re-scope `thalam-model` to the subscription with a filter on the Anthropic offer, and
  say so in the evidence.

**Evidence:** _not run yet_. Record:
- the region and the deployed model;
- both budgets: amount, thresholds, scope type and whether the alert email is set;
- whether a rate limit was set;
- the next-day cost check;
- the date.

Never record names, IDs or the key.

## 6. Repository and ruleset — SPEC-001-R1, SPEC-001-R2

Done in plan Task 9. Before the first push: `make secrets-scan` and a second full-history scan
with gitleaks' default rules alone (so the allowlist hides nothing) both gave `no leaks found`,
and every author and committer was the GitHub no-reply address.

```bash
gh repo create <you>/thalam --public --source . --remote origin --description "..."
git push -u origin main
gh repo edit <you>/thalam --enable-squash-merge --enable-merge-commit=false \
  --enable-rebase-merge=false --delete-branch-on-merge
# wait for the ci and codeql runs on main to succeed, then:
gh api -X POST repos/<you>/thalam/rulesets --input .github/rulesets/main.json
```

Apply the ruleset only after both workflows are green on `main`, and check the names first:
`gh api repos/<you>/thalam/commits/<sha>/check-runs` must list `lint`, `test`, `secrets`,
`codeql (python)` and `codeql (actions)` from app 15368 (GitHub Actions), exactly as the ruleset
requires them. A name that never appears would block every pull request.

**Evidence R1 (2026-11-18):** `gh repo view --json visibility,defaultBranchRef` gave visibility
`PUBLIC`, default branch `main`. GitHub detected the MIT licence.

**Evidence R2 (2026-11-18):** the first `ci` and `codeql` runs on `main` succeeded, and the
commit's check runs were exactly the five required names, all from app 15368. Ruleset `main`:
`active`, target the default branch, 0 bypass actors. `gh api .../rules/branches/main` lists
`deletion`, `non_fast_forward`, `required_linear_history`, `pull_request` (0 approvals, squash
only) and `required_status_checks` (`lint`, `test`, `secrets`, `codeql (python)`,
`codeql (actions)`). An empty probe commit pushed straight to `main` was refused, exit 1:

```
remote: error: GH013: Repository rule violations found for refs/heads/main.
remote: - Changes must be made through a pull request.
remote: - 5 of 5 required status checks are expected.
```

The probe was removed with `git reset --soft HEAD~1`. This evidence went in through the first
pull request, which is the PR flow's own proof.

## 7. A planted fake secret is blocked — SPEC-001-R6

The pre-commit hook (`make hooks`) was given a random, never-issued GitHub-shaped token.

**Evidence (2026-11-18):** staging `scripts/dev/leak_probe.py` holding a random 36-character
`ghp_` value and committing gave `WRN leaks found: 1` (rule `github-pat`,
`scripts/dev/leak_probe.py:1`, secret redacted) and `Commit blocked: a possible secret or real
address is staged.`, exit 1. The probe was unstaged and deleted. A staged line holding the
`000000000000` placeholder next to a real-looking 12-digit number, committed with no terminal,
gave `A 12-digit number is being committed` and `No terminal to ask ... blocked`, exit 1.

## 8. Run the sandbox check — SPEC-001-R10 to R13

```bash
make sandboxes
```

Expected: seven `PASS` lines. The output never contains a token or an address, by design, so it
can be pasted here. What a failure usually means:

- R10 read `HTTP 401`: wrong email or token, or the token belongs to the planning site's account.
- R10 write `HTTP 400 (... CAN write)`: the token has write scopes. Recreate it with read scopes only.
- R11 write `HTTP 200 (... CAN write)`: `snc_read_only` is missing from `thalam.read`.
- R12 `channels: general, thalam`: remove the app from `#general`.
- R13 `must be the resource name only`: `.env` holds an address or a URL; keep only
  `<your-resource>`.
- R13 `HTTP 401` or `HTTP 403`: a wrong key, or another resource's key.
- R13 `HTTP 404`: a wrong resource name or deployment name. Use the deployment's name, not the
  model's.
- Any `HTTP 3xx`: the service redirected (a sleeping instance, a wrong address); redirects are
  never followed, so credentials never leave the configured host.

**Evidence:** _not run yet_

## Credentials and their expiry

| Credential | Where | Expires | Rotate by |
|---|---|---|---|
| Jira sandbox read token | bot account, id.atlassian.com | _not run yet_ | |
| ServiceNow `thalam.read` | the instance | password policy of the instance | |
| ServiceNow instance | developer.servicenow.com | reclaimed after 10 days without a sign-in to it (once 90+ days old) | sign in weekly |
| Slack bot token | api.slack.com/apps | does not expire; revoke by uninstalling | |
| Foundry key (Key 1) | the Foundry resource, endpoint and keys | no expiry | switch `.env` to Key 2, then regenerate Key 1 |

## If a sandbox is down or reclaimed

`make sandboxes` fails only that sandbox's lines. A sleeping ServiceNow instance wakes from the
developer portal; a reclaimed one is re-requested, and sections 3 and 8 are repeated. Only signing
in to the instance keeps it alive; API calls do not.
