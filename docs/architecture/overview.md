# Architecture overview

Updated whenever a component is added, removed or rewired (Definition of Done, item 6).

## Components

```
                 ┌────────────── read-only ──────────────┐
 Jira ──┐        │                                       │
 Git ───┤        ▼                                       │
 CI/CD ─┼─▶ collector ─▶ Postgres ◀─ agent (LangGraph) ──┘ reads via read-only clients / MCP
 Prom ──┤   (events)     + pgvector     │   graphs: chat, readiness, notes,
 Kaval ─┘                               │           post_release_watch, cab_summary
                                        │   guard: in → screen → model → out
                                        │   model: router → Ollama (local) or Claude on
                                        │          Microsoft Foundry; knowledge: Foundry IQ
                                        ▼
                                    proposals ─▶ policy (OPA) ─▶ auto / ask / never
                                                                    │
                               web chat ◀─ gateway (FastAPI) ─▶ Slack approval card
                                                │ decision row
                                                ▼
                                            executor ─▶ Jira · ServiceNow · Confluence ·
                                                │       calendar · Slack announcements
                                                ▼
                                    executions, outcomes ─▶ graph resumes (checkpoint)
```

Hosted pieces ([ADR-0012](../adr/0012-microsoft-foundry-and-azure.md)): Claude on Microsoft
Foundry, reached only through the router; Foundry IQ (Free or Serverless tier) serves release
policies, runbooks, CAB rules and freeze calendars from Phase 2. Postgres stays the system of
record for the release graph. Phase 7 hosts the services on Azure.

**Cost guardrails around the hosted model** ([ADR-0014](../adr/0014-azure-cost-guardrails.md)),
outside the application and built with Terraform (`infra/`):
- Azure Policy on Thalam's resource group (one model, one deployment type, a capacity cap);
- two budgets whose brake-line alerts go to an action group;
- an Automation runbook that deletes the deployment, started by that action group and every night;
- `make foundry-up` / `foundry-down`, which own the deployment, and `make azure-sweep`, which
  checks it.

None of these is reachable from `agent` or `executor`.

## Core entities

| Table | Meaning |
|---|---|
| `component` | a deployable service, from `catalog-info.yaml`; owner team |
| `dependency` | component → component (runtime / API / data), with version constraint |
| `release` | component + version + planned window + state |
| `release_item` | Jira issues and PRs in that release |
| `calendar_window` | freeze, blackout, maintenance windows |
| `check`, `check_result` | readiness and post-release checks and their results |
| `proposal` → `decision` → `execution` → `outcome` | Kaval's chain, unchanged |
| `audit_event` | every guardrail verdict, tool call and decision |
| LangGraph checkpoint tables | durable conversation and workflow state |

## Release life cycle

`planned → scoped → ready (checks pass) → change approved → deploying → verifying →
released | rolled back`. Each arrow that touches an outside system is a proposal.

## Trust boundaries

1. Users → gateway (login, limits).
2. Outside text → agent (guard layer 4).
3. Agent → proposals (the only write).
4. Executor → outside systems (scoped bot accounts, idempotency keys).
