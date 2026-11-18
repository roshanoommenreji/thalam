# ADR-0008 — Cost ceiling: plan for $50, alarm by $100

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan

## Context

Roshan set a budget of **$50–$100 a month**, "plan efficiently; we can go above if needed".
This project needs more than Kaval: a hosted model, Langfuse, a web front end, possibly a
larger node. Kaval's lesson is that limits are built before compute exists, and that a raise is
argued in writing (Kaval ADR-0008, 0028).

## Decision

| Line | Amount | What happens |
|---|---|---|
| Planning target | **$50 / month** | every design is costed against this first |
| Alarm 1 | $70 | e-mail; the journal records why |
| Alarm 2 | $85 | e-mail; non-essential environments parked |
| Hard brake | $95 | staging stopped, hosted model calls refused (local fallback) |
| Above $100 | allowed | only by a new ADR that says what the extra money buys |

The ceiling covers AWS **and** model tokens **and** any SaaS tier. The hosted-model share starts
at a cap of **$20 / month**, enforced in code by the router.

Carried over from Kaval unchanged: no NAT gateway, no ALB, no persistent EKS, no RDS, no GPU;
staging on demand; production parks itself when idle; every resource priced on the day it is
proposed.

## Consequences

**Easier:** room for a 8 GB node and hosted chat without a fight over every dollar.
**Harder:** two meters to watch (AWS bill, token spend); `docs/cost/` tracks both.
**Revisit if:** two months in a row cross alarm 1.
