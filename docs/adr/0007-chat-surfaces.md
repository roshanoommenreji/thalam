# ADR-0007 — Chat surfaces: a web chat and Slack

- **Status:** Accepted 2026-11-18 (option 2, "go with recommended")
- **Date:** 2026-11-18
- **Deciders:** Roshan

## Context

The brief asks for a chat app. Kaval uses Slack only (its phone app was retired, Kaval ADR-0097).
Release managers also need tables, calendars and dependency diagrams, which Slack shows poorly.

## Options

1. **Slack only** — reuse Kaval's Socket Mode bot; no front end to build.
2. **Web chat + Slack** — a small web app streaming from the gateway (Server-Sent Events) for
   rich answers; Slack for approvals and announcements.
3. **Microsoft Teams** — common in large IT companies; same role as Slack.

## Recommendation

**2.** The web chat is where conversations, the calendar and the release graph live; Slack stays
the approval surface, exactly as in Kaval. The front end choice (e.g. a React chat kit, or
LangGraph's open-source agent chat UI) is made at Phase 2 start, after a one-hour spike.

## Decision

Option 2: a web chat app for conversations, tables, the calendar and the release graph; Slack
for approval cards and announcements, reusing Kaval's Socket Mode pattern. The front-end kit is
picked by a one-hour spike at Phase 2 start.

## Consequences

**Easier:** rich answers where they belong; approvals stay where people already are.
**Harder:** a front end to build, secure (login, CSP, escaping) and ship as a fourth image.
**Cost:** none beyond the node it runs on.
**Revisit if:** the company standard is Teams — then the Slack half becomes a Teams bot.
