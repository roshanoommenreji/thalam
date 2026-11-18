# ADR-0005 — Guardrails are layers, each stopping a different failure

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan

## Context

The agent reads text written by thousands of people (Jira tickets, commits, PRs, change notes)
and chats with users of different teams. Threats, mapped to the OWASP Top 10 for LLM
Applications: prompt injection (direct and indirect), sensitive-data disclosure, improper output
handling, excessive agency, system-prompt leakage, misinformation (hallucinated release notes),
unbounded consumption.

State of the open-source tools, checked 2026-11-18:

- **Presidio** (Microsoft, MIT) — PII detection and anonymisation; maintained.
- **NeMo Guardrails** (NVIDIA, Apache-2.0) — programmable dialog and topic rails; sends
  telemetry by default (turn it off).
- **Llama Guard / Prompt Guard** (Meta) — classifier models for unsafe content and injection;
  extra model calls, and a licence to read.
- **LLM Guard** (Protect AI) — **archived July 2026**; do not depend on it.
- **Guardrails AI** — acquired by Harvey in September 2026; treat as a risk for a core dependency.

The lesson from Kaval: no guardrail library replaces the architecture. The read-only agent is
the guardrail that cannot be talked out of its job.

## Decision

One `guard` package, called by every graph, in this order:

| # | Layer | What it does | Tool |
|---|---|---|---|
| 1 | Identity | OIDC login; every tool call carries the user; the user only sees projects their groups allow | gateway + Postgres row filters |
| 2 | Input limits | size cap, rate limit, token budget per user and per conversation | gateway |
| 3 | Input screen | PII redaction; prompt-injection classifier; topic rail (release management only) | Presidio; Prompt Guard class model on CPU; embedding similarity, NeMo if needed |
| 4 | Untrusted content | outside text flattened, capped, wrapped in labelled data blocks ("spotlighting"); never in the system prompt | Kaval ADR-0083 pattern |
| 5 | Tools | per-graph allowlist; read-only clients; argument schemas; no free-form URLs or JQL from the model without validation | LangGraph + Pydantic |
| 6 | Output | Pydantic schema; secret and PII scan; **grounding check** (every release-note line cites a Jira key or PR); escape before Slack/Jira/HTML | Pydantic, Presidio, detect-secrets-style rules |
| 7 | Action | OPA `auto`/`ask`/`never`; human approval; executor is the only writer | `policy/`, Slack |
| 8 | Evidence | golden and injection eval sets as CI gates; guardrail verdicts traced | `evals/`, Langfuse |

Each layer fails **closed** and logs a verdict; a blocked request gets a plain reply, not a
silent drop.

## Consequences

**Easier:** each layer is small, testable and replaceable; the study value is high.
**Harder:** latency — classifier calls add time; measure the p95 per layer in Phase 2.
**Cost:** CPU only; no paid guardrail service.
**Revisit if:** a managed option (e.g. Bedrock Guardrails) becomes available and cheaper than the
CPU it saves.
