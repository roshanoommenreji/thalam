# SPEC-002 — Phase 1 the release graph, local

- **Status:** Approved
- **Roadmap phase / Jira:** Phase 1 · THL-2 (the Phase 1 epic); this spec THL-27; one story per plan task
- **Approved by / date:** Roshan, 2026-11-23

> `CLAUDE.md` wins over anything written here. Drafted through `superpowers:brainstorming` on
> 2026-11-23 ([ADR-0010](../adr/0010-ai-dlc-spec-driven-workflow.md)). The decisions below
> (questions 1–6) go into ADR-0015, "Phase 1 shape", written in Construction.

## Intent

A release manager's first question about any release is what has to ship before it. Phase 1 answers
it from data, with no model involved: a fixture company's services, their dependencies and their
releases sit in Postgres, and `make ask Q="before cart-api 2.3"` answers in order, with reasons. Phase
2's chat agent calls the same read-only queries as tools, and Phase 4's dependency check reuses the
same walk.

## Out of scope

- **Ollama and Langfuse** move to Phase 2, their first user. Phase 1's exit gate calls no model, and
  self-hosted Langfuse needs ClickHouse, Redis and object storage (ADR-0004).
- **The other tables** arrive with the phases that use them: `audit_event` in Phase 2, `proposal` →
  `decision` → `execution` → `outcome` in Phase 3, and `check` / `check_result` in Phase 4.
- **The gateway and any image build.** Nothing is built, so rule 2 (arm64) is not touched yet.
- **Any Azure change or model call.** The Foundry deployment stays parked.
- **The sandbox Jira site.** Phase 2 seeds it from the fixture files with Roshan's own token, never
  the bot's.
- **Conflict and freeze checks** (Phase 4). Phase 1 loads the calendar windows but checks nothing
  against them.
- **Backstage API entities (`consumesApis`) and a live Backstage instance.** Phase 1 reads
  `dependsOn` from files.

## Numbers

- **Cost: ₹0.** Local Docker only. Postgres uses about 200 MB of the laptop's RAM (the laptop has
  15.7 GB, and Docker gets about 7.6 GB of it).
- **Volume:** 8 components, 4 teams, about 25 releases, 60 events and 80 Jira issues. A query reads
  the whole graph into memory once, which stays fine into the thousands of components.
- **Latency:** an answer in under a second on the laptop.
- **Data:** fixture data only, with fake names and `xxxx` hosts (CLAUDE.md rule 6). Jira's REST
  responses carry `self` URLs, so the Jira-shaped files use `https://xxxx.atlassian.net`.

## Open questions (the AI asks, Roshan answers)

| # | Question | Answer | Date |
|---|---|---|---|
| 1 | What does SPEC-002 cover? | Lean: Postgres only in compose and the release-graph tables; Ollama and Langfuse move to Phase 2, and the other tables arrive with their phases | 2026-11-23 |
| 2 | How is the gate's question asked? | A read-only query library plus a CLI on the laptop. No gateway, so no image to build | 2026-11-23 |
| 3 | What does "must ship before" mean? | Version-aware. Each release declares the upstream versions it needs; the answer follows them transitively, skips what prod already satisfies, and reports an unmet need as a blocker | 2026-11-23 |
| 4 | Where does the fixture company live? | Files in the repo under `evals/company/`, Jira data in Jira's own REST shape. Phase 2 seeds the sandbox Jira site from them | 2026-11-23 |
| 5 | How does "append-only like Kaval" apply? | The catalog tables mirror the catalog (a component that disappears is retired, never deleted). Releases and their needs are written once, and every state change or re-plan is a new event row | 2026-11-23 |
| 6 | Where does the graph reasoning run? | A pure Python core over one read of the database rows: stdlib `graphlib` for order and cycles, `packaging` for version ranges | 2026-11-23 |
| 7 | The requirement check fails a spec whose "Proved by" path does not exist yet, whatever its status, so this Draft failed it on 17 paths. Change the check, or merge the spec with the code? | Change the check: SPEC-001-R8 is amended so a Draft or Approved spec may name proof files not written yet. The table lists them, their shape is still checked, and from Built a missing file fails as before | 2026-11-23 |

## Requirements

| ID | Requirement | Proved by (test or live check) |
|---|---|---|
| SPEC-002-R1 | `compose.yaml` runs one service, Postgres: the pgvector image pinned by digest, port bound to 127.0.0.1 only, credentials from `.env` that must be set, and nothing built. CI's Postgres uses the same digest | `scripts/dev/test_compose.py`, live: `docs/labs/01-release-graph.md` |
| SPEC-002-R2 | Alembic creates `component`, `dependency`, `release`, `release_need`, `release_event`, `release_item` and `calendar_window`. On real Postgres: upgrade to head, `alembic check` finds no drift from the models, downgrade to base, and upgrade again | `services/shared/tests/test_migrations.py` |
| SPEC-002-R3 | `scripts/ops/db-roles.sql` creates `thalam_loader` and `thalam_reader`. The reader can only SELECT: an INSERT, UPDATE or DELETE as it is refused. The loader can INSERT into `release`, `release_need` and `release_event` but not UPDATE or DELETE them, and can write the mirror tables. Tested by running the real script inside a rolled-back transaction | `services/shared/tests/test_db_roles.py`, live: `docs/labs/01-release-graph.md` |
| SPEC-002-R4 | The catalog loader reads Backstage `catalog-info.yaml` files (kinds Component and Group, several documents a file) with `yaml.safe_load_all`. Names follow Backstage's rules, each `spec.owner` is a Group in the catalog, each `spec.dependsOn` target is a Component in the catalog, and free text is capped (descriptions at 1,000 characters). As a mirror: the same files loaded twice change nothing, a component gone from the catalog gets `retired_at` and is never deleted, and the edge set is replaced | `services/collector/tests/test_catalog.py` |
| SPEC-002-R5 | The release loader reads `evals/company/releases/*.yaml` (strict schema, unknown fields refused): each release's version (`X.Y.Z`), its needs (an upstream component and a range using only `>=`, `>`, `<=`, `<`, `==`, `!=`), and its events. It joins the Jira-shaped `versions.json` and `search.json` (extra fields ignored, summaries capped at 255 characters) for the Jira version id and the release items, and reads freeze and blackout windows from `calendar.yaml` | `services/collector/tests/test_releases.py` |
| SPEC-002-R6 | A load writes nothing, and names the file and field, when: a file does not parse or fails its schema; an owner, `dependsOn` target or need names an unknown component; a release needs its own component; a release is defined twice; a version or range is malformed; a window ends before it starts; an event breaks the life cycle or is dated before the release's previous event; or the database holds an event the files no longer contain | `services/collector/tests/test_load.py` |
| SPEC-002-R7 | Loading the same files twice adds no rows; new events are appended; a release, need or event row, once written, is never changed. A need on a component that the release's component does not list in `dependsOn` loads with a warning | `services/collector/tests/test_load.py` |
| SPEC-002-R8 | `load_graph` reads every table as `thalam_reader` in one transaction and returns the same `Graph` as one built straight from the fixture files | `services/shared/tests/test_graph_read.py` |
| SPEC-002-R9 | `upstream(c)` and `downstream(c)` are transitive over `dependsOn`. `prod_version(c)` is the highest version whose current state is `released`; rolled-back and cancelled releases never count, and a component with none is "not in prod" | `services/shared/tests/test_graph.py` |
| SPEC-002-R10 | `must_ship_before(c, v)`: a need that `prod_version` satisfies is "already satisfied". Otherwise the lowest-versioned in-flight release (current state neither `released`, `rolled_back` nor `cancelled`) that satisfies it becomes a step, and its own needs are followed. A need nothing satisfies, or one on a retired component, is a blocker. Steps come upstream first; a cycle is an error naming every component in the loop | `services/shared/tests/test_graph.py` |
| SPEC-002-R11 | `release_order()` puts every in-flight release after each release it needs, with the same cycle rule | `services/shared/tests/test_graph.py` |
| SPEC-002-R12 | `make ask Q="..."` takes `before <component> <version>`, `upstream <component>`, `downstream <component>` and `order`, connects as `thalam_reader`, and prints only validated fields: names, versions, ranges, states and dates, never free text. Exit 0 when answered, 3 when answered with blockers, 2 for an unknown component or release or bad input, and 1 when Postgres is unreachable, with a message that says `make db-up` and prints no URL or password | `services/shared/tests/test_ask.py` |
| SPEC-002-R13 | `evals/company/` holds 8 components across 4 teams and these scenarios: the gate (`cart-api 2.3.0` needs `pricing-svc 1.8.0` first, and `ledger-svc` is already satisfied by prod's 4.2.0), a two-step chain (`checkout-svc 3.0.0`), a blocker (`web-shop`), a cancelled release, a rolled-back release, and a December freeze window. Every host in it is `xxxx` | `services/collector/tests/test_fixture_company.py` |
| SPEC-002-R14 | The `test` job runs the database tests against a Postgres service container. In CI, a database test that cannot reach Postgres fails rather than skips; locally it skips and says why. pytest runs with `--import-mode=importlib`, so test files in different services may share a name | `services/shared/tests/test_db_guard.py`, `.github/workflows/ci.yml` |
| SPEC-002-R15 | From a clean clone on the laptop, Lab 01 runs `make db-up`, `migrate`, `load` and `ask Q="before cart-api 2.3"`, and records the answer and a refused INSERT as `thalam_reader` | live: `docs/labs/01-release-graph.md` |

**The life cycle (R6).** `planned → scoped → ready → change_approved → deploying → verifying →
released`, one step at a time. `cancelled` can follow `planned`, `scoped`, `ready` or
`change_approved`; `rolled_back` can follow `deploying`, `verifying` or `released`. A release's first
event is `planned` with its window; a re-plan event moves the window. The current state and window are
the latest event of each kind, so Phase 6's DORA metrics (lead time, change failure rate) and the
slippage read come from these rows without a backfill.

**Where the code goes** (the README's repository map already allows it). `services/shared/thalam_shared/`
holds `models.py`, `db.py`, `graph.py` (the pure core: typed objects in, an answer out), `graph_read.py`
(the one read) and `ask.py` (the CLI). `services/collector/thalam_collector/` holds the loaders, run as
`python -m thalam_collector load evals/company`. The fixture sits under `evals/` because Phase 2's 20
golden questions ask about the same company.

## Failure and safety

- **The database enforces the rules.** The reader cannot write, and the loader cannot change history.
  Both are grants, tested on real Postgres (R3), not conventions. This is the groundwork for rule 3:
  Phase 2's agent inherits a role that cannot write.
- **Untrusted text (rule 4).** Catalog descriptions and Jira summaries are written by people Thalam must
  not obey. The loader parses with `safe_load_all` and `json` only, caps the text, and never reads
  meaning from it. The CLI never prints it, so a planted terminal escape cannot reach the shell. Phase
  2 labels the text as data before any model sees it.
- **Fails closed.** A bad file writes nothing and names itself (R6). A dropped edge would make "must
  ship before" silently wrong, which is why an unknown `dependsOn` target fails the load rather than
  being skipped.
- **Secrets (rule 6).** Postgres passwords live in `.env` only, with placeholders in `.env.example`.
  The port listens on 127.0.0.1. No error message prints the database URL.
- **Down or wrong.** Postgres down: `ask` exits 1 and says `make db-up`. A wrong answer is caught by the
  fixture scenarios (R13), which are the tests the queries must pass. **Off switch:** `make db-down`.
- **Observability.** Nothing runs unattended in Phase 1, so there is no alert to add. The loader prints
  its counts and warnings, and tracing arrives with Langfuse in Phase 2.

## Done when

ROADMAP Phase 1 exit gate: "what must ship before `cart-api 2.3`?" answered from the database, no model.
Concretely: R1–R14 green in CI on `main`, with Postgres in the `test` job; Lab 01 run from a clean clone
and its evidence recorded (R15); then this spec set to Built. Docs follow: ADR-0015 (Phase 1 shape);
ROADMAP Phases 1 and 2 (Ollama and Langfuse move; the data-model list split by phase); `overview.md`
(`dependency` loses its version range, `release_need` and `release_event` added) and
`architecture.toml`; the dashboard rebuilt and republished; the journal; `vault/projects/thalam.md`.

## Measured (filled in at the end)

Hours · pages reviewed · defects after merge · tokens used · did the spec catch anything the old way
would have missed? (So far, in Inception: the roadmap's Ollama and Langfuse are not needed by Phase
1's gate, Backstage carries no versions so the range belongs on the release, and the requirement check
fails a Draft spec whose tests do not exist yet.)
