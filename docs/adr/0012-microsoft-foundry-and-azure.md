# ADR-0012 — Microsoft Foundry and Azure are the platform

- **Status:** Accepted
- **Date:** 2026-11-22
- **Deciders:** Roshan ("Azure all the way", "Claude on Foundry", "own resource group")

## Context

Thalam copied Kaval's platform ([ADR-0002](0002-inherit-kavals-stack-and-conventions.md)). That
meant AWS for hosting in Phase 7, and the Anthropic API directly as the hosted model, with Bedrock
later ([ADR-0006](0006-model-provider-and-routing.md)). On 2026-11-22 nothing on AWS existed yet.
There was no code, no Terraform and no account choice, and the Anthropic key (Task 10, SPEC-001-R13)
had not been created. Changing course cost almost nothing.

Four reasons to move:

1. **Learning.** Kaval already teaches AWS. Thalam can teach the second big cloud. Roshan is
   preparing for Microsoft's AI-103 exam, which is built on Microsoft Foundry, and he already has a
   pay-as-you-go Azure subscription for it.
2. **One cloud, one bill.** Claude runs inside Foundry and is billed on the Azure invoice at
   Anthropic's prices (in Claude Consumption Units, through Azure Marketplace). The model, the
   knowledge layer and the later hosting then sit under one identity, one budget and one cost report.
3. **The knowledge layer exists.** Foundry IQ, formerly Azure AI Search, is part of Microsoft IQ
   (Ignite, 17 Nov 2026). It serves an agent "curated institutional knowledge, including policies
   and authoritative documents". For Thalam that means release policies, runbooks, CAB rules and
   freeze calendars.
4. **Prior art.** The closest open project, Microsoft's Release Manager Assistant
   ([prior art](../prior-art.md)), is a Foundry solution template.

Facts checked on 2026-11-22 against Microsoft's documentation and the Azure retail price API:

- **Claude on Foundry** needs a paid, card-backed pay-as-you-go subscription. Free-trial,
  student and credit-only subscriptions are refused, and the billing country must be one where
  Anthropic sells the offer.
  - The Haiku and Opus families deploy as Global Standard in `westus3` and `eastus2`.
  - Foundry adds no content filter for Claude.
- **Foundry IQ** pricing:
  - Free tier: $0, 3 indexes, 50 MB.
  - Serverless (generally available in December 2026): $0.24 per compute-unit hour and $0.20 per
    GB-month, with free monthly allowances.
  - Basic: $0.101 an hour, about $74 a month.
- **Azure pay-as-you-go has no hard spending limit.** A budget only sends alerts, and cost data can
  lag up to 72 hours. The Anthropic console's monthly limit was a hard stop.
- **The rest of Microsoft IQ** does not fit:
  - Work IQ grounds an agent in Microsoft 365 content, and whether it needs a Microsoft 365 Copilot
    licence or Copilot Credits is unclear.
  - Fabric IQ needs Fabric capacity.
  - Web IQ is web search.

  Thalam's data lives in Jira, ServiceNow, Git and CI, not in any of these.
- **Hosting options:**
  - Azure Container Apps runs `linux/amd64` images only.
  - Azure's Arm (Cobalt) VMs exist. In `eastus2`: B2ps v2 at $0.0672/h, D2ps v6 at $0.0702/h.

## Options

| Option | Good | Bad |
|---|---|---|
| A. Keep the plan: Anthropic API directly, AWS in Phase 7 | same as Kaval; the console's hard monthly limit | two vendors and two bills; no second cloud learned; no managed knowledge layer |
| B. Models only: Claude on Foundry, hosting decided at Phase 7 | smallest change | the budget, identity and knowledge choices are made twice |
| C. **Azure all the way**: Foundry models now, Foundry IQ in Phase 2, Azure hosting in Phase 7 | one cloud and one bill; AI-103 practice; matches the prior art | no hard spending cap; Kaval's AWS Terraform cannot be reused as is; Kaval integration crosses clouds |

## Decision

**Option C.**

1. **Hosted model: Claude on Microsoft Foundry.**
   - ADR-0006's router is unchanged: Ollama runs locally, and the hosted model does chat and
     long-form writing.
   - The code calls it through the Anthropic SDK's Foundry client, which uses the same Messages API.
   - Model IDs are still chosen and priced in Phase 2.
   - If Anthropic's Marketplace offer is refused for the billing country, the fallback is an OpenAI
     model on the same Foundry resource (gpt-4.1-mini), and SPEC-001-R13 is amended again.
2. **Thalam has its own resource group.** It holds one Foundry resource and project, in the same
   subscription as the AI-103 study resources but apart from them, so a budget can see Thalam alone.
3. **Knowledge layer: Foundry IQ, on the Free or Serverless tier only.**
   - It serves policies, runbooks, CAB rules and freeze calendars to the Phase 2 agent.
   - Postgres stays the system of record for the release graph.
   - The Phase 2 spec decides the details.
4. **Hosting: Azure in Phase 7.**
   - The service is chosen then, priced on the day.
   - The candidates are k3s on a Cobalt Arm VM, which keeps Kaval's k3s, Helm and Flux path and its
     `linux/arm64` images, and AKS with an Arm node pool.
   - Container Apps would mean revisiting CLAUDE.md rule 2.
   - Terraform uses the `azurerm` provider, in Kaval's module layout.
5. **Not adopted: Work IQ, Fabric IQ, Web IQ.** They become future scope ([FS-5](../future-scope.md)).
6. **Cost guards start now, in Phase 0,** because the model meter is now on the Azure bill:
   - **Budget `thalam-total`:** $100 a month on Thalam's resource group, with alerts at 70, 85 and 95 %
     ($70 / $85 / $95, [ADR-0008](0008-cost-ceiling.md)).
   - **Budget `thalam-model`:** $20 a month on the model.
   - *Amounts superseded 2026-11-22 by [ADR-0013](0013-cost-ceiling-1500-inr.md): the account bills in INR, so the budgets
     are ₹1,500 (alerts at 70 / 85 / 95 %) and ₹1,000 on the model; the router's cap is $10.*
   - Both budgets exist before the model deployment.
   - The only Phase 0 model call is a free token count.
   - Azure has no hard cap, so the router's in-code monthly cap (Phase 2) is the real brake. A low
     deployment rate limit is set as well, if Foundry offers one for Claude.
7. **Keys:**
   - The Foundry key lives in `.env`, and in Azure Key Vault from Phase 7.
   - Claude Code is denied `az cognitiveservices account keys list`.
   - Phase 2 decides keyless Entra ID with the narrowest role that can call the model.

**What this replaces in earlier ADRs** (each gets an inline note, and keeps its status):
- ADR-0002's platform row.
- ADR-0006's provider order.
- ADR-0008's "AWS" wording. Its brake was already the router.
- [ADR-0011](0011-phase-0-shape.md) decision 3. Budget alerts move back to Phase 0, in Azure. The
  hosting brake (stop staging) comes with hosting in Phase 7.

## Consequences

**Easier:**
- One bill and one identity.
- Budgets scoped to Thalam alone.
- A managed knowledge layer with a free tier.
- AI-103 practice from Phase 0.
- The Messages API and the SDK stay Anthropic's, so ADR-0006 is unchanged in shape.

**Harder:**
- No hard spending cap, and budget alerts arrive late. The in-code cap and the budgets-first order
  have to make up for it.
- A Foundry key reaches the whole data plane of its resource, not only inference, which is wider than
  the Anthropic key was. That is one reason Thalam's resource holds nothing else.
- Kaval's AWS Terraform and its brake Lambda cannot be copied as they are; Phase 7 rewrites them for
  Azure.
- Kaval integration (FS-1) crosses clouds, over MCP and HTTPS.
- More values must stay out of the public repo: resource names (they are the address),
  subscription and tenant IDs, and tenant domains. gitleaks rules cover them.

**Cost:**
- Phase 0: about $0. Idle Foundry resources and Global Standard deployments cost nothing, and a
  token count is free.
- Phase 2: inside the $20 model cap.
- Foundry IQ: $0 on the Free tier. The Basic tier and above (≥ $74 a month) are on the "never
  without a conversation" list.

**Revisit if:**
- Claude on Foundry is refused for the billing country.
- Azure spend crosses alarm 1 two months running.
- Kaval integration needs both projects on one cloud.
- Microsoft adds a hard spending limit to pay-as-you-go.
