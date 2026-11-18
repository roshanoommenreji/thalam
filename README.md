# Thalam

**താളം** — *the beat that keeps the ensemble in time.*

**A release coordinator that is allowed to think, but not allowed to act.**

Many teams, each releasing on its own schedule, each depending on someone else's API. Thalam keeps one central view of every release in flight, checks each one before and after it goes
out, opens the Jira release and the ServiceNow change, keeps the release notes and the calendar
current — and answers questions about all of it in chat. Nothing is created, changed or
announced until a person approves.

Sibling of [Kaval](../AWS%20AI/README.md), and built the same way.

```
 Jira ─┐                                                      ┌─▶ Jira fixVersion
 Git ──┤                                                      ├─▶ ServiceNow change
 CI ───┼─▶ collect ─▶ release graph ─▶ LangGraph ─▶ proposal ─┤   (executor only,
 CD ───┤   (read-     (components,     agent       ─▶ policy  ├─▶ release notes
 Prom ─┤    only)      dependencies,   (read-only) ─▶ approve?├─▶ calendar / Slack
 Kaval ┘               calendar)          ▲                    └─▶ rollback proposal
                                          │                               │
                              chat (web + Slack) ◀── guardrails ──▶ measure (post-release)
```

## The design in three sentences

1. **The part that thinks has no power.** The LangGraph `agent` holds read-only credentials; its
   only outputs are chat replies and rows in `proposals`. A separate `executor` holds the scoped
   Jira and ServiceNow accounts and acts only on approved proposals.
2. **Every release is checked against the whole graph, not alone.** Components and their
   dependencies come from a service catalog (Backstage `catalog-info.yaml`), so "can X go out?"
   is answered from what X depends on and what depends on X.
3. **Guardrails are layers, not a library.** Identity, input screening, untrusted-text handling,
   read-only tools, schema-checked output, policy and evals each stop a different failure.

## How it will be built

| Part | What it does | Can it change things? |
|---|---|---|
| `collector` | Reads Jira, Git, CI/CD, Prometheus (later Kaval); writes events | No |
| `agent` | LangGraph graphs: chat, readiness, notes, post-release watch; writes proposals | **No** |
| `guard` | Input and output guardrails, shared by every graph | No |
| `policy/` | Rego: `auto` / `ask` / `never`, freeze windows, dependency rules | Decides only |
| `gateway` | FastAPI: chat API (streaming), Slack, webhooks, iCal feed, login | Records decisions only |
| `executor` | Jira, ServiceNow, Confluence, calendar, Slack announcements | **The only part that can** |
| `web` | The chat app | No |
| Postgres + pgvector | Releases, graph, checks, proposals, decisions, outcomes, LangGraph checkpoints, notes index | Append-only |
| Langfuse | LLM traces, prompt versions, eval scores | No |

Stack and conventions: [ADR-0002](docs/adr/0002-inherit-kavals-stack-and-conventions.md).
Architecture: [overview](docs/architecture/overview.md). What already exists:
[prior art](docs/prior-art.md).

## Status

| | |
|---|---|
| **Phase** | 0 — Foundations, started 2026-11-18 |
| **Decided** | Name Thalam, key `THL`; budget plan $50, brake $95; local + hosted model router; web chat + Slack; Jira Cloud and ServiceNow PDI sandboxes |
| **Running cost** | $0 — nothing provisioned |

## Repository map

| Path | What lives there |
|---|---|
| `services/` | `collector`, `agent`, `guard`, `gateway`, `executor`, `shared` (Python packages) |
| `web/` | The chat UI (once D-5 is decided) |
| `policy/` | Rego rules and their tests |
| `evals/` | Golden release scenarios, injection set, scoring |
| `migrations/` | Alembic |
| `infra/` | Terraform modules and environments |
| `deploy/` | Helm chart, environments, GitOps |
| `scripts/` | `dev/`, `ops/`, `tracking/` |
| `docs/` | ADRs, specs (AI-DLC, [ADR-0010](docs/adr/0010-ai-dlc-spec-driven-workflow.md)), labs, runbooks, journal, architecture, cost, learn |
