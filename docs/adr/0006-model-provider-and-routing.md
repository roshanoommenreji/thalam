# ADR-0006 — Model provider and routing

- **Status:** Accepted 2026-11-18 (option C, "go with recommended")
- **Date:** 2026-11-18
- **Deciders:** Roshan

## Context

Kaval runs Gemma 3 1B on CPU, which suits single-shot, schema-bound diagnosis. This project
needs **multi-turn chat with tool calling** and long-form writing (release notes, CAB
summaries) — a 1B model is not good enough for that. Kaval's Bedrock path never completed a live
call because AWS restricts the Marketplace subscription on that account (Kaval ADR-0019, 0098).

## Options

| Option | Good | Bad |
|---|---|---|
| A. Local only (Ollama, a 4–8B tool-calling model) | $0 per token, private, same as Kaval | needs a bigger node (≥8–16 GB), slower, weaker answers |
| B. Hosted only (Anthropic API direct, or Bedrock if the restriction lifts) | best quality, no GPU | per-token cost, data leaves the account |
| C. **Router** — local small model for classification, guard checks and evals smoke runs; hosted model for chat and writing | cost-aware, teaches routing, matches Kaval's escalation idea | two paths to test |

## Recommendation

**C**, behind LangChain's provider-neutral chat model interface so the choice is a config value.
Every call records model, tokens and cost; a monthly token budget is enforced like Kaval's AWS
brake. Prices are verified on the day, not recalled.

## Decision

Option C. A local small model (Ollama) for guard checks, classification and offline eval smoke
runs; a hosted model for chat and long-form writing. Provider order: the Anthropic API directly
first (Kaval's account cannot subscribe to Bedrock's Marketplace models), Bedrock when that
restriction lifts. The exact model IDs and prices are checked on the day the router is built
(Phase 2), not recalled.

## Consequences

**Easier:** good chat quality without a GPU; routing is itself a lesson.
**Harder:** two paths to test; data leaves the account for hosted calls, so guard layer 3
(PII redaction) runs before every hosted call.
**Cost:** the hosted model has its own monthly cap inside the project budget
([ADR-0008](0008-cost-ceiling.md)); the router refuses hosted calls past it and falls back to
the local model with a plain notice.
**Revisit if:** the token cap is hit two months running, or a local 4–8B model passes the evals.
