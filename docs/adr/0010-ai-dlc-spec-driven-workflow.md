# ADR-0010 — Build Thalam with an AI-DLC, spec-first workflow (hand-rolled)

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan ("use KAV-120 AI-DLC on this project"; option "hand-rolled, in repo" chosen)

## Context

Kaval's epic KAV-120 (FS-9 in Kaval's
[future scope](../../../AWS%20AI/docs/future-scope.md)) plans a measured trial of AI-DLC, AWS's
*AI-Driven Development Life Cycle*: the AI drafts a plan, asks clarifying questions, and builds only
after a person approves, across **Inception → Construction → Operations**. Kaval's own write-up says a
brand-new system is the case that deserves the full workflow ("Petti" is the named pilot).

Thalam is a brand-new system with no code yet, so it can be built spec-first from the first line
rather than retrofitted. Two limits on this ADR: the live Jira ticket was not readable when this was
written (no Atlassian access from the session), so the source is Kaval's FS-9 text; and Kaval's trial
runs on Kaval's own schedule, so nothing here counts as that trial's result.

## Decision

Adopt the AI-DLC shape **by hand, in this repo, with no third-party workflow installed.**

1. **Inception** (before code). For every roadmap phase and every non-trivial story, a one-page spec
   in `docs/specs/` from [the template](../specs/TEMPLATE.md): intent, out of scope, the numbers,
   requirements with IDs, and the test that proves each one. The AI asks its clarifying questions
   first; Roshan answers; **the spec is approved before Construction starts.**
2. **Construction.** Plan → tasks → code → tests. Each test cites the requirement it proves
   (`# covers: SPEC-001-R2`). Existing gates are unchanged: CI green, a person merges, staging before
   prod.
3. **Operations.** What release and post-release work teaches (an incident, a failed check, a cost
   surprise) becomes the next spec or a spec amendment, and a journal line. The spec is kept current
   as the code changes; a stale spec is a defect.

**Size ladder** (from KAV-120):

| Work | Spec |
|---|---|
| Small fix | None. A test and a commit message |
| Normal story | One page, written before the code |
| Roadmap phase / new component | Full spec, kept up to date |
| "Generate code from the spec, edit only the spec" | **No.** The code is what runs and must stay readable |

**Rules that stop it going wrong**

- `CLAUDE.md` wins if a spec or any tool's rules disagree with it.
- A spec is not a test: a requirement with no test is a wish. A check that fails on a requirement
  without a citing test is built in Phase 0 (KAV-120 Stage 2, same pattern as Kaval's
  `test_threat_model.py`).
- **Stop rule** (KAV-120): if a spec takes longer to review than the code it produces, or two stories
  in a row catch nothing the old way would have missed, cut back to what worked and record that in a
  new ADR.
- **Measure per story** in the journal: hours, pages to review, defects found after merge, tokens
  used.
- **Resumable from the repo alone** (KAV-120 Stage 3): a fresh session with no chat history can pick
  up from `CLAUDE.md`, the roadmap, the active spec and the latest journal entry. If it can't, add what
  was missing.

## Amendment 2026-11-18 — superpowers skills drive the stages

The `superpowers` plugin is installed in Claude Code on the laptop (not in this repo). Where it is
available, its skills run the stages above; where it is not, the written workflow still applies and
nothing in the repo depends on the plugin.

| Stage | Superpowers skill |
|---|---|
| Inception: questions → spec → approval | `brainstorming` |
| Plan and tasks | `writing-plans` |
| Construction | `test-driven-development`, then `subagent-driven-development` or `executing-plans` |
| Gates | `verification-before-completion`, `requesting-code-review` |
| Merge | `finishing-a-development-branch` |
| Subagent model choice | `superpowers-plus` (haiku / sonnet / opus by subtask) |

Overrides of the plugin's defaults, so there is one source of truth:

- Specs go to `docs/specs/SPEC-NNN-<slug>.md` in [the template](../specs/TEMPLATE.md), **not**
  `docs/superpowers/specs/`. Plans go to `docs/specs/plans/SPEC-NNN-plan.md`, not
  `docs/superpowers/plans/`.
- Spec approval is recorded in the spec's own "Approved by / date" line.
- Until git exists (a Phase 0 item), specs are saved but not committed.
- If a skill's instruction conflicts with `CLAUDE.md`, `CLAUDE.md` wins.

## Alternatives rejected

- (Clarification: "no third-party workflow" means nothing installed **into the repo**. The
  superpowers plugin lives in the developer's harness and is optional; see the amendment above.)
- **AWS `aidlc-workflows`** (5 phases, 33 stages): sized for teams; installs agents and rules that must
  be read and pinned first. Revisit if the hand-rolled version proves too thin.
- **GitHub Spec Kit:** lighter, but brings its own rules files that can clash with `CLAUDE.md`.
- **Scratch-repo trial of both first** (KAV-120 Stage 0): the right call for Kaval's decision, not
  needed to build a new system sensibly. Not done here.

## Consequences

- Every phase starts with a spec to approve, which adds a small up-front cost; the Definition of Done
  gains a spec line (see CLAUDE.md).
- Spec-driven work is contested (Thoughtworks Radar, Fowler's review). This is a measured bet with an
  exit, not a belief.
- **Revisit if:** the stop rule fires, or Kaval's KAV-120 ADR (its Stage 6) reaches a different
  conclusion, in which case reconcile the two.
