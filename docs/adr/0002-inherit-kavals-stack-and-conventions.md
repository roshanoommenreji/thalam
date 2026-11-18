# ADR-0002 — Inherit Kaval's stack and conventions

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan

## Context

The brief is "everything the same as the AWS AI project (Kaval)", for two reasons: it is a study
project, and it will later be integrated with Kaval. Reusing the stack makes the integration
cheap and lets every Kaval lab, runbook and ADR be read as a reference.

Kaval does not, however, cover everything this project needs: it has no agent framework (its
pipeline is hand-written), no chat surface beyond Slack cards, and no LLM-specific tracing.

## Decision

Copy unchanged from Kaval:

| Area | Choice |
|---|---|
| Language and libraries | Python 3.11, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, `uv` |
| Quality | `ruff`, `mypy --strict`, `pytest`, gitleaks, CodeQL, Dependabot, Trivy |
| Data | Postgres 16 + pgvector |
| Safety architecture | read-only `agent`, scoped `executor`, OPA `auto`/`ask`/`never`, Slack approval with expiry |
| Untrusted text | flatten, cap, label as data; escape model text before display |
| Evals | golden set + injection set as CI gates |
| Platform | k3s on Graviton (`linux/arm64`), Helm umbrella chart, Flux, Terraform |
| Environments | `local` → `staging` (on demand) → `prod`, promotion by signed digest |
| Supply chain | SBOM, keyless signing, admission check |
| Process | ADRs, labs, journal, Jira-linked conventional commits, Definition of Done |
| Local model runtime | Ollama |

Add, each with its own ADR: LangGraph ([0003](0003-langgraph-for-orchestration.md)), OTel +
Langfuse ([0004](0004-llm-observability-otel-and-langfuse.md)), a layered guardrail stack
([0005](0005-layered-guardrails.md)), a model router ([0006](0006-model-provider-and-routing.md)),
a web chat ([0007](0007-chat-surfaces.md)).

## Consequences

**Easier:** Kaval's labs are a ready textbook; shared table shapes (proposal, decision,
execution, outcome) make FS-1 integration mostly a matter of feeds.
**Harder:** Kaval's single small node will not fit Langfuse, a chat UI and a larger model; the
capacity plan must be measured in Phase 1, not assumed.
**Cost:** none yet.
**Revisit if:** a Kaval choice turns out to be wrong for a multi-team, chat-heavy workload.
