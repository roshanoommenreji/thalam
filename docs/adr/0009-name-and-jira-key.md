# ADR-0009 — The name is Thalam, the Jira key is THL

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** Roshan (delegated: "give one that you feel like")

## Context

Kaval's siblings are named in Malayalam: *Kaval* (the watch), *Petti* (the box). This project's
job is keeping many independent teams releasing in step.

## Decision

**Thalam** — താളം, *rhythm, the beat*: in Kerala percussion, the *thalam* is the cymbal beat that
keeps a whole ensemble of drummers in time. That is the job: many teams, one beat.

- Jira project key: **THL** (stories `THL-<n>`, branches `type/THL-<n>-slug`)
- Python packages: `thalam_shared`, `thalam_agent`, `thalam_gateway`, …
- Repository: `thalam`; the local folder stays `Release Agent` until git is initialised.
  *Amended 2026-11-18: the folder is not renamed at all ([ADR-0011](0011-phase-0-shape.md)).*

## Consequences

Short, pronounceable, unused in the stack. **Revisit if:** the Jira key is already taken on the
site — then `THLM`.
