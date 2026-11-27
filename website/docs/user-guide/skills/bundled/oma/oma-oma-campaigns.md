---
title: "Oma Campaigns — Design, validate, and activate local campaigns"
sidebar_label: "Oma Campaigns"
description: "Design, validate, and activate local campaigns"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Oma Campaigns

Design, validate, and activate local campaigns.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/oma/oma-campaigns` |
| Version | `0.8.0` |
| Author | Open Marketing Agency (OMA) |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `oma`, `campaigns`, `ideas`, `plays`, `provisioning`, `profiles` |
| Related skills | [`hermes-agent`](../../bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent.md), [`oma-agents`](../../bundled/oma/oma-oma-agents.md), [`oma-playbook`](../../bundled/oma/oma-oma-playbook.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# OMA Campaigns Skill

Design campaigns from the saved brand and marketing playbook. Creating a campaign provisions its team and an empty Kanban board and leaves it paused. Use the ideas catalog and worked plays as references, not as installer inputs. One orchestrator plans and assigns work and one publisher applies authorized changes.

## When to Use

- Create campaigns during onboarding, add a campaign, or revise its goals, plans, and tools.
- Inspect, provision, or start a saved campaign when requested.
- Find an idea, worked play, or channel rule to guide campaign design.

## Prerequisites

Resolve the default Hermes home with `hermes -p default config path`. Read `oma/brand/config.yaml`, its relevant research, and `oma/playbook/config.yaml`. Load `oma-agents` with `skill_view` for agent record and persona guidance. Use `skills_search` to find reusable OMA skill packages. Treat the onboarding URL as research, not as a source of executable definitions.

## How to Run

Use `terminal` from the installed skill directory reported by `skill_view`. Run `campaign.py` with `python3` on macOS/Linux or `python` on Windows. Run `plays.py` with Python in the activated Hermes environment, which supplies its YAML parser. Quote paths containing spaces and use the default profile. Pass `--home <default Hermes home>` to `plays.py` when automatic home discovery is unavailable.

| `scripts/campaign.py` arguments | Purpose |
| --- | --- |
| `list`, `status <id>` | Inspect installed or incomplete campaigns and verify the board and roster. |
| `validate <kind> <path>` | Validate a `brand`, `playbook`, `campaign`, or `agent` record without applying it. |
| `integrations` | Suggest canonical IDs from brand evidence. Does not verify account access. |
| `recommend --channels <play channels> [--for <ids>]` | Pick integrations for the play's channels, list what they need (such as image or video generation for Instagram) and complementary tools. Suggestions only. |
| `create <definition.yaml>` | Provision a new campaign, its team, and an empty Kanban board. Leaves it paused. |
| `install <id>` | Provision a legacy saved definition as a paused campaign. |
| `revise <id> <definition.yaml>` | Apply revised goals, plans, and tools to an installed campaign and sync its team. Refuses tool changes the plans don't cover. |
| `configure <id>` | Fill missing routing on a verified installation; does not change its roster. |
| `lifecycle <id> resumed` | Resume an installed campaign using its saved model. Does not verify connection access. |

| `scripts/plays.py` arguments | Purpose |
| --- | --- |
| `ideas [--section <name>] [--play <play-id>]` | Find options in the [ideas catalog](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/ideas/catalog.yaml). |
| `list`, `show <play-id>` | Find plays and their `play.yaml`, `rules.md`, `example.md`, and channel guidance. |
| `new <play-id> --from <play-id>` or `--blank` | Draft a custom reference under `oma/plays/`. Never overwrites. |
| `validate [<play-id>]` | Validate reference plays; use `campaign.py validate` for saved records. |
| `jobs <campaign-id> --play <play-id> --agent <role> --sources "..."` | Draft jobs using the chosen reference and that role's verified sources. Does not save or enable jobs. |

## Campaign Format

Write new definitions outside `oma/campaigns/`, for example `oma/staging/<campaign_id>.yaml`. The `create` command writes the canonical `oma/campaigns/<campaign_id>/config.yaml`; do not write it directly for a new campaign. Use `id`, `name`, `description`, `orchestrator`, `agents`, `integrations`, `goals`, and `plans`, plus optional `integration_categories` for tool suggestions. See the [record examples](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/records.md) for a complete sample.

- `goals` and `plans` are inline YAML lists of text. Goals describe the audience, outcome and measurement; ordered plans describe what ships, prerequisites, channel sequence and how results inform later work. Put business-specific limits in plans and relevant personas.
- Use canonical IDs `<campaign_id>__<role>` for the ordered roster, with one `__orchestrator` and one `__publisher`. Put recurring job declarations in each owning agent's config, not in campaign YAML.
- Campaign mode gates new publications only: `approve` and `control` require exact-revision human approval after saving a new post or reply; `yolo` auto-approves without asking. Route authorized edits to existing live content to the publisher without publication approval. `control` disables all campaign cron, including analytics.
- Plays and ideas are reference material, not record fields. Do not add `play`, `ideas`, `rank`, `needs`, `deliverables`, `access_needed`, or `limits` as campaign keys. Do not author legacy `playbook` or `version`; do not set helper-managed installation or lifecycle state by hand.
- Use `integrations` for the smallest set of canonical connections the actual plan needs. Save the IDs before asking the user to connect missing accounts in the OMA console. Never ask for credentials or MCP configuration in chat. A catalog ID or public account URL does not verify access.
- Integrations come from `recommend`, run in step 4. `create` and `revise` add a provider, and a plan naming it, for any need the definition leaves unmet; the console shows every integration as required.
- Use `integration_categories` to suggest the types of tools the plan needs, even when no specific connector has been chosen yet. Use exact category labels from `hermes_cli/oma_campaigns/schemas/composio-categories.json` (or the [Composio catalog](https://docs.composio.dev/data/toolkits-list.json)), without duplicates. Choose only categories relevant to the work; omit the field or use `[]` when there are no suggestions. Categories do not replace `integrations`, connect accounts, or grant access.

## Procedure

1. **Read the strategy and existing work.** Match campaigns to the saved strategy and brand evidence. Read existing campaign records and use `status` to verify installed ones. Reuse suitable teams and preserve manual pauses.
2. **Choose ideas and adapt a play.** Pick catalog ideas for this business, not one campaign per idea. Use the [worked plays](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/plays/README.md) for choices about roles, deliverables, and cadence; adapt the example rather than copying its facts. For a first run, consider launch (`show-hn-launch`), Reddit replies (`buying-intent-listening`), SEO (`seo-blog-engine`), and social (`daily-shorts` or `comment-to-dm`); choose what fits the brand and explain omitted or deferred options. If you need a reusable custom play, follow [Designing plays](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/designing-plays.md) and the [play schema](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/play-schema.md). Business decisions go in the existing campaign and agent fields, not in a new manifest.
3. **Plan work that ships.** Research the topics, audience, accounts, and applicable rules now. State the first concrete output and any steps that must come before it in `plans`. Share prerequisites instead of duplicating work. For missing website, blog, or docs infrastructure, route authorized hosting work via the `oma-agents` maintenance handoff; keep `maintenance` outside the roster. When posting access is missing, prepare drafts for an authorized person where the channel permits it.
4. **Prepare the definition and team.** Run `campaign.py recommend --channels <the play's requires channels>` and save its `integrations`, including each need's `chosen` provider, and its `integration_categories`. Give each integration a plan naming it, and give the role that uses a media provider its instructions. Write the staging definition, each `oma/agents/<agent-id>/config.yaml`, and its role-specific `SOUL.md`. Give everyone distinct outputs, an absolute `saves/` path, and only needed tools and skills. Give standing `kanban` access to the orchestrator only. Roles reading untrusted content do not get `terminal`. Use authorized channel tools for writes, never browser-driven publication. Publishers follow the [channel rules](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/channels/README.md), verify the destination, and record the resulting URL or receipt. Apply human approval only to new publications in `approve` and `control`. For human-only channels, hand material to the authorized person rather than posting automatically.
5. **Declare recurring work.** Follow [review signals](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/review-signals.md). For active social and community accounts, start with **one lightweight activity check per hour** for new comments, replies, mentions, or tagged posts. Keep performance reporting weekly. Use the requested cadence and prefer reliable events when available. Scope checks to verified sources, act only on new items since the last successful checkpoint, cap work, and don't queue duplicates. The Comment-to-DM publisher can scan eligible keyword replies hourly; polling is not permission to send. Save existing `jobs` fields (`id`, `schedule`, `prompt`, plus `timezone` or `repeat` only as needed); otherwise `jobs: []`.
6. **Validate and provision.** Run `campaign.py validate campaign <path>` and `validate agent <path>` in `terminal`. Resolve each `warnings` entry from campaign validation by adding a provider or planning the fallback. Read each persona back and check the roster, saves paths, integration IDs, suggested categories, and declared prompts. Complete missing role records before provisioning. Run `campaign.py create <definition.yaml>` for a new campaign. If the canonical config already exists and `status <id>` says to run `install`, use `install <id>` for that legacy definition instead. Reuse an already-installed campaign; report an incomplete installation as blocked rather than overwriting it. Read back `status <id>`: for a new installation, require `state: installed`, `lifecycle_state: paused`, the expected `campaign-<id>` board, and `present_profiles` matching the installed roster, including the managed analyst. Missing connections are start prerequisites, not reasons to stop at an uninstalled definition. If provisioning fails, report the error and don't claim the campaign was created.

## Change a Campaign's Tools

When the user adds or removes a tool on an installed campaign, revise the plans with it; a tool no plan names gets no work.

1. Copy `oma/campaigns/<id>/config.yaml` to `oma/staging/<id>.yaml`. Fields you leave out keep their saved values; the roster and mode don't change here.
2. Run `recommend --for <the new integrations>` and add one provider for each unmet need, such as image generation for Instagram.
3. For each added tool, add a plan naming it, what it produces, the owning role, the cadence, and the fallback. Change `goals` only when what is measured changes. For each removed tool, rewrite or drop the plans that name it.
4. Update the owning roles' records: the publisher's channels and `SOUL.md` for a new channel, the writer's `SOUL.md` and `oma_skills` for a new media tool, and an hourly activity job for a new social account per [review signals](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/review-signals.md).
5. Run `validate`, then `revise <id> oma/staging/<id>.yaml`. It refuses an added tool no plan names and a removed tool a plan still names, syncs the team, and on a running campaign outside `control` queues one re-plan task for the orchestrator. Report `added`, `removed`, `replan_task`, and any `warnings`.

## Finish Campaign Copy

Add `humanizer` to `oma_skills` for roles that own outward-facing copy, such as articles, social posts, replies, captions, scripts, ads, and emails. In the role's `SOUL.md`, ask the writer to load it with `skill_view` for a final editorial pass before saving or handing off the draft. Use the saved brand voice and preserve verified claims, exact quotes and numbers, sources, links, disclosures, and channel limits. Follow venue rules on AI-assisted text. For venues that require human-written copy, hand over only the facts the venue permits. The publisher delivers the approved revision unchanged.

## Write Kanban Cards People Can Read

Put this guidance in each campaign orchestrator's `SOUL.md`, following the orchestrator examples in `oma-agents`. Apply it to kickoff cards and the follow-up cards the orchestrator creates. Give the card a short action title. In the body, tell the assignee what to do, why it matters when that isn't obvious, and what to hand back or check before calling it done. Include relevant links or constraints. Use plain sentences and short Markdown bullets when useful; don't paste JSON, YAML, raw tool output, or a wall of IDs. Set the board, assignee, task dependencies, and idempotency key in the Kanban fields rather than making the reader parse them from the body. See the [example kickoff card](https://github.com/openmarketing-agency/oma-agent/blob/main/skills/oma/oma-campaigns/references/records.md#kickoff-task).

## Activate a Campaign

Only when requested. Read back `status <id>` and verify the campaign is installed with its board and full team. Do not reinstall to extend an installed roster. Verify actual access to the intended accounts and work prerequisites before resuming or enabling anything; a missing required connection leaves the campaign paused. Use the console's start flow when available, or the campaign lifecycle command. A resume requires a saved model. In `control`, do not queue automatic kickoff work or register or run any cron, including the managed analytics collector. Human-approved publications can still be dispatched.

In `approve` or `yolo`, for an authorized kickoff, queue one task for the orchestrator on the campaign's recorded board via Tool Search, with idempotency key `kickoff:<campaign_id>`. Reuse jobs registered by the console or sync. For an eligible missing job, list the owning profile's jobs with `hermes -p <agent-id> cron list --all`; only create if no matching managed job exists. Use `cron create --name 'oma:<declared-id>' --deliver local -- <schedule> <prompt>` in that profile, placing applicable timezone or repeat flags before `--`. Pass schedule and prompt separately. Preserve operator pauses, don't force an immediate run, and never register a job that writes externally without verified authority.

## Pitfalls

- The examples are not installable templates. A play's role list, cadence, and prerequisites are drafting inputs, not new campaign fields.
- Editing goals or plans does not authorize running work or changing the installed roster or schedules.
- A saved integration declaration is not access or publishing authority. When in doubt, keep work unpublished and report what is missing.

## Verification

Report which campaigns were installed with their teams and boards, their first deliverables, and any blocked prerequisites. Verify that new campaigns are paused with no kickoff queued. If activation was requested, verify the resulting lifecycle state, queued kickoff, and scheduled jobs in their owning profiles. Distinguish an authored schedule, a registered job, and an observed run.
