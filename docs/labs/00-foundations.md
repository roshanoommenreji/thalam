# Lab 00 — Foundations: a public repo, CI, and read-only sandboxes

Proves SPEC-001's live requirements ([spec](../specs/SPEC-001-phase-0-foundations.md)). Written so
a stranger can repeat it from zero. **Never write a real site address, tenant ID, email address
or token here** (CLAUDE.md rule 6). Use the placeholders shown, and keep real values in `.env`.

**You need:** Git, uv, gitleaks 8.30.1 (`scoop install gitleaks` or `winget install gitleaks` on
Windows; a release binary elsewhere), the GitHub CLI (logged in), GNU Make (`scoop install make` on Windows), a browser. **Cost:** $0.

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

## 5. Anthropic key with a spend limit — SPEC-001-R13

1. platform.claude.com (formerly console.anthropic.com) → create a workspace `thalam`. The
   Default Workspace cannot have its own spend limit or notifications.
2. In workspace `thalam`: set a **monthly spend limit of $20 or less** (ADR-0008) and an email
   notification below it, where the console offers it (notifications are available when
   Anthropic bills you directly). Organization-wide limits are under Settings → Spend limits.
3. API keys → in workspace `thalam`, create key `thalam-dev`, then copy it to `.env` as
   `ANTHROPIC_API_KEY`.

**Evidence:** _not run yet_ (the workspace, the limit and the notification actually set, the date; never the key).

## 6. Repository and ruleset — SPEC-001-R1, SPEC-001-R2

Done in plan Task 9. Commands and outputs go here.

**Evidence R1:** _not run yet_ (`gh repo view roshanoommenreji/thalam --json visibility,defaultBranchRef`)

**Evidence R2:** _not run yet_ (ruleset id and rules from `gh api`, plus the refused direct push)

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
| Anthropic `thalam-dev` | platform.claude.com, workspace `thalam` | no expiry; revoke in the console | |

## If a sandbox is down or reclaimed

`make sandboxes` fails only that sandbox's lines. A sleeping ServiceNow instance wakes from the
developer portal; a reclaimed one is re-requested, and sections 3 and 8 are repeated. Only signing
in to the instance keeps it alive; API calls do not.
