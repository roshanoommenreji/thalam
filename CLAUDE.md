# CLAUDE.md

Guidance for Claude Code working in the **Thalam** repository (താളം, *the beat*; Jira key
`THL`, [ADR-0009](docs/adr/0009-name-and-jira-key.md)).

## What this project is

A release-coordination agent for a large IT organisation where many teams release independently
but depend on each other functionally. With AI-assisted development the number of releases has
gone up sharply; coordinating them by spreadsheet, CAB meeting and memory no longer scales.

The agent keeps one central picture of every release in flight and:

- runs **pre-release readiness checks** (CI, tests, scans, Jira scope, upstream dependencies,
  change approval, freeze windows, rollback plan);
- **creates the Jira release** (fixVersion) and the **ServiceNow change request**;
- drafts and maintains **release notes** and the **release calendar**;
- **watches each release after it goes out** and proposes a rollback when health degrades;
- is also a **chat app**: "what is going out on Thursday?", "is payments-api safe to release
  before ledger-svc?", "draft the CAB summary for this week".

It is the sibling of **Kaval** (`..\AWS AI`), an ops agent with human-in-the-loop approval. The
stack, the safety architecture, the environments and the documentation discipline are **copied
from Kaval on purpose**. Where this project departs from Kaval, an ADR says why
([ADR-0002](docs/adr/0002-inherit-kavals-stack-and-conventions.md)). Integration with Kaval is
planned ([future scope, FS-1](docs/future-scope.md#fs-1--kaval-integration)).

This is a **learning project built to be documented**. Roshan is a Release Manager moving toward
an AI platform role. Two consequences that override normal defaults:

- **Explain, don't just do.** When you make a non-obvious choice, say why. The reasoning is the
  product as much as the code is.
- **Every session produces documentation.** See "Definition of Done". The docs become a course.

---

## Non-negotiable constraints

### 1. Cost: plan for $50, alarms at $70 / $85, brake at $95

Set by [ADR-0008](docs/adr/0008-cost-ceiling.md). Covers AWS, model tokens and any SaaS tier;
the hosted model has its own $20 cap enforced by the router. Going above $100 needs a new ADR.
Before proposing *any* paid resource, state its monthly cost and verify the price on the day. Kaval's "never without a conversation" list applies unchanged:
NAT Gateway, ALB, persistent EKS, RDS, GPU instances, always-on staging.

### 2. Images must be `linux/arm64`

Same Graviton target as Kaval. Always `docker buildx build --platform linux/arm64`.

### 3. The agent never gets write access

This is the architecture, not a preference — exactly Kaval's split:

- `agent` — reasoning (LangGraph). **Read-only** credentials to Jira, ServiceNow, Git, CI and
  metrics. Its only output is a row in `proposals` (and chat replies).
- `executor` — the only component that writes to Jira, ServiceNow, the calendar, Confluence or
  Slack announcements. Scoped service accounts. Acts solely on proposals that passed policy and,
  where required, human approval.

LangGraph's `interrupt()` pauses a graph while a person decides; it is **not** the thing that
acts. The graph files a proposal, pauses, and resumes on the executor's recorded outcome.
If a change would let `agent` call a write API (including a write tool of an MCP server), the
change is wrong. Say so rather than implementing it.

### 4. Untrusted text is data, never instructions

Jira descriptions, commit messages, PR bodies, change notes and chat input are written by people
the model must not obey. Every such text is flattened, capped and labelled as data before the
model reads it (Kaval ADR-0083), and every model output is schema-validated and escaped before it
reaches Slack, Jira, ServiceNow or HTML (Kaval ADR-0082). See
[ADR-0005](docs/adr/0005-layered-guardrails.md).

### 5. Nothing reaches prod without passing staging

`local` → `staging` → `prod`. Build once, promote the signed artifact by digest. Environments
differ only by a Helm values file and a pinned digest (Kaval ADR-0004, 0032, 0081, 0092).

### 6. Secrets never enter git

Plan for the repo being public. No real instance URLs, tenant IDs, account IDs or tokens in any
committed file. `.env.example` carries placeholders only. gitleaks runs pre-commit.

---

## Conventions (inherited from Kaval)

**Python** — 3.11, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, `uv` + `uv.lock`, `ruff` +
`mypy --strict`, `pytest`. Every LLM output is validated against a Pydantic schema before it
touches the database.

**Agent framework** — LangGraph 1.x for every multi-step flow, LangChain only for model and tool
adapters; Postgres checkpointer, never the in-memory one outside tests
([ADR-0003](docs/adr/0003-langgraph-for-orchestration.md)).

**LLM observability** — OpenTelemetry GenAI conventions in code; traces to Langfuse
([ADR-0004](docs/adr/0004-llm-observability-otel-and-langfuse.md)).

**Policy** — OPA/Rego in `policy/`, every action classed `auto` / `ask` / `never`; everything
starts `ask` (Kaval ADR-0017).

**Terraform / Helm / GitOps / CI supply chain** — exactly as Kaval: modules in `infra/modules/`,
one umbrella chart, Flux, signed images, SBOM, promotion by digest.

**Commits and branches** — conventional commits with the Jira key; short-lived
`type/THL-<n>-slug` branches; PR-only merges once CI is green.

**Where things go** — the README's repository map is authoritative; the top level holds only
files a tool requires there.

---

## Development workflow: AI-DLC, spec first

Set by [ADR-0010](docs/adr/0010-ai-dlc-spec-driven-workflow.md), from Kaval's KAV-120. Hand-rolled;
no third-party workflow tool is installed.

1. **Inception** — before code for a roadmap phase or non-trivial story, ask clarifying questions,
   then draft `docs/specs/SPEC-NNN-<slug>.md` from [the template](docs/specs/TEMPLATE.md). Wait for
   Roshan's approval; do not start Construction on a Draft spec.
2. **Construction** — plan, tasks, code, tests. Each test names the requirement it proves
   (`# covers: SPEC-001-R2`); a requirement with no test is a wish.
3. **Operations** — what a release or incident teaches goes into a spec amendment or the next spec.
   Keep the active spec current as the code changes.

**With the superpowers plugin** (when installed): Inception runs through `superpowers:brainstorming`,
the plan through `superpowers:writing-plans`, Construction through `test-driven-development` and
`subagent-driven-development` / `executing-plans`, gates through `verification-before-completion`.
Override its paths: specs go to `docs/specs/SPEC-NNN-<slug>.md` (template), plans to
`docs/specs/plans/SPEC-NNN-plan.md`, never `docs/superpowers/`. Without the plugin, follow the steps
above by hand; nothing in the repo depends on it.

Small fixes need no spec. Never generate code from a spec and then edit only the spec. If a spec takes
longer to review than the code, shrink it (stop rule in the ADR). Record hours, pages reviewed, defects
and tokens per story in the journal. A fresh session should be able to resume from this file,
`ROADMAP.md`, the active spec and the latest journal entry alone.

---

## Definition of Done

Same ten items as Kaval's CLAUDE.md, adapted, plus a spec step:

0. Spec approved before building and amended to match what was built (non-trivial work)
1. Code merged, CI green (including the eval and injection gates once they exist)
2. Lab doc in `docs/labs/` — a stranger could reproduce it from zero
3. ADR in `docs/adr/` if a decision was made
4. Entry appended to `docs/journal/YYYY-MM-DD.md`
5. Cost impact noted in `docs/cost/` if spend changed (including model tokens)
6. `docs/architecture/overview.md` updated if a component was added, removed or rewired
7. Deployed to `staging` and verified before `prod`
8. Jira reflects reality
9. Generated mirrors (dashboard, Confluence) regenerated if their sources changed
10. Documentation sweep, unasked, when a fact changes

---

## Planning standard

Copied from Kaval. For anything non-trivial, write down before building:
1. What real companies do (2–3 patterns, then a recommendation)
2. The whole path: local → staging → prod
3. Security: least privilege, secrets, what an attacker or a confused model could do
4. Failure: what happens when it is down or wrong, how it is noticed, how it is turned off
5. Observability: metrics, logs, traces, an alert on the feature itself
6. Cost and capacity, stated first
7. Testing: unit, real dependency, live proof, and the negative case
8. People and process: runbook, ownership, expiry and escalation for anything waiting on a human

---

## Working style here

- Phases are sequential and gated — check `ROADMAP.md` before suggesting later-phase work.
- When something is uncertain (a price, an API shape, a library version), **verify it**.
- Plain-language recap at every story and phase boundary, unprompted.
- Kaval is read for patterns, never edited from this repo.
