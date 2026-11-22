# ADR-0013 — Cost ceiling: ₹1,500 a month, the model ₹1,000

- **Status:** Accepted
- **Date:** 2026-11-22
- **Deciders:** Roshan ("max I can do is 1500 per month"; "₹1,500 total, ₹1,000 model")

## Context

[ADR-0008](0008-cost-ceiling.md) set the ceiling in dollars: plan $50, alarms $70 / $85, brake $95,
$100 as the line that needs an ADR, and a $20 cap on the hosted model.
[ADR-0012](0012-microsoft-foundry-and-azure.md) copied those amounts into two Azure budgets.

The live check after `az login` (2026-11-22) showed that the Azure billing account is in India and
bills in **INR**. Azure budgets are set in the billing currency. At Azure's own price-list rate that
day (about ₹95 to the dollar), the budgets came to ₹9,500 and ₹1,900. Roshan's answer: the most he
can spend is **₹1,500 a month**, about $15.75.

Two things make the real maximum matter more than it did:

- **Azure pay-as-you-go has no hard spending limit.** A budget only sends alerts, and its data can
  lag a day or more (ADR-0012). An alarm set above what Roshan can pay would fire after the money
  is gone.
- **Thalam's spending is small until Phase 7.** Phases 0–6 run on the laptop, so the hosted model is
  almost the only meter. Phase 0 spends nothing: the check only counts tokens. On Claude Haiku 5.5
  ($0.10 per million input tokens, $0.50 per million output), a month of development chat costs a
  few hundred rupees.

## Decision

The ceiling is set in rupees, in the billing currency:

| Line | Amount | What happens |
|---|---|---|
| Planning target | **under ₹750 / month** | every design is costed against this first |
| Alarm 1 | ₹1,050 (70 %) | e-mail; the journal records why |
| Alarm 2 | ₹1,275 (85 %) | e-mail; non-essential use stops; the hosted model only for what needs it |
| Brake | ₹1,425 (95 %) | hosted model calls refused (local fallback); staging stopped once it exists |
| Ceiling | **₹1,500 / month** | going above it needs a new ADR, written before the spend |

- **It covers everything:** Azure, model tokens and any SaaS tier.
- **Budget `thalam-total`:** ₹1,500 a month on Thalam's resource group, with alerts at 70, 85 and
  95 %.
- **Budget `thalam-model`:** **₹1,000** a month on the Foundry resource, with alerts at 50, 80 and
  100 %.
- **The router's in-code cap** (Phase 2) is **$10 a month**, about ₹950. It is held in dollars because
  token prices are quoted in dollars, and it stays below the model budget.
- **Claude Haiku is the default hosted model.** Sonnet or Opus is used only where Phase 2's evals show
  Haiku is not good enough, and only inside the cap.

What stays from ADR-0008: the shape (plan, two alarms, brake, ceiling), costing every design first,
pricing every resource on the day, and Kaval's "never without a conversation" list, which is in
Azure terms in CLAUDE.md rule 1.

## Consequences

**Easier:** the alarms fire before the money runs out, and every number is in the currency of the
invoice.

**Harder:**

- **Phase 7 cannot keep anything running all month.** The smallest suitable Arm VM (B2ps v2, $0.0672
  an hour) is about ₹4,700 a month. Phase 7 hosting has to start on demand and park when idle, like
  Kaval's production, or stay on local k3d. The Phase 7 spec decides, with prices checked on the day.
- **Foundry IQ stays on the Free tier.** Serverless is used only if its usage fits what is left.
- **Alerts are not a stop.** Phase 2 adds an automated brake. At the ₹1,425 alert, an action group
  removes the Claude deployment, which can be redeployed free, so a runaway loop cannot keep
  spending while the alert email waits to be read. The router's cap stops it earlier in code.

**Cost:** Phase 0 about ₹0. Phases 1–6 under ₹750 a month planned.

**Revisit if:**

- Roshan's budget changes;
- two months in a row cross alarm 1;
- Phase 7's spec shows that on-demand hosting cannot fit, in which case a raise is argued in a new
  ADR first.
