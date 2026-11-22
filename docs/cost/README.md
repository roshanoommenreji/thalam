# Cost

What Thalam spends, and where it is watched. The limits are set by
[ADR-0008](../adr/0008-cost-ceiling.md):
- plan $50 a month;
- alarms at $70 and $85;
- brake at $95;
- the hosted model capped at $20.

The meters are on Azure ([ADR-0012](../adr/0012-microsoft-foundry-and-azure.md)). Prices are
checked on the day they are used. The ones below were checked on **2026-11-22**.

## The meters

| Meter | Where it shows | Guard |
|---|---|---|
| Azure resources (Phase 7 hosting, Foundry IQ) | the Azure invoice, Cost analysis on `rg-thalam` | budget `thalam-total`: $100 a month, alerts at 70 / 85 / 95 % |
| Claude tokens (Claude Consumption Units, through Azure Marketplace) | the same invoice | budget `thalam-model`: $20 a month; the router's in-code cap from Phase 2 |
| SaaS tiers | each vendor | none yet: every one is on a free plan |

**Azure pay-as-you-go has no hard spending limit.** A budget only sends alerts, and its data can lag
a day or more. Three things make up for that:
1. the budgets exist before the resource they watch;
2. Phase 0's only model call is a token count;
3. from Phase 2 the router refuses hosted calls past the cap and falls back to the local model
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

Phase 7 parks them when idle, like Kaval, and prices them again on the day.

## Spend so far

| Month | Azure | Claude | Note |
|---|---|---|---|
| 2026-11 | $0 | $0 | nothing deployed yet (Task 10 creates the budgets, then the deployment) |
