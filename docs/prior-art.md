# Prior art — does this already exist?

Checked 2026-11-18. Short answer: **pieces exist; the whole does not, at least not open and
vendor-neutral.** Each vendor covers its own slice, and AI in change management today drafts and
suggests — none of the big ITSM tools auto-approves a change.

## Closest matches

| What | Who | Covers | Gap vs this project |
|---|---|---|---|
| **Release Manager Assistant** (MIT, `github.com/microsoft/release-manager-assistant`) | Microsoft Foundry solution template | Multi-agent chat over Jira and Azure DevOps (via MCP): dependency mapping, release health, timeline forecasting | Azure-bound; read and analyse only — no ServiceNow change, no gated writes, no post-release watch. **Read its code first.** |
| **Now Assist for ITSM / AI agents** | ServiceNow | Change risk assessment answers, change summaries, conflict and quality assessment, outage association; a release-lifecycle documentation agent that writes release notes | Inside ServiceNow only; no cross-team release graph from Git/CI |
| **Rovo agents** | Atlassian | Release notes from Jira, automation flows, Rovo MCP server (GA Feb 2026) | Inside Atlassian only; no change management, no deployment health |
| Plutora, Digital.ai Release, Harness, Octopus | Release orchestration vendors | Release trains, environments, deployment pipelines, some AI features | Commercial, closed; AI is an add-on, not the design |
| Release-notes agents (many: LangSmith Agent Builder template, Agno, Kortix, Claude skills) | Community / vendors | Notes from PRs and issues | One task, no coordination |

## What to borrow

- **Microsoft's assistant**: the router-to-specialist-agents shape, and Jira custom-field handling.
- **ServiceNow**: the vocabulary — change models (standard/normal/emergency), risk assessment,
  conflict detection, blackout and maintenance schedules. The free Personal Developer Instance
  gives a real Change Management API to integrate against.
- **Atlassian Rovo MCP server**: a candidate read path for the agent (writes stay in the executor,
  over REST, with a bot account).
- **Backstage**: `catalog-info.yaml` (`dependsOn`, `providesApis`, `consumesApis`) as the format
  for the component graph — the industry's de facto service catalog.
- **Kaval**: everything about safety, evidence and environments.

## What makes this project different

1. One release graph across teams and tools (Jira + ServiceNow + Git + CI + metrics).
2. The propose-then-approve architecture: the reasoning part cannot write.
3. Post-release verification that closes the loop into the change record.
4. Open, documented, and built to plug into Kaval.
