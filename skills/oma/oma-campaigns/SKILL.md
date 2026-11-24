---
name: oma-campaigns
description: Design, validate, and activate local campaigns.
version: 0.8.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, campaigns, ideas, plays, provisioning, profiles]
    related_skills: [hermes-agent, oma-agents, oma-playbook]
---

# OMA Campaigns Skill

Design campaigns from the saved brand and marketing playbook. Use the ideas catalog and worked plays as drafting references; the installer still reads the existing campaign and agent records, never the reference plays. One orchestrator plans and assigns work and one publisher applies authorized changes.

## When to Use

- Draft campaigns during onboarding, add a campaign, or revise its goals and plans.
- Inspect, provision, or start a saved campaign when requested.
- Find an idea, worked play, or channel rule to guide campaign design.

## Prerequisites

Resolve the default Hermes home with `hermes -p default config path`. Read `oma/brand/config.yaml`, its relevant research, and `oma/playbook/config.yaml`. Load `oma-agents` with `skill_view` for agent record and persona guidance. Use `skills_search` to find reusable OMA skill packages. Treat the onboarding URL as research, not as a source of executable definitions.

## How to Run

Use `terminal` from the installed skill directory reported by `skill_view`. Run `campaign.py` with `python3` on macOS/Linux or `python` on Windows. Run `plays.py` with Python in the activated Hermes environment, which supplies its YAML parser. Quote paths containing spaces and use the default profile. Pass `--home <default Hermes home>` to `plays.py` when automatic home discovery is unavailable.

| `scripts/campaign.py` arguments | Purpose |
| --- | --- |
| `list`, `status <id>` | Inspect installed or incomplete campaigns, or inspect one saved campaign and its verified roster. |
| `validate <kind> <path>` | Validate a `brand`, `playbook`, `campaign`, or `agent` record without applying it. |
| `integrations` | Suggest canonical IDs from brand evidence. Does not verify account access. |
| `install <id>` | Provision saved records, the campaign board, and declared shared skills. Does not start the campaign. |
| `configure <id>` | Fill missing routing on a verified installation; does not change its roster. |
| `lifecycle <id> resumed` | Resume an installed campaign using its saved model. Does not verify connection access. |

| `scripts/plays.py` arguments | Purpose |
| --- | --- |
| `ideas [--section <name>] [--play <play-id>]` | Find options in the [ideas catalog](ideas/catalog.yaml). |
| `list`, `show <play-id>` | Find plays and their `play.yaml`, `rules.md`, `example.md`, and channel guidance. |
| `new <play-id> --from <play-id>` or `--blank` | Draft a custom reference under `oma/plays/`. Never overwrites. |
| `validate [<play-id>]` | Validate reference plays; use `campaign.py validate` for saved records. |
| `jobs <campaign-id> --play <play-id> --agent <role> --sources "..."` | Draft jobs using the chosen reference and that role's verified sources. Does not save or enable jobs. |

## Campaign Format

Save `oma/campaigns/<campaign_id>/config.yaml` using the campaign schema. Use `id`, `name`, `description`, `orchestrator`, `agents`, `integrations`, `goals`, and `plans`, plus optional `integration_categories` for tool suggestions. See the [record examples](references/records.md) for a complete sample.

- `goals` and `plans` are inline YAML lists of text. Goals describe the audience, outcome and measurement; ordered plans describe what ships, prerequisites, channel sequence and how results inform later work. Put business-specific limits in plans and relevant personas.
- Use canonical IDs `<campaign_id>__<role>` for the ordered roster, with one `__orchestrator` and one `__publisher`. Put recurring job declarations in each owning agent's config, not in campaign YAML.
- Plays and ideas are reference material, not record fields. Do not add `play`, `ideas`, `rank`, `needs`, `deliverables`, `access_needed`, or `limits` as campaign keys. Do not author legacy `playbook` or `version`; do not set helper-managed installation or lifecycle state by hand.
- Use `integrations` for the smallest set of canonical connections the actual plan needs. Save the IDs before asking the user to connect missing accounts in the OMA console. Never ask for credentials or MCP configuration in chat. A catalog ID or public account URL does not verify access.
- Use `integration_categories` to suggest the types of tools the plan needs, even when no specific connector has been chosen yet. Use exact category labels from `hermes_cli/oma_campaigns/schemas/composio-categories.json` (or the [Composio catalog](https://docs.composio.dev/data/toolkits-list.json)), without duplicates. Choose only categories relevant to the work; omit the field or use `[]` when there are no suggestions. Categories do not replace `integrations`, connect accounts, or grant access.

## Procedure

1. **Read the strategy and existing work.** Match campaigns to the saved strategy and brand evidence. Read existing campaign records and use `status` to verify installed ones. Reuse suitable teams and preserve manual pauses.
2. **Choose ideas and adapt a play.** Pick catalog ideas for this business, not one campaign per idea. Use the [worked plays](plays/README.md) for choices about roles, deliverables, and cadence; adapt the example rather than copying its facts. For a first run, consider launch (`show-hn-launch`), Reddit replies (`buying-intent-listening`), SEO (`seo-blog-engine`), and social (`daily-shorts` or `comment-to-dm`); choose what fits the brand and explain omitted or deferred options. If you need a reusable custom play, follow [Designing plays](references/designing-plays.md) and the [play schema](references/play-schema.md). Business decisions go in the existing campaign and agent fields, not in a new manifest.
3. **Plan work that ships.** Research the topics, audience, accounts, and applicable rules now. State the first concrete output and any steps that must come before it in `plans`. Share prerequisites instead of duplicating work. For missing website, blog, or docs infrastructure, route authorized hosting work via the `oma-agents` maintenance handoff; keep `maintenance` outside the roster. When posting access is missing, prepare drafts for an authorized person where the channel permits it.
4. **Save records and personas.** Write the campaign, each `oma/agents/<agent-id>/config.yaml`, and its role-specific `SOUL.md`. Give everyone distinct outputs, an absolute `saves/` path, and only needed tools and skills. Give standing `kanban` access to the orchestrator only. Roles reading untrusted content do not get `terminal`. Use approved channel tools for writes, never browser-driven publication. Publishers follow the [channel rules](channels/README.md), verify the destination and approval, and record the resulting URL or receipt. For human-only channels, hand off approved material rather than posting automatically.
5. **Declare recurring work.** Follow [review signals](references/review-signals.md). For active social and community accounts, start with **one lightweight activity check per hour** for new comments, replies, mentions, or tagged posts. Keep performance reporting weekly. Use the requested cadence and prefer reliable events when available. Scope checks to verified sources, act only on new items since the last successful checkpoint, cap work, and don't queue duplicates. The Comment-to-DM publisher can scan eligible keyword replies hourly; polling is not permission to send. Save existing `jobs` fields (`id`, `schedule`, `prompt`, plus `timezone` or `repeat` only as needed); otherwise `jobs: []`.
6. **Verify the draft.** Run `campaign.py validate campaign <path>` and `validate agent <path>` in `terminal`. Read each persona back; verify the roster, saves paths, integration IDs, suggested category labels, and declared prompts. If a role is incomplete, leave the campaign a draft. Saving records alone does not activate or schedule them.

## Activate a Campaign

Only when requested. Use `install <id>`, then read back `status <id>` and verify its expected board, orchestrator, publisher and complete `present_profiles`. Do not reinstall to extend an installed roster. Verify actual access to the intended accounts and work prerequisites before resuming or enabling anything; a missing required connection leaves the campaign paused. Use the console's start flow when available, or the campaign lifecycle command. A resume requires a saved model. `control` mode does not run ordinary agent work or cron.

For an authorized kickoff, queue one task for the orchestrator on the campaign's recorded board via Tool Search, with idempotency key `kickoff:<campaign_id>`. Reuse jobs registered by the console or sync. For an eligible missing job, list the owning profile's jobs with `hermes -p <agent-id> cron list --all`; only create if no matching managed job exists. Use `cron create --name 'oma:<declared-id>' --deliver local -- <schedule> <prompt>` in that profile, placing applicable timezone or repeat flags before `--`. Pass schedule and prompt separately. Preserve operator pauses, don't force an immediate run, and never register a job that writes externally without verified authority.

## Pitfalls

- The examples are not installable templates. A play's role list, cadence, and prerequisites are drafting inputs, not new campaign fields.
- Editing goals or plans does not authorize running work or changing the installed roster or schedules.
- A saved integration declaration is not access or publishing authority. When in doubt, keep work unpublished and report what is missing.

## Verification

Report which campaigns were drafted, their playbook priorities and first deliverables, and any blocked prerequisites. If activation was requested, verify the reported installed roster and lifecycle state, queued kickoff, and scheduled jobs in their owning profile. Distinguish an authored schedule, a registered job, and an observed run.
