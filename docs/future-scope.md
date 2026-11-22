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
servers with read-only tools on both sides. Since [ADR-0012](adr/0012-microsoft-foundry-and-azure.md),
Kaval runs on AWS and Thalam on Azure, which is one more reason to choose MCP over HTTPS rather than
a shared database.

## FS-2 — Thalam as an MCP server

Expose read-only tools ("what ships this week", "dependencies of X") so Claude, IDEs and Kaval can
ask it directly.

## FS-3 — Multi-tenant

Many business units, each with its own Jira and ServiceNow, one control plane (Kaval FS-5).

## FS-4 — Risk scoring from history

Learn change-failure likelihood from past outcomes; feed it to policy as evidence, never as
permission (Kaval FS-12, Jev).

## FS-5 — Work IQ and Teams, for an organisation on Microsoft 365

Microsoft IQ (Ignite, 17 Nov 2026) has four parts. Thalam uses one of them, Foundry IQ
([ADR-0012](adr/0012-microsoft-foundry-and-azure.md)). **Work IQ** grounds an agent in Microsoft 365:
meetings, documents, chats and past decisions. For a company that runs CAB meetings in Teams and
keeps its change policy in SharePoint, that is the missing context. It covers what the last CAB
decided about `ledger-svc`, and who objected.

It pairs with a Teams chat surface ([ADR-0007](adr/0007-chat-surfaces.md)'s "revisit if the company
standard is Teams"). Work IQ's reads go through the agent's read-only path; anything it writes
(Office documents, messages) goes through the executor like every other write.

Not now: Thalam's fixture company has no Microsoft 365 tenant, and Work IQ's licensing (Microsoft 365
Copilot licence or Copilot Credits) was unclear on 2026-11-22. **Fabric IQ** (governed business
data in Fabric) needs Fabric capacity, so it is noted only. **Web IQ** (web grounding) has no
release use yet.
