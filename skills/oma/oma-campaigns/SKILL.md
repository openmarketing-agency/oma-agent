---
name: oma-campaigns
description: Install and inspect local OMA campaigns.
version: 0.3.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, campaigns, provisioning, profiles]
    related_skills: [hermes-agent]
---

# OMA Campaigns Skill

Use this skill in the default OMA Agent profile to design and provision campaigns from the saved brand and playbook. Each campaign has one orchestrator, which plans and assigns work on its own Kanban board. There are no campaign or agent templates.

## When to Use

- The user asks to create or provision a campaign, inspect an installed one, or save its goals or plans.

## Prerequisites

Resolve the default Hermes home with `hermes -p default config path`. Read `oma/brand/config.yaml` and `oma/playbook/config.yaml` from that home before designing a team. For record formats load `oma-agents` with `skill_view`. `oma-bundle/skills/` supplies reusable skills only; find them with `search_skills` and read relevant ones with `skill_view`. Do not look for campaign templates or use the onboarding URL as a source of executable definitions.

## How to Run

Use `terminal` to run `scripts/playbook.py` from the installed skill directory (`skills/oma/oma-campaigns/` under the current profile home). Use the directory reported by `skill_view` if the profile retains an older customized copy. Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces and do not switch to a campaign profile to run the helper.

| Arguments | What they do |
|---|---|
| `install <id>` | Provision the saved campaign and agent records, create the board, and install declared shared skills. |
| `list` | List installed campaigns. |
| `status <id>` | Show an installation record and the profiles that still exist. |
| `configure <id>` | Create a missing campaign config or fill missing routing fields from the installation ledger. Does not reprovision agents or create a board. |

## Campaign Config

Save the editable config at `oma/campaigns/<campaign_id>/config.yaml`. Use the campaign ID as the directory name. For example, not as a template to install verbatim:

```yaml
id: seo
name: SEO
description: Improve the site's organic visibility.
version: 0.1.0
orchestrator: seo__orchestrator
agents:
  - seo__orchestrator
  - seo__researcher
kanban_board: campaign-seo
kanban_board_name: SEO
goals:
  - Increase qualified organic traffic.
plans:
  - Review search performance and prioritize high-impact fixes.
```

Goals and plans are inline YAML lists of text. All campaigns share the strategy at `oma/playbook/config.yaml`; do not add a `playbook` field or rewrite older records just to remove it. This config is the source for initial provisioning; the installation ledger is separate.

Use exactly one orchestrator, `<campaign_id>__orchestrator`, in the ordered `agents` list. Use canonical `<campaign_id>__<agent_id>` IDs unchanged and without duplicates. Before provisioning, the list is the proposed roster; after provisioning verify it against `present_profiles`. The helper fills missing `kanban_board` and `kanban_board_name`. Use the board slug in commands. Editing a record does not reconfigure an installed board or profile.

## Procedure

1. **Design from the records.** Compare the saved strategy, audience, channels, assets, and available capabilities. Choose the smallest set of campaigns with distinct goals and useful first steps. For each, choose one orchestrator and only the specialists that have distinct responsibilities and handoffs. Use `list` and `status` first on a rerun; reuse installed teams and preserve edits, notes, and manual pauses rather than creating duplicates.
2. **Save the campaign and agent records.** Use `write_file` or `patch` for the campaign config and each `oma/agents/<agent-id>/config.yaml` and `SOUL.md`. Record canonical `id`, `name`, `description`, and `campaign_id` for each role; use the same ID for the future profile. Give the orchestrator responsibility for deciding Kanban tasks and handoffs rather than hardcoding a pipeline. Choose only needed toolsets and existing shared skills; use `oma_skills` for exact package IDs to install, or `[]` for none. Keep `saves/` and link each persona to its own absolute saves path. Never copy credentials or grant authority inferred from a website.
3. **Decide which work needs cron.** Assign each genuine recurring obligation to exactly one role. Choose its cadence from the campaign's goals, freshness needs, and external constraints. An orchestrator can own a periodic review when warranted; a specialist can own an independent recurring check it can actually perform. Leave one-off work, handoffs, and event-driven work on Kanban. Do not create a job for every role or a second timer for an existing obligation. Save `jobs: []` for unscheduled agents. For each job use a stable `id`, a native Hermes `schedule`, and a bounded `prompt` with clear stop conditions; add `timezone` or positive `repeat` only when needed. Do not add per-job skills, scripts, or remote delivery.
4. **Provision and verify.** Run `install <id>` using the saved records. Check `status <id>` for the expected orchestrator, board, and complete `present_profiles` list before enabling any jobs. The helper wires the same board into the team without switching the shared current board. It does not start turns, copy launch credentials, create jobs, or seed tasks. Use `configure <id>` to recover missing campaign metadata for an existing installation without reinstalling.
5. **Register eligible jobs.** Use each verified owning profile's native cron commands in the next section when provisioning includes scheduling. When editing only goals or plans, patch those fields without registering jobs or starting campaign work.

## Register Campaign Cron Jobs

1. Match each saved job to its owning agent and that agent's `declared_jobs` in `status`. List the owning profile's jobs with `terminal` and `hermes -p <agent-id> cron list --all`. Match by the exact existing declaration ID or the stable native name `oma:<declared-id>`. Preserve active, completed, and operator-paused jobs. If identity or state is unclear, report it instead of creating a duplicate or resuming a job.
2. Use `hermes -p <agent-id> cron create --name 'oma:<declared-id>' --deliver local -- <schedule> <prompt>` for a missing eligible job. Pass schedule and prompt as separate literal arguments. Put any validated `--timezone` or `--repeat` before `--`; omit unset options. Do not use `cron run` or edit the job store by hand. Register only work the owning profile can perform. Only enable jobs that make external changes if the integration, target, and standing authorization are already verified; otherwise leave them unscheduled and report why. A URL alone does not authorize publication, messaging, or external modifications.
3. Read back the job and its state in the owning profile with `cron list --all`; check scheduler health with `cron status`. If the gateway is not serving that profile, report the schedule as waiting without starting or restarting services.

## Pitfalls

- A missing optional skill does not prevent authoring a team that does not need it. Never look for another campaign template or fetch a cached release.
- Installing an already recorded campaign does not replace its board, tasks, or profiles. Older campaigns installed without a board are not retrofitted by `configure`. If a board slug is already occupied by another board or an installation is incomplete, report the conflict; do not delete anything to retry.

## Verification

Verify the campaign config, the canonical roster, the agent records and saves paths, and the routing in `$HERMES_HOME/playbooks/<id>/installation.yaml`. Report what was provisioned, which jobs were registered or skipped, and any blockers. A saved job, an enabled job, a healthy scheduler, and an observed run are separate outcomes.
