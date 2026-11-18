# Future scope

## FS-1 — Kaval integration

Kaval's roadmap names this kind of work as its own FS-1 ("integration mini-projects"): wire the
agent into third-party systems such as Jira. This project is that, at full size, and the two
connect both ways:

| Direction | What flows | Why it matters |
|---|---|---|
| Thalam → Kaval | every release as a **change event** (component, version, time, change number) | Kaval's context builder already uses "recent changes" to diagnose; a bad release becomes obvious |
| Kaval → Thalam | incidents and their fingerprints during a post-release window | post-release verification gets a second opinion; the change record gets the incident link |
| Shared | the proposal → decision → execution → outcome shape, OPA, Slack approval | one approval habit for ops and releases |

Mechanism, to decide then: a shared Postgres schema is simplest but couples them; **an event feed
(webhook or queue) or each exposing an MCP server** keeps them separate. Recommendation: MCP
servers with read-only tools on both sides.

## FS-2 — Thalam as an MCP server

Expose read-only tools ("what ships this week", "dependencies of X") so Claude, IDEs and Kaval can
ask it directly.

## FS-3 — Multi-tenant

Many business units, each with its own Jira and ServiceNow, one control plane (Kaval FS-5).

## FS-4 — Risk scoring from history

Learn change-failure likelihood from past outcomes; feed it to policy as evidence, never as
permission (Kaval FS-12, Jev).
