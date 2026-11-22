# ADR-0014 — Azure cost guardrails come before the Claude deployment

- **Status:** Accepted (Roshan approved SPEC-001-R14–R20 as written, 2026-11-22)
- **Date:** 2026-11-22
- **Deciders:** Roshan ("can we control it like how we did in kaval project, like delete or pause
  resource when not in use, add guardrails"; chose "Everything, brake included")
- **Story:** THL-24 · builds on [ADR-0012](0012-microsoft-foundry-and-azure.md) and
  [ADR-0013](0013-cost-ceiling-1500-inr.md) · copies Kaval's ADR-0029 (park when idle), ADR-0064
  (a tested brake, proven live) and ADR-0067 (a sweep as the exit gate)

## Context

Task 10 step D creates Thalam's first thing that can spend money: a Claude Haiku 5.5 deployment on
Microsoft Foundry. Until now, the only guard planned for it was two budgets
([ADR-0013](0013-cost-ceiling-1500-inr.md)), with an automated brake left for Phase 2. Facts checked
on 2026-11-22:

- **Budgets only alert, and late.** Pay-as-you-go has no spending limit. Cost data can lag up to
  72 hours ([ADR-0012](0012-microsoft-foundry-and-azure.md)), so an alert can arrive days after the
  spend that caused it.
- **An idle deployment costs nothing.** Global Standard bills per token, so deleting the deployment
  and creating it again loses nothing but a minute.
- **The deployment's capacity is its rate limit.** Azure's model catalogue, read for East US 2, gives
  Claude Haiku 5.5 on Global Standard a default capacity of 10 units. Each unit allows **1 request and
  1,000 tokens a minute**. The subscription's default pay-as-you-go quota for the model is 40 requests,
  40,000 input tokens and 8,000 output tokens a minute.
- **The price** is $0.10 per million input tokens and $0.50 per million output tokens, for prompts up
  to 100,000 tokens. Foundry bills through Azure Marketplace at Anthropic's rates.
- **Azure Policy can see every field that matters.** The aliases
  `Microsoft.CognitiveServices/accounts/deployments/model.name`, `…/sku.name` and `…/sku.capacity`
  exist, so a deny rule can refuse the wrong model, the wrong deployment type or too much capacity.
- **Microsoft's documented brake** is budget → action group → runbook. An action group can start an
  Azure Automation runbook directly. Automation's first 500 job-minutes a month are free (then about
  ₹0.19 a minute), and secure-webhook notifications are free at this volume.
- **Marketplace usage is included in Cost Management on a Microsoft Customer Agreement.** Whether a
  Claude charge is attributed to Thalam's resource group, which both budgets need, has to be seen on a
  real charge.

**What a runaway costs.** Take the worst case: a loop, or someone with a leaked key, uses every unit
of capacity all day, and the output limit is as large as the token limit:

| | Per capacity unit per day | At the cap below (3 units) |
|---|---|---|
| Input: 1,000 tokens × 1,440 minutes × $0.10 per million | $0.144 | |
| Output: 1,000 tokens × 1,440 minutes × $0.50 per million | $0.720 | |
| **Total** | **$0.864, about ₹82** | **about ₹246 a day** |

If output is limited to a fifth of input, as the subscription quota suggests, the total is about ₹27 a
unit. At the default capacity of 10 units the worst case is about ₹820 a day. Three days of that,
before a lagging alert arrives, would pass the whole ₹1,500 ceiling.

## Decision

Six guardrails, all built and proven before the first deployment (moved forward from ADR-0013's
Phase 2):

1. **Parked by default.** `make foundry-up` creates the one deployment and `make foundry-down` deletes
   it. Both are safe to repeat. The deployment is not in Terraform: the brake deletes it, and a
   deployment Terraform did not create cannot drift. `foundry-up` refuses unless the guardrails check
   passes: the policy is assigned, both budgets exist with the agreed amounts, the brake is wired, and
   neither budget has reached its brake line this month. That last check stops a restart after the
   brake has fired, the gap Kaval's ADR-0064 recorded and left open.
2. **A rate cap.** The deployment runs at **capacity 1** (1 request and 1,000 tokens a minute), the
   smallest the catalogue offers, which is enough for Phase 0's token count. Phase 2 may raise it, up
   to the policy cap, in the change that needs it.
3. **Azure Policy on Thalam's resource group**, one assignment of one initiative:
   - every resource in **East US 2** (and `global`, for the action group);
   - a model deployment must be **Claude Haiku 5.5**, **Global Standard**, at **capacity 3 or less**;
   - Foundry accounts of kind `AIServices` only;
   - AI Search on the **Free** tier only;
   - **not allowed:** virtual machines and scale sets, AKS, NAT gateways, application gateways, Front
     Door and CDN profiles, managed PostgreSQL and SQL. Phase 7 lifts these only by an ADR.

   The cap of 3 is where a three-day runaway, about ₹738, still fits inside the ₹750 between the
   planning target and the ceiling.
4. **The brake.** A Python runbook in an Automation account deletes every model deployment on Thalam's
   Foundry resource. Three things start it:
   - the action group `thalam-brake` when `thalam-total` reaches **95 % (₹1,425)**;
   - the same action group when `thalam-model` reaches **100 % (₹1,000)**;
   - **a schedule every night at 02:00 IST**. A deployment left up is parked overnight, and the brake's
     whole path runs every day, not only on the day it is needed (Kaval's lesson: a brake never seen
     running had a broken step).

   The runbook's managed identity has one custom role: read the account, and read and delete its
   deployments. Azure can make a custom role assignable at a resource group but not at one
   resource, so the role is defined on Thalam's group and **assigned on the Foundry resource only**.
   The identity cannot create anything, read keys, or touch any other resource. The runbook uses the Python standard library only, takes a dry-run switch, treats "already
   gone" as success, tries every deletion even if one fails, and fails the job at the end if any did.
5. **`make azure-sweep`**, read-only, the exit gate after every session (Kaval's `lab-sweep`). It fails
   if:
   - a model deployment exists while it should be parked;
   - a resource in the group is of a type not on its list;
   - a resource tagged `project=thalam` sits outside the group;
   - the policy, a budget or the brake is missing.
6. **A test that the numbers agree** (Kaval's `test_budget_wiring.py`). The ceiling, both budgets and
   their thresholds, the capacity cap, the deployment's capacity and the model must say the same thing
   in ADR-0013, this ADR, CLAUDE.md, `docs/cost/`, the Terraform, the policy files and the scripts. The
   runaway arithmetic above (cap × ₹82 × 3 days ≤ ₹750) is checked too.

**And for the agent itself:** `.claude/settings.json` denies Claude Code deleting the policy
assignment, creating a policy exemption, deleting a budget or the action group, running
`terraform destroy`, and listing Foundry keys. Roshan can still do all of these himself.

**How it is built:** Terraform (`azurerm`, Kaval's layout: `infra/modules/azure-guardrails/`, root in
`infra/envs/azure/`) holds the resource group, both budgets, the policy, the Foundry resource and
project, the Automation account, the runbook and its schedule, the role and the action group. State
stays on the laptop and is gitignored.

Three values reach Terraform as environment variables only, through `scripts/ops/tf.py`:
- the subscription, from `az account show`;
- the Foundry name and the alert e-mail, read from `.env` as data, never run as shell.

Both names are marked sensitive, so a plan hides them. Rule 6 holds: no subscription ID or resource
address in git. Every number lives once, in `infra/modules/azure-guardrails/guardrails.json`. Every
resource is tagged `project=thalam`.

**One live proof the budgets need:** after the first real deployment, Lab 00 makes one paid call of a
few tokens (well under ₹0.01). Within 72 hours its meter must show under Thalam's resource group in
Cost Management. If it doesn't, the budgets see nothing, and they move to the subscription scope with a
filter, by a SPEC amendment.

## Alternatives rejected

- **Budgets alone (the plan before this ADR):** they alert, they don't stop, and they alert late.
- **Budget → Logic App → runbook** (Microsoft's tutorial): one more component, billed per action. An
  action group starts a runbook itself.
- **An Azure Function as the brake:** a second runtime to deploy, secure and pay for. Automation is
  free at this volume.
- **A spending limit:** pay-as-you-go does not offer one.
- **An allowed-types list in Policy instead of a deny list:** stricter, but Foundry and Automation
  create child resource types that would be refused on day one, and a wrong guess blocks the lab. The
  sweep checks the allowed list read-only instead. Revisit once the real list is known.
- **Waiting for the router's in-code cap (Phase 2):** it does not exist yet, and it would not stop a
  leaked key used outside Thalam.
- **Terraform owning the deployment (`apply` to bring it up):** the brake deletes it outside Terraform,
  so the next `apply` would quietly put it back.
- **Regenerating the key as the brake:** it stops a leaked key, but not a loop inside Thalam using the
  current key. Deleting the deployment stops both.

## Consequences

- **The worst case is bounded by the design, not by an alert.** A day at the cap costs at most about
  ₹246. A runaway lasts at most until 02:00 IST, unless someone runs `foundry-up` again, which refuses
  past the brake line.
- **The brake is a backstop:** it fires on lagging data. The rate cap and nightly parking do most of the
  work.
- **Phase 2 has to start each working session with `make foundry-up`** (about a minute) and may need
  more than 3 units of capacity for chat. Raising the cap needs this ADR's arithmetic redone and the
  numbers test updated in the same change.
- **The Automation webhook expires** (Azure requires a date). It is set to one year and goes in the Lab
  00 credentials table, with a rotate-by date two weeks before.
- **Cost of the guardrails:** about ₹0 a month. Policy, budgets and roles are free; action-group e-mail
  and webhooks are within the free grant; about 31 runbook runs a month use a few of the 500 free
  minutes.
- [ADR-0013](0013-cost-ceiling-1500-inr.md)'s "Phase 2 adds an automated brake" now happens in Phase 0;
  that line carries an inline note.

## Revisit if

- the Claude meter does not show under the resource group (the budgets' scope changes);
- Phase 2 needs more than 3 units (redo the arithmetic, new numbers);
- the brake fires, or the nightly run fails twice in a row;
- Phase 7 adds hosting, which needs its own park-and-brake (ADR-0013).
