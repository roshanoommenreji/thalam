# Cost

What Thalam spends, and where it is watched. The limits are set by
[ADR-0013](../adr/0013-cost-ceiling-1500-inr.md) in the billing currency, INR, with
[ADR-0008](../adr/0008-cost-ceiling.md)'s shape:
- **at most ₹1,500 a month**, and planned under ₹750;
- alarms at ₹1,050 and ₹1,275;
- brake at ₹1,425;
- the hosted model's budget at ₹1,000, with the router's cap at $10 (about ₹950).

On 2026-11-22, Azure's own price list worked out to about ₹95 to the dollar (AI Search Basic,
$0.101 or ₹9.62 an hour).

The meters are on Azure ([ADR-0012](../adr/0012-microsoft-foundry-and-azure.md)). Prices are
checked on the day they are used. The ones below were checked on **2026-11-22**.

## The meters

| Meter | Where it shows | Guard |
|---|---|---|
| Azure resources (Phase 7 hosting, Foundry IQ) | the Azure invoice, Cost analysis on `rg-thalam` | budget `thalam-total`: ₹1,500 a month, alerts at 70 / 85 / 95 % |
| Claude tokens (Claude Consumption Units, through Azure Marketplace) | the same invoice | budget `thalam-model`: ₹1,000 a month, alerts at 50 / 80 / 100 %; the guardrails below; the router's $10 cap from Phase 2 |
| SaaS tiers | each vendor | none yet: every one is on a free plan |

**Azure pay-as-you-go has no hard spending limit.** A budget only sends alerts, and its data can lag
up to three days. The guardrails make up for that
([ADR-0014](../adr/0014-azure-cost-guardrails.md)). Their numbers live in
`infra/modules/azure-guardrails/guardrails.json`, and a test checks this page quotes them.

| Guardrail | What it does |
|---|---|
| Parked by default | The deployment exists only between `make foundry-up` and `make foundry-down`. An idle Global Standard deployment costs nothing, so parking loses nothing |
| Rate cap | Capacity 1: 1 request and 1,000 tokens a minute |
| Azure Policy on `rg-thalam` | Claude Haiku 5.5 on Global Standard only, at a cap of 3; East US 2 only; AI Search Free only; no VMs, AKS, NAT, gateways, Front Door or managed databases |
| The brake | At ₹1,425 total (95 %) or ₹1,000 on the model (100 %), an action group runs a runbook that deletes the deployment. It also runs every night at 02:00 IST |
| `make azure-sweep` | Read-only; fails on anything billable left behind |

**The worst case, worked out.** Each capacity unit allows 1,000 tokens a minute. Count all of them
as input ($0.10 per million) **and** as output ($0.50 per million), all day:
- 1,000 × 1,440 × $0.60 per million = $0.864, about **₹82 a unit a day**;
- at the cap of 3, about **₹246 a day**;
- over three days of budget lag, about ₹738, which still fits inside the ₹750 between the plan
  and the ceiling.

At Azure's default of 10 units, the same worst case is about ₹820 a day.

**What the guardrails cost:** about ₹0 a month.
- Azure Policy, budgets and roles are free.
- Action-group e-mail and webhooks are within their free grant (secure webhooks are ₹0 for the
  first tier, then ₹0.0057 per 10).
- Automation's first 500 job-minutes a month are free, then ₹0.1905 a minute. About 31 short
  runbook runs a month use a few of them.

From Phase 2 the router also refuses hosted calls past its cap and falls back to the local model
(ADR-0006).

## Prices checked on 2026-11-22

**Claude on Microsoft Foundry.** Anthropic's prices, per million tokens, Global Standard deployment.
US Data Zone Standard costs 1.1 times as much.

| Model | Input | Output |
|---|---|---|
| Claude Haiku 5.5 | $0.10 (prompts up to 100,000 tokens) | $0.50 |
| Claude Sonnet 5.5 | $2 | $10 |
| Claude Opus 5.5 | $4 | $20 |

**Foundry IQ (Azure AI Search)**, `eastus2`, from the Azure retail price API:

| Tier | Price | Note |
|---|---|---|
| Free | $0 | 3 indexes, 50 MB; Thalam's default |
| Serverless | $0.24 per compute-unit hour, $0.20 per GB a month | generally available December 2026, with free monthly allowances |
| Agentic retrieval | free allowance per month, then about $0.022 per million tokens | |
| Basic | $0.101 an hour, about $74 a month | on the "never without a conversation" list |

**Arm VMs for Phase 7**, `eastus2`, Linux, pay-as-you-go. Running all month means about 730 hours.

| Size | Per hour | All month |
|---|---|---|
| B2ps v2 | $0.0672 | about $49 |
| D2ps v6 | $0.0702 | about $51 |

At about ₹4,700 a month, neither fits under ₹1,500 if left running. Phase 7 starts them on demand
and parks them when idle, like Kaval, or stays on local k3d. Its prices are checked again on the
day (ADR-0013).

## Spend so far

| Month | Azure | Claude | Note |
|---|---|---|---|
| 2026-11 | $0 | $0 | nothing deployed yet (Task 10 creates the budgets, then the deployment) |
