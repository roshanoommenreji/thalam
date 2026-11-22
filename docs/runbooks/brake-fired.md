# Runbook: the brake fired

**When:**
- The e-mail from action group `thalam-brake` arrives (a budget reached its brake line), or
- `make foundry-status` says `parked` when you expected it up.

**What already happened:** the runbook `thalam-brake` deleted every model deployment on Thalam's
Foundry account ([ADR-0014](../adr/0014-azure-cost-guardrails.md)). Nothing is lost: a Global
Standard deployment bills per token, and `make foundry-up` recreates it in about a minute.
`foundry-up` refuses while either budget is at or past its brake line, so the deployment stays down
for the rest of the month unless a decision says otherwise.

The nightly run at 02:00 IST also parks the deployment. That one is routine and sends no e-mail.

## 1. Was it the budget, or the nightly run?

Automation account `thalam-brake` → Jobs. A job started by the webhook, rather than the schedule,
was the budget. Its output lists what it deleted. A `FAIL` line means a deployment may still be up:
run `make foundry-down` and check `make foundry-status`.

## 2. What spent the money?

Cost analysis on `rg-thalam`, this month, grouped by resource and meter.

- **The Claude meter, more than the work explains:** a loop in Thalam, or a leaked key.
  - Regenerate the key in use: the Foundry resource → Keys and Endpoint. Switch `.env` to the other
    key, then regenerate the old one.
  - Look for a loop in the router's logs or traces (Langfuse, from Phase 2).
- **Anything else:** something the policy did not refuse. Run `make azure-sweep`, which names the
  type. Delete the resource, and add its type to the policy's list by an ADR.

## 3. Decide

- **Wait for next month:** the budgets reset on the 1st, and `foundry-up` works again.
- **Raise the ceiling:** only by a new ADR, written before the spend (CLAUDE.md rule 1). Change
  `guardrails.json` and every document `scripts/dev/test_budget_wiring.py` reads, in one commit.

## 4. Record it

A journal entry: the date, which line fired, what spent, the decision. Record a real fire in
ADR-0014's "Revisit if", and as Lab 00 section 5's evidence of the budget link.

## Owner and escalation

Roshan, the only owner. There is nobody to escalate to: the brake exists so that no one has to be
awake when it matters.
