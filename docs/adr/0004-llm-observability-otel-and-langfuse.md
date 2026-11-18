# ADR-0004 — LLM observability: OpenTelemetry in code, Langfuse as the backend

- **Status:** Accepted (hosting choice reviewed at Phase 7)
- **Date:** 2026-11-18
- **Deciders:** Roshan

## Context

Every model call, tool call, guardrail verdict and token cost must be traceable per conversation
and per release. Options checked 2026-11-18:

| Option | Shape | Trade-off |
|---|---|---|
| LangSmith | LangChain's own platform; deepest LangGraph integration | Proprietary; self-hosting is Enterprise-only |
| Langfuse | MIT core, framework-neutral, OTel-native; acquired by ClickHouse in January 2026 | Self-hosting needs ClickHouse, Redis and object storage |
| Arize Phoenix and similar | Open source, OTel-based | Smaller eval/prompt tooling |

Kaval's rule is self-host where it is cheap and sensible, and stay portable.

## Decision

- Instrument with **OpenTelemetry**, using the GenAI semantic conventions, so the backend is
  swappable.
- **Langfuse** is the backend: traces, prompt versions, datasets, scores. Locally it runs in
  Compose. For staging/prod, measure its memory first; Langfuse Cloud's free tier is the
  fallback if self-hosting does not fit the node.
- Prometheus keeps the service-health metrics, as in Kaval; an alert on guardrail block rate and
  on eval-score drift.
- PII is redacted **before** a span is exported, never after.

## Consequences

**Easier:** one trace per conversation from input guard to executor; cost per release.
**Harder:** another stateful system to run and back up.
**Cost:** $0 locally; self-hosted cost to be measured in Phase 7.
**Revisit if:** a hosted LangSmith project becomes worth its cost (for example, to share traces
with people outside the project), or Langfuse's licence changes after the acquisition.
