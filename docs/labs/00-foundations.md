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
- The Azure CLI, and Terraform 1.11 or later (`winget install Hashicorp.Terraform`).
- A card-backed **pay-as-you-go** Azure subscription. Claude on Foundry refuses free-trial,
  student and credit-only subscriptions.
- A browser.

**Cost:** about ₹0. An idle Foundry resource costs nothing, the deployment is parked between
sessions, the guardrails are free, and the model calls are token counts and one call of a few
tokens.

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
   site. Create one space in it (any name; Phase 1 adds the fixture company). Signed in to an
   account that already has a site, the sign-up page offers **Go to Jira** (the planning site:
   wrong) or **start a new site** (right).
2. Invite a bot account (for example a `+thalam-bot` alias of your email), accept, sign in as it.
3. As the bot, at id.atlassian.com → Security → API tokens → **Create API token with scopes**
   (Atlassian may first send a one-time code to the bot's email): app **Jira**, select only
   **`read:jira-work`** (enough for the check; `read:jira-user` is not needed). Expiry: the
   maximum, 365 days; write the date in the table at the end.
   If scoped tokens are not offered, stop: the fallback is an OAuth app with read scopes, which
   needs a change to `check_sandboxes.py`.
4. Cloud ID: open `https://<your-sandbox>.atlassian.net/_edge/tenant_info` and copy `cloudId`. This endpoint is undocumented but long-standing; if it fails, stop and record it here.
5. In `.env`: `JIRA_SANDBOX_CLOUD_ID`, `JIRA_SANDBOX_EMAIL` (the bot's full address),
   `JIRA_READ_TOKEN`.

**Evidence (2026-11-22):** a new free site, separate from the planning site, created through
**start a new site**; one team-managed Kanban space. No card was asked for. The sign-up page
started a Premium trial, which without payment details falls back to Free, so it cannot bill. A bot
account on a `+thalam-bot` alias was invited from the site's setup screen. As the bot, Atlassian
asked for an 8-digit code emailed to that alias before the token page opened. Scoped token: app
Jira, scope `read:jira-work` only, expiring 2027-11-22 (the 365-day maximum). `tenant_info`
returned a `cloudId`. `make sandboxes`: R10 read `HTTP 200`, R10 write refused `HTTP 401`.

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

**Evidence (2026-11-22):**
- **Instance:** requested on the developer site with release **Brazil**, the latest offered;
  Australia was the other choice. Ready in a few minutes. **Start building** opened it already
  signed in through the developer account.
- **User:** `thalam.read`, created with Identity type **Machine** and no password field on the
  new-user form. Reading the record back showed `identity_type=machine`,
  `web_service_access_only=true` (switched on by itself), `internal_integration_user=false`,
  active, not locked. The password was set afterwards with **Set Password**, by the owner.
- **Roles:** the user's role records show `itil` and `snc_read_only`, both assigned directly
  (`inherited=false`). `itil` also brings about 45 inherited roles, write ones among them, such as
  `sn_change_write`. Blocking all of those is exactly what `snc_read_only` is for.
- **Check:** `make sandboxes` gave R11 read `HTTP 200` and R11 write refused `HTTP 403`.

## 4. Slack app — SPEC-001-R12

Use a workspace of its own: a new free one named **Thalam** (Create Another Workspace → skip
inviting → Continue with Free), so the bot never sits beside another project's channels.

1. api.slack.com/apps → **Create an App** → under *From scratch*, **Pick features** → name
   **Thalam** → your workspace. (Slack's free plan allows 10 apps in total. In November 2026 the
   dialog also offers templates and pasting a manifest; *Pick features* is the old *From scratch*.)
2. Bot scopes: `channels:read` and `groups:read` only (so it can list its own channels; without
   them the check fails with `missing_scope`). No events. Posting comes in Phase 3.
3. Before installing, App Home → App Display Name → Edit: set **Default username** to
   `thalam_bot`. Slack refuses a channel named like a user and never renames a bot user once it
   exists, so a bot left as `thalam` blocks a channel of that name (it happened on 2026-11-22;
   SPEC-001-R12 was amended to the channel below).
4. Create and Install → Allow, then copy the Bot User OAuth Token to `.env` as `SLACK_BOT_TOKEN`.
5. Create `#thalam-releases` (public) and run `/invite @Thalam` in it. Invite it nowhere else.

**Evidence (2026-11-22):**
- **Workspace:** a new free workspace, Thalam. It comes with three channels; the bot is in none
  of them.
- **App:** Thalam, with bot scopes `channels:read` and `groups:read` only, no user scopes and no
  events.
- **The name clash:** creating `#thalam` failed with "That name is already taken by a channel,
  username, or user group". The default username was changed to `thalam_bot` and the app
  reinstalled; the consent screen asked for the same two scopes. `#thalam` was still taken, while
  `thalam_bot` was free, so the bot user keeps the name it was created with.
- **Channel:** `#thalam-releases` was created (public), and `/invite @Thalam` posted "Thalam was
  added to #thalam-releases".
- **Check:** `make sandboxes` gave R12 auth.test `HTTP 200` and R12 `channels: thalam-releases`.

## 5. Microsoft Foundry behind the guardrails — SPEC-001-R13 to R20

The hosted model is Claude on Microsoft Foundry, billed on the Azure invoice
([ADR-0012](../adr/0012-microsoft-foundry-and-azure.md)). Azure pay-as-you-go has **no hard
spending limit**: a budget only sends alerts, and cost data can lag up to three days. So the fence
and the brake go up first and the model last ([ADR-0014](../adr/0014-azure-cost-guardrails.md)).
One `terraform apply` builds everything except the deployment, which `make foundry-up` creates
and `make foundry-down` (or the brake) removes. Portal labels were checked on 2026-11-22; if one has
moved, follow the step's intent and note the new label here.

1. **Sign in:** `az login`. Add `--tenant <your-tenant-id>` if your account has more than one
   directory. Device-code login is blocked when Entra security defaults are on. Never paste the
   tenant or subscription ID into a file or a chat.
2. **Register the resource providers** Thalam uses (free, once per subscription). The Terraform
   provider no longer does this itself:

   ```bash
   for ns in Microsoft.CognitiveServices Microsoft.Automation Microsoft.Insights \
             Microsoft.Consumption Microsoft.PolicyInsights; do
     az provider register --namespace "$ns"
   done
   az provider list --query "[?registrationState=='Registered'].namespace" -o tsv
   ```
3. **`.env`:**
   - `ANTHROPIC_FOUNDRY_RESOURCE=<your-resource>`: choose a globally unique name. It becomes the
     address `https://<your-resource>.services.ai.azure.com`, so it lives in `.env` only.
   - `LLM_HOSTED_MODEL=<deployment-name>`: the name the deployment will get.
   - `THALAM_ALERT_EMAIL=<you@example.com>`: where the alerts and the brake's notice go.
4. **Plan:** `make guardrails-plan`. Nothing changes yet. Read the plan: about 20 resources to
   add, 0 to change, 0 to destroy:
   - the resource group;
   - three policy definitions, the initiative and its assignment;
   - the Foundry account and project;
   - both budgets;
   - the Automation account, its Python runtime, the runbook, the webhook, the schedule and its
     link;
   - the brake role and its assignment;
   - the action group.

   The Foundry name and the e-mail show as `(sensitive value)`.
5. **Apply (creates Azure resources):** `make guardrails-apply`. It applies the saved plan only.
   - The policy assignment comes before the Foundry account.
   - Budgets are in the billing currency, INR for an India billing account: `thalam-total`
     **₹1,500** (alerts at 70 / 85 / 95 %) and `thalam-model` **₹1,000** on the Foundry account
     (alerts at 50 / 80 / 100 %). Elsewhere, change `currency` and the amounts in
     `infra/modules/azure-guardrails/guardrails.json`, and the documents the numbers test reads,
     in one commit.
6. **R15, the fence holds.** A new assignment can take up to 30 minutes to take effect. Then try a
   deployment over the cap; it must be refused:

   ```bash
   az cognitiveservices account deployment create --resource-group rg-thalam \
     --name <your-resource> --deployment-name probe --model-name claude-haiku-5-5 \
     --model-version 2 --model-format Anthropic --sku-name GlobalStandard --sku-capacity 4
   ```

   Expected: `RequestDisallowedByPolicy`, naming the `deployments` rule. If it is created, stop:
   run `make foundry-down` and find out why before going on.
7. **R16, the brake runs.**
   - **Dry run:** Automation account `thalam-brake` → Runbooks → `thalam-brake` → Start, with the
     argument `--dry-run`. The job output says `nothing to delete: the deployment is parked`. That
     proves the identity, its token and its read access.
   - **Through the real path:** run `make foundry-up` (step 8), then Monitor → Alerts → Action
     groups → `thalam-brake` → Test, sample type **Budget**. The e-mail arrives, the runbook's job
     says `deleted`, and `make foundry-status` says `parked`. The budget's own crossing is not
     forced; its first real crossing is that link's proof, as in Kaval's ADR-0064.
8. **R14, unpark:** `make foundry-up`. It prints every guardrail, then
   `UP claude-haiku-5-5, GlobalStandard, capacity 1`.
   - **A Marketplace error on the first deployment:** deploy once from the portal instead (the
     project → Model catalog → Claude Haiku 5.5 → Deploy → Global Standard, capacity 1, the same
     deployment name). That accepts the Anthropic offer. Then `make foundry-down` and
     `make foundry-up` again.
   - **The offer refused because of the billing country:** stop. ADR-0012's fallback needs a new
     R13 amendment first.
9. **Key:** the Foundry resource → Keys and Endpoint → copy Key 1 into `.env` as
   `ANTHROPIC_FOUNDRY_API_KEY`. Do not run `az cognitiveservices account keys list`: it prints both
   keys to the terminal, and Claude Code is denied it.
10. **R13:** `make sandboxes` (section 8): seven `PASS` lines.
11. **R20, the budgets see Claude.** Send one tiny paid call: the deployment's playground in the
    Foundry portal, the message `ping`. That is a few tokens, well under ₹0.01.
12. **R17, park and sweep:** `make foundry-down`, then `make azure-sweep`, which must end `CLEAN`.
    Run the sweep at the end of every session from now on.
13. **Within 72 hours:** Cost analysis on `rg-thalam`, grouped by resource.
    - The Claude meter from step 11 must show under the Foundry account. If it doesn't, both
      budgets are blind to the model: re-scope them to the subscription, with a filter, by a SPEC
      amendment.
    - Check that the token counts added no Claude charge. If they did, SPEC-001's note on them is
      amended.

**Evidence SPEC-001-R15 (fence):** _not run yet_ (the refusal's error code and the date).

**Evidence SPEC-001-R16 (brake):** _not run yet_ (the dry-run output, the action-group test, the job's
`deleted` line, `foundry-status` afterwards).

**Evidence SPEC-001-R14 (park):** _not run yet_ (the `foundry-up` lines and the date).

**Evidence SPEC-001-R17 (sweep):** _not run yet_ (the `CLEAN` line after `foundry-down`).

**Evidence SPEC-001-R20 (meter):** _not run yet_ (where the Claude charge showed, and how long it took).

**Evidence R13:** in section 8. Never record names, IDs or the key.

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
- R12 `channels: general, thalam-releases`: remove the app from `#general`.
- R13 `must be the resource name only`: `.env` holds an address or a URL; keep only
  `<your-resource>`.
- R13 `HTTP 401` or `HTTP 403`: a wrong key, or another resource's key.
- R13 `HTTP 404`: a wrong resource name or deployment name, or the deployment is parked
  (`make foundry-up`). Use the deployment's name, not the model's.
- R13 `HTTP 429`: capacity 1 allows one request a minute. Wait a minute and run it again.
- Any `HTTP 3xx`: the service redirected (a sleeping instance, a wrong address); redirects are
  never followed, so credentials never leave the configured host.

**Evidence:** _not run yet_

## Credentials and their expiry

| Credential | Where | Expires | Rotate by |
|---|---|---|---|
| Jira sandbox read token | bot account, id.atlassian.com | 2027-11-22 | 2027-11-08: create a new scoped token, update `.env`, run `make sandboxes`, revoke the old one |
| ServiceNow `thalam.read` | the instance | password policy of the instance | |
| ServiceNow instance | developer.servicenow.com | reclaimed after 10 days without a sign-in to it (once 90+ days old) | sign in weekly |
| Slack bot token | api.slack.com/apps | does not expire; revoke by uninstalling | |
| Foundry key (Key 1) | the Foundry resource, endpoint and keys | no expiry | switch `.env` to Key 2, then regenerate Key 1 |
| Brake webhook | Automation account `thalam-brake` | one year after `make guardrails-apply` | two weeks before: delete the webhook in the portal, then `make guardrails-plan` and `make guardrails-apply` recreate it |

## If a sandbox is down or reclaimed

`make sandboxes` fails only that sandbox's lines. A sleeping ServiceNow instance wakes from the
developer portal; a reclaimed one is re-requested, and sections 3 and 8 are repeated. Only signing
in to the instance keeps it alive; API calls do not.
