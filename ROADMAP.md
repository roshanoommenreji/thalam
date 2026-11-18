# Roadmap

Same shape as Kaval's: phases are sequential and gated, every phase ends in something
demonstrable, and every phase can be paused without lost state.

This file is the record. The Jira board (`THL`) and any planning board follow it; when they
disagree, update this file.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` retired

---

## Phase 0 — Foundations · `[~]`

- [x] Project charter, CLAUDE.md, README, roadmap (2026-11-18)
- [x] Prior-art survey ([docs/prior-art.md](docs/prior-art.md))
- [x] ADR-0001 to ADR-0009 written and Accepted
- [x] **Decisions closed 2026-11-18:**
  - D-1 Cost: plan $50, alarms $70 / $85, brake $95 ([ADR-0008](docs/adr/0008-cost-ceiling.md))
  - D-2 Name **Thalam**, Jira key **THL** ([ADR-0009](docs/adr/0009-name-and-jira-key.md))
  - D-3 Model: local + hosted router ([ADR-0006](docs/adr/0006-model-provider-and-routing.md))
  - D-4 Sandboxes: a free Jira Cloud site and a ServiceNow Personal Developer Instance; never a
    real company tenant
  - D-5 Web chat + Slack approvals ([ADR-0007](docs/adr/0007-chat-surfaces.md))
- [x] AI-DLC spec-first workflow adopted, hand-rolled ([ADR-0010](docs/adr/0010-ai-dlc-spec-driven-workflow.md),
      [spec template](docs/specs/TEMPLATE.md)); from Kaval KAV-120 (2026-11-18)
- [ ] Requirement-to-test check in CI: a requirement ID with no citing test fails (KAV-120 Stage 2)
- [ ] SPEC-001 for Phase 0 and SPEC-002 for Phase 1 drafted and approved before building
- [ ] Sign up: Jira Cloud free site (project `THL`), ServiceNow developer program + PDI, Slack
      workspace app, Anthropic API key with a spend limit set in its console
- [ ] Git repo `thalam`, GitHub, branch protection, CI skeleton (ruff, mypy, pytest, gitleaks, CodeQL)
- [ ] Jira project + epics mirroring this roadmap
- [ ] AWS budget alarms and the hard stop, **before** any compute (Kaval Lab 01)

**Exit gate:** sandboxes reachable with read-only tokens; CI green on an empty package.

## Phase 1 — The release graph, local · `[ ]`

- [ ] Data model: `component`, `dependency`, `release`, `release_item`, `calendar_window`
      (freeze/blackout), `check`, `check_result`, `proposal`, `decision`, `execution`,
      `outcome`, `audit_event`; append-only like Kaval
- [ ] Components and dependencies loaded from Backstage `catalog-info.yaml` files
- [ ] **A fixture company**: ~8 services across 4 teams with a real dependency web
      (e.g. `web-shop → cart-api → pricing-svc → ledger-svc`), synthetic Jira data
- [ ] Compose stack: Postgres + pgvector, gateway, Ollama, Langfuse
- [ ] Dependency queries: upstream / downstream / release-order (topological sort)

**Exit gate:** "what must ship before `cart-api 2.3`?" answered from the database, no model.

## Phase 2 — Read-only chat agent · `[ ]`

- [ ] LangGraph chat graph with read-only tools (release search, graph queries, calendar, Jira
      read, ServiceNow read), Postgres checkpointer, per-user threads
- [ ] Guardrails v1 ([ADR-0005](docs/adr/0005-layered-guardrails.md)): identity, input screen,
      untrusted-text handling, output schema and escaping
- [ ] Tracing to Langfuse; token cost per conversation recorded
- [ ] Eval harness: 20 golden release questions + 10 injection cases (Kaval ADR-0018, 0072),
      as a CI gate

**Exit gate:** evals pass; an injection planted in a Jira description changes nothing.

## Phase 3 — Proposals, policy, approval, executor · `[ ]`

- [ ] Proposal schema and the `propose_*` tools (the agent's only "write")
- [ ] OPA policy: every action `ask`; `never` list (e.g. close a change as successful without a
      post-release check, release into a freeze window)
- [ ] Slack approval card (Kaval ADR-0026, 0048: reminder, escalation, expiry)
- [ ] Executor: **create Jira version** and **create ServiceNow change** (Change Management API),
      idempotent, with scoped bot accounts
- [ ] LangGraph `interrupt()` → resume on the executor's recorded outcome

**Exit gate:** a person approves in Slack; a Jira version and a ServiceNow change appear in the
sandboxes; a denied proposal changes nothing.

## Phase 4 — Pre-release readiness gate · `[ ]`

- [ ] Checks as code: CI green on the release commit; scope (all fixVersion issues done); security
      scan with no criticals; signed image + SBOM; upstream dependencies released or compatible;
      change approved and inside its window; not in a freeze; rollback plan present
- [ ] A readiness report per release, and a **go / no-go proposal**
- [ ] Cross-release conflict detection (two dependent components in the same window)

## Phase 5 — Release notes and calendar · `[ ]`

- [ ] Notes drafted from Jira + merged PRs; **every line cites its source** (grounding check)
- [ ] Audiences: engineering changelog, customer notes, CAB summary
- [ ] Release calendar with freeze windows; iCal (RFC 5545) feed; weekly digest

## Phase 6 — Post-release verification · `[ ]`

- [ ] Watch golden signals vs the pre-release baseline for a set window
- [ ] Healthy → propose "release Jira version, close change successful"; degraded → propose
      rollback and "close change with issues"
- [ ] DORA's key metrics per team (deployment frequency, lead time, change failure rate, time to
      restore)

## Phase 7 — Kubernetes and AWS · `[ ]`

Kaval's path, reused: k3d → k3s on Graviton, Helm, Flux, staging on demand, signed images,
promotion by digest, restore drills.

## Phase 8 — Harden and publish · `[ ]`

Threat model, red-team pass against OWASP's LLM and agentic top-10 lists, access review,
repo public.

## Beyond v1 — future scope

See [docs/future-scope.md](docs/future-scope.md): Kaval integration, Thalam as an MCP
server, multi-tenant, bigger-model escalation.
