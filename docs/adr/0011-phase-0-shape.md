# ADR-0011 — Phase 0 shape: public repo, two Jira sites, AWS guard moves to Phase 7

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan ([SPEC-001](../specs/SPEC-001-phase-0-foundations.md), open questions 1–3)

## Context

Writing SPEC-001 turned up three facts that changed Phase 0:

1. On GitHub Free, branch protection, rulesets and free CodeQL scanning work only on public
   repositories.
2. Jira Free cannot restrict project access: everyone with product access is effectively a
   project admin. So a bot account on a site can read and change every project there.
3. Thalam spends nothing on AWS before Phase 7. Phases 1–6 run locally, and the hosted model is
   the Anthropic API directly ([ADR-0006](0006-model-provider-and-routing.md)).

## Decision

1. **The repository is public from its first push**, like Kaval. CLAUDE.md already assumes it
   (rule 6, gitleaks). Phase 8's "repo public" becomes a final access review.
2. **Two Jira sites.** Planning (`THL`) lives on the existing site, next to Kaval's, with no bot
   accounts. The sandbox is a separate free site that holds only fixture data and the bots.
   Read-only is enforced by the token's scopes, since Jira Free cannot enforce it by permission.
3. **AWS budget alarms and the hard stop move to the start of Phase 7**, before the first AWS
   resource and together with the account choice (Kaval's or a new one). Until then the only paid
   meter is the Anthropic key, capped at $20 or less a month in its console
   ([ADR-0008](0008-cost-ceiling.md)).
4. **The local folder stays `Release Agent`**; the repository is `thalam`. This replaces
   [ADR-0009](0009-name-and-jira-key.md)'s note that the folder would be renamed at `git init`.

## Alternatives rejected

- A private repo on Free (no enforced protection, no CodeQL), or GitHub Pro (~$4/month, still no
  free CodeQL on private repos).
- One new Jira site for both planning and sandbox, or everything on the existing site: either
  way the bots become admins of the planning board, and in the second case of Kaval's too.
- Building AWS guards now, in Kaval's account (its account-wide budget would count Thalam) or in
  a new account (one more account to secure, months before it holds anything).

## Consequences

Everything in the repo is public from day one, so rule 6 is enforced by gitleaks rules, not by
care alone: real Atlassian site names (with or without `.net`), ServiceNow instance addresses and
Atlassian cloud IDs, on top of gitleaks' default secret rules. Docs and `.env.example` are scanned
too. The pre-publication review proved the point: it found the planning site's name in a `grep`
command in the SPEC-001 plan, written with an escaped dot and no `.net`, which the first rule
missed. History was rewritten before the first push and the rule broadened to catch that form.

Two Jira logins. Cost guarding before Phase 7 depends on the Anthropic console limit.

**Revisit if:** the repo must hold something that cannot be public, or Thalam needs AWS before
Phase 7.
