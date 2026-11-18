# ADR-0003 — LangGraph for orchestration, inside Kaval's safety split

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan

## Context

Release work is long-running and stateful: a readiness check may wait days for a change approval;
a post-release watch runs for an hour; a chat thread must remember context. Kaval hand-wrote its
pipeline. The brief asks for LangChain / LangGraph.

What real teams use (checked 2026-11-18): LangGraph (stable since 1.0, October 2025) is the common
choice for stateful agents with human-in-the-loop; alternatives are hand-written loops (Kaval),
CrewAI-style role frameworks, and durable-execution engines such as Temporal wrapping agent steps.

## Decision

- **LangGraph 1.x** for every multi-step flow: `chat`, `readiness`, `release_notes`,
  `post_release_watch`, `cab_summary`. Each is a separate compiled graph with its own tool
  allowlist.
- **LangChain only as adapters** (chat models, embeddings, tool schemas). No chains as business
  logic.
- **Postgres checkpointer** (`langgraph-checkpoint-postgres`) in every environment except unit
  tests.
- **`interrupt()` is a pause, not a permission.** A graph that needs an action files a proposal
  and interrupts. The gateway records the human decision; the executor acts; the graph is
  resumed with the recorded outcome. The graph process never holds write credentials.
- Graphs are pinned by version; a renamed or removed node is a migration (an interrupt pending on
  a removed node is lost, a known failure mode reported against LangGraph 1.2).

## Consequences

**Easier:** durable threads, resumable workflows, time-travel debugging, first-class tracing.
**Harder:** a framework to learn and to upgrade; checkpoint tables grow and need pruning.
**Cost:** none (open source).
**Revisit if:** waits of days start failing in checkpoints — then put Temporal under the graphs.
