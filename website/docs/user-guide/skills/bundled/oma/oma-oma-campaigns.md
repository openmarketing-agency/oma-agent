---
title: "Oma Campaigns — Install and inspect local OMA campaigns"
sidebar_label: "Oma Campaigns"
description: "Install and inspect local OMA campaigns"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Oma Campaigns

Install and inspect local OMA campaigns.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/oma/oma-campaigns` |
| Version | `0.3.1` |
| Author | Open Marketing Agency (OMA) |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `oma`, `campaigns`, `provisioning`, `profiles` |
| Related skills | [`hermes-agent`](../../bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# OMA Campaigns Skill

Use this skill in the default OMA Agent profile to design and provision campaigns from the saved brand and playbook. Each campaign has one orchestrator to plan and assign work on its Kanban board and a separate publishing agent to apply authorized content or edits. The templates below are drafting references; the installer reads only the saved campaign and agent records.

## When to Use

- The user asks to create or provision a campaign, inspect an installed one, or save its goals or plans.

## Prerequisites

Resolve the default Hermes home with `hermes -p default config path`. Read `oma/brand/config.yaml` and `oma/playbook/config.yaml` from that home before designing a team. For agent record formats load `oma-agents` with `skill_view`; when drafting a roster, load its `references/base-agent-template.md` for the config and persona examples. `oma-bundle/skills/` supplies reusable skills only; find them with `search_skills` and read relevant ones with `skill_view`. Do not use the onboarding URL as a source of executable definitions.

## How to Run

Use `terminal` to run `scripts/campaign.py` from the installed skill directory (`skills/oma/oma-campaigns/` under the default Hermes home, as reported by `skill_view`). Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces and stay in the default profile. If an older customized copy lacks the current launcher, use the current bundled launcher rather than modifying the custom copy.

| Arguments | What they do |
|---|---|
| `install <id>` | Provision the saved campaign and agent records, create the board, and install declared shared skills. |
| `list` | List installed or incomplete campaigns. |
| `status <id>` | Show the saved roster, provisioning state, and profiles verified against the campaign board. |
| `configure <id>` | Fill missing routing fields in the existing campaign config from the verified board and profiles. Does not reprovision agents or create a board. |
| `integrations` | List candidate integration IDs from observed brand integrations and verified social channels. Does not check account access. |
| `validate <kind> <path>` | Check a `brand`, `playbook`, `campaign`, or `agent` YAML record without applying it. |

## Campaign Templates

When drafting a new campaign, load the closest reference with `skill_view(name="oma-campaigns", file_path="references/...")`:

| Campaign | Use when the playbook prioritizes |
|---|---|
| [Website build](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/website-build-template.md) | Creating the client's missing official site and primary conversion path. |
| [Blog build](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/blog-build-template.md) | Creating a missing blog and publishing its first useful articles. |
| [Public docs build](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/docs-build-template.md) | Creating a missing public docs destination and first tested quickstart. |
| [Docs](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/docs-template.md) | Improving documentation on an existing publishing destination. |
| [SEO](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/seo-template.md) | Growing qualified organic discovery and conversions. |
| [Social media](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/social-media-template.md) | Reaching an audience and responding on verified social channels. |
| [Product launch](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/product-launch-template.md) | Driving adoption around a dated product or feature release. |

Adapt the example IDs, integrations, goals, ordered plans, roster, and review cadence to the saved brand and playbook. Do not install examples verbatim, create one campaign per template, or overwrite an existing campaign to match one. If none fits, draft from the campaign config rules below.

### Build missing owned channels

When brand research confirms a website, blog, or public docs are absent and the playbook calls for one, draft the corresponding build campaign instead of assuming there is already a destination. Treat unchecked channels as unknown. Reuse fitting campaigns and shared hosting; if a blog or docs depends on the new site, put the hosting dependency first rather than repeating it.

Keep content and publication with the campaign team. For hosting or app setup, load `references/maintenance-handoff.md` from `oma-agents`: the campaign orchestrator defines the dependency, `default` routes the authorized request to the installed `maintenance` profile on the operations board, and `maintenance` uses `omactl`. Do not add `maintenance` to the campaign roster, install `omactl` on campaign agents, or treat campaign setup as permission to make infrastructure changes. Verify separate CMS access before enabling work that requires it.

## Campaign Config

Save the editable config at `oma/campaigns/<campaign_id>/config.yaml`. Use the campaign ID as the directory name.

- **Playbook — overall strategy:** `oma/playbook/config.yaml` defines what marketing should focus on and why across all campaigns. Use its priorities to decide which campaigns are needed, not as a list of tasks.
- **Campaign `goals` — purpose and outcomes:** Say why this campaign exists, what should change, and how to recognize success when measurable. Publishing a blog post is an action, not the outcome it serves.
- **Campaign `plans` — approach and sequence:** Say how the campaign will reach its goals: what to create, publish, or edit, on which channels, what must happen first, and how results will inform the next steps. Keep the campaign-level sequence here and let the orchestrator break it into Kanban tasks.

Goals and plans are inline YAML lists of text. Do not add a `playbook` field or rewrite older records just to remove it. Do not add `version` to campaign or agent records. The helper stores `installation_state` in the campaign config; do not set it by hand.

Use exactly one orchestrator, `<campaign_id>__orchestrator`, in the ordered `agents` list. Use canonical `<campaign_id>__<agent_id>` IDs unchanged and without duplicates. Before provisioning, the list is the proposed roster; after provisioning verify it against `present_profiles`. The helper fills missing `kanban_board` and `kanban_board_name`. Use the board slug in commands. Editing a record does not reconfigure an installed board or profile.

## Campaign Integrations

- Every campaign must declare a non-empty `integrations` list in its `config.yaml`. Use unique canonical OMA catalog IDs, not display names, URLs, or connector aliases. Select the smallest set that the campaign needs for its plans and measurement; don't copy the brand's entire inventory. If no catalog integration fits, leave the campaign unprovisioned and report the gap rather than adding an unrelated integration.
- Use the platforms the user named or that the saved brand and playbook clearly support. Ask which platforms to use only if the choice is still unclear. The launcher's `integrations` command shortlists candidates from brand evidence; consult the full OMA catalog for other choices. Prefer suitable existing connections and include media generation only if the plan needs it.
- **Save first, then ask the user to connect.** Write the selected catalog IDs to `integrations: [...]` in `oma/campaigns/<campaign_id>/config.yaml` even if the accounts are not connected yet. Then direct the user to the campaign's integration setup in the OMA console for the missing accounts, following the [integration intake guide](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/integration-intake.md). Never ask the user to paste MCP configuration, server URLs, headers, API keys, or tokens into chat. Do not put those values in campaign or agent records or configure MCP servers manually as a workaround.
- **Do not start without verified integrations.** A saved ID or a public account link does not prove access. Until each required integration is connected and the intended account and the owning profile's required permissions have been verified, keep the campaign as a draft or provision it paused. Do not start or resume it, dispatch campaign work, or register or enable its jobs. Tell the user which accounts still need connecting. This is a skill check, not a gate enforced by the YAML validator or lifecycle command.

## Publishing Agent

- Include `<campaign_id>__publisher` in every new campaign roster, with its own `config.yaml` and `SOUL.md`. The publisher owns applying authorized changes to the campaign's destination: publishing new content, editing existing content, or applying a prepared change such as a website, CMS, or documentation edit. Assign research, drafting, and review separately as needed; the orchestrator decides the handoffs on Kanban.
- Give the publisher only the tools and authorized destinations it needs. Before publishing or editing, verify the destination and the exact version or change to apply, and satisfy any required review. Read it back afterward and record the resulting URL, revision, or other confirmation on the task. If access, authorization, or a required review is missing, leave the work unpublished and report the blocker. A publishing role does not itself authorize a live change or require a cron job.
- If an installed campaign lacks a verified publishing agent, report the gap. Do not append a draft to its installed roster, assign publishing to another role as a workaround, or rerun `install` to try to extend the team.

## Schedule the Orchestrator

- Give every campaign a recurring review owned by `<campaign_id>__orchestrator`. Declare it in that agent's `jobs` list with a stable ID such as `campaign-review`, a native Hermes `schedule`, and a bounded `prompt`. Use the user's cadence when specified. Otherwise, choose the slowest cadence that meets the campaign's response needs, given data freshness, rate limits, and run cost. Reuse an existing equivalent job and preserve operator pauses.
- Name the checks in the saved `prompt` itself. For Social & Community, tell the orchestrator to read new comments and replies on the brand's posts, @mentions and tagged posts, and any relevant community threads. Include inbox messages only where the campaign covers them and read access is authorized. Name the verified channels/accounts and their available read tools; verifying access or reading engagement totals is not a substitute for checking activity. For other campaigns, use their own signals (e.g. search performance for SEO).
- Each review checks the saved goals and plans, the campaign's Kanban board, and new evidence since the last review. Decide what to continue, change, or queue; propose changes outside the orchestrator's authority and route authorized publication or edits to the publisher. Record material decisions and stop without creating duplicate tasks or rewriting plans when nothing meaningful changed. When data or access is missing, note the gap rather than inventing a trend.

## Procedure

1. **Derive campaigns from the strategy.** Read the singleton playbook's priorities and recommendations alongside the compiled brand. Choose the smallest set of campaigns that advances those priorities, considering channel fit, existing work, prerequisites, and verified capabilities. For each, identify the strategic priority it serves, write a distinct outcome in `goals`, and put the actions and their order in `plans`. Include the orchestrator and publisher, then add only specialists with distinct responsibilities and handoffs. Use `list` and `status` first on a rerun; reuse installed teams and preserve edits, notes, and manual pauses rather than creating duplicates.
2. **Save the campaign and agent records.** Select and save the required `integrations` as described above. Use `write_file` or `patch` for the campaign config and each `oma/agents/<agent-id>/config.yaml` and `SOUL.md`. Record canonical `id`, `name`, `description`, and `campaign_id` for each role; use the same ID for the future profile. Give the orchestrator responsibility for deciding Kanban tasks and handoffs rather than hardcoding a pipeline. Choose only needed toolsets and existing shared skills; use `oma_skills` for exact package IDs to install, or `[]` for none. Keep `saves/` and link each persona to its own absolute saves path. Never copy credentials or grant authority inferred from a website.
3. **Declare the orchestrator review and any other recurring work.** Follow the review guidance above. Assign each other genuine recurring obligation to exactly one role. A specialist can own an independent check it can actually perform; do not schedule it to duplicate the orchestrator's review. Leave one-off work, handoffs, and event-driven work on Kanban. Save `jobs: []` for unscheduled specialists. For each job use a stable `id`, a native Hermes `schedule`, and a bounded `prompt` with clear stop conditions; add `timezone` or positive `repeat` only when needed. Do not add per-job skills, scripts, or remote delivery.
4. **Provision and verify.** For a new campaign, use `read_file` to verify that every ID in `agents` has a nonempty, role-specific `oma/agents/<agent-id>/SOUL.md` beside its `config.yaml`, with the correct saves path. YAML validation alone doesn't check the persona. If a write was blocked or a file is missing, report the affected role and leave the campaign a draft. Do not bypass the block or substitute `default`'s SOUL. Once the records are complete, run `install <id>`. Before enabling jobs, check that `status <id>` reports `installed`, the expected orchestrator and board, and a complete `present_profiles` list; resolve each profile's home via `hermes -p <agent-id> config path` and verify its adjacent `SOUL.md`. The helper wires the same board into the team without switching the shared current board. It does not start turns, copy launch credentials, create jobs, or seed tasks. Use `configure <id>` to fill missing routing fields in the existing config without reinstalling.
5. **Hand off missing connections before starting work.** After saving the integration IDs, tell the user which accounts to connect in the OMA console. Leave the campaign paused while any required connection is missing or unverified. Only after verifying access may you proceed with activation or use each owning profile's native cron commands below, and only when in scope. When editing only goals or plans, patch those fields without registering jobs or starting campaign work.

## Register Campaign Cron Jobs

1. Read `jobs` from each verified owning agent's `oma/agents/<agent-id>/config.yaml`. List the owning profile's jobs with `terminal` and `hermes -p <agent-id> cron list --all`. Match by the exact existing declaration ID or the stable native name `oma:<declared-id>`. Preserve active, completed, and operator-paused jobs. If identity or state is unclear, report it instead of creating a duplicate or resuming a job.
2. Use `hermes -p <agent-id> cron create --name 'oma:<declared-id>' --deliver local -- <schedule> <prompt>` for a missing eligible job. Pass schedule and prompt as separate literal arguments. Put any validated `--timezone` or `--repeat` before `--`; omit unset options. Do not use `cron run` or edit the job store by hand. Register only work the owning profile can perform. Only enable jobs that make external changes if the integration, target, and standing authorization are already verified; otherwise leave them unscheduled and report why. A URL alone does not authorize publication, messaging, or external modifications.
3. Read back the job and its state in the owning profile with `cron list --all`; check scheduler health with `cron status`. If the gateway is not serving that profile, report the schedule as waiting without starting or restarting services.

## Pitfalls

- A missing optional skill does not prevent authoring a team that does not need it. Use the local drafting references above; do not look for an installable template or fetch a cached release.
- Installing an already recorded campaign does not replace its board, tasks, or profiles. Older campaigns installed without a board are not retrofitted by `configure`. If a board slug is already occupied by another board or an installation is incomplete, report the conflict; do not delete anything to retry.

## Verification

Check that the saved campaign declares a non-empty `integrations` list and that each ID serves a need in the plan or its measurement. Report any missing declaration on existing campaigns during inspection; don't silently change their records or running state. Report which required connections were verified and which still block activation.

Verify the campaign config, the canonical roster (including the orchestrator and publisher), the agent records and saves paths, and the routing from `status <id>`. Check that the publisher's persona specifies what it can publish or edit and that its profile appears in `present_profiles` after provisioning. Read the saved orchestrator job prompt and confirm it names the channels and tells the agent what activity to check; if scheduling was in scope, verify the registered prompt, cadence, and state in the orchestrator's own cron store. New agents get a `tmp/` directory beside their `config.yaml` for scratch files. Report what was provisioned, which jobs were registered or skipped, and any blockers. A saved job, an enabled job, a healthy scheduler, and an observed run are separate outcomes.
