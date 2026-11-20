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
| Version | `0.2.2` |
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

Use this skill in the default OMA Agent profile to install a campaign already present on the runtime. A campaign defines a team; its orchestrator, not the default profile, plans and runs the work.

## When to Use

- The user asks to install a named local campaign, inspect an installed one, or save its goals or plans.

## Prerequisites

Use `$HERMES_HOME/oma-bundle` in the default profile. In Docker this is `/opt/data/oma-bundle`: campaign definitions are in `campaigns/<id>/config.yaml`, and shared skill packages are in `skills/`. A campaign may also include its own `skills/` directory. Use the OMA Agent `hermes` launcher on `PATH` and Python 3. There is no network source, catalog, or version selection.

## How to Run

Use `terminal` to run `scripts/playbook.py` from the installed skill directory (`skills/oma/oma-campaigns/` under the current profile home). Use the directory reported by `skill_view` if the profile retains an older customized copy. Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces and do not switch to a campaign profile to run the helper.

| Arguments | What they do |
|---|---|
| `install <id>` | Create the campaign board, provision its agent profiles, and install their declared skills. |
| `list` | List installed campaigns, not available source definitions. |
| `status <id>` | Show an installation record and the profiles that still exist. |
| `configure <id>` | Create a missing campaign config or fill missing routing fields from the installation ledger. Does not reprovision agents or create a board. |

## Campaign Config

The default profile stores each installed campaign's editable config at `oma/campaigns/<campaign_id>/config.yaml` under its Hermes home. Use the campaign ID as the directory name. For example:

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

Goals and plans are inline YAML lists of text. Use `goals: []` and `plans: []` until values have been chosen. All campaigns share the single strategy at `oma/playbook/config.yaml`; do not add a `playbook` field. Ignore legacy `playbook` fields without rewriting old records just to remove them. Keep this file separate from source definitions and the installation ledger.

`orchestrator` is the canonical profile ID declared in the source manifest's `orchestrator` field. Keep `agents` as an ordered YAML list of verified campaign profile IDs, including the orchestrator. Use canonical `<campaign_id>__<agent_id>` IDs unchanged and without duplicates. `kanban_board` is the board slug (`campaign-<id>`); `kanban_board_name` is its display name at installation. Use the slug in commands. Editing this metadata does not provision agents, rename the board, reassign the orchestrator, or rebind profiles.

## Procedure

1. When asked what can be installed, inspect `$HERMES_HOME/oma-bundle/campaigns` using `search_files`. Do not fetch or check for updates.
2. On request, run `install <id>` with the local campaign ID. The helper validates `orchestrator`, `agents`, and declared `oma_skills` from the manifest. It creates one Kanban board, enables the team's Kanban tools on that board, and tells the declared orchestrator to coordinate work there with its own roster. Do not switch the shared current board. Installation does not start agent turns, copy launch credentials, register cron jobs, or seed tasks.
3. Use `status <id>` to check the board slug, orchestrator, and profiles. After installation or when asked to record the roster, use `read_file` and `patch` to save the verified `present_profiles` under `agents` in the editable `config.yaml`, in roster order. Run `configure <id>` first if the record is missing. Do not list unprovisioned drafts. Report discrepancies rather than silently removing existing entries.
4. To inspect the board from the CLI, use `terminal` with `hermes kanban --board <kanban_board> list`; a newly installed board can be empty. The ledger is `$HERMES_HOME/playbooks/<id>/installation.yaml`. Scratch paths live under that directory and are exposed in each installed agent's SOUL.
5. To save campaign goals or plans, run `configure <id>` if the config is missing. Use `read_file` and `patch` on the campaign config to update only the requested fields. Saving a plan does not schedule or execute it.

## Pitfalls

- If the local definition or a declared skill is missing, report the missing input. Do not look for a remote source or a cached release.
- Installing an already recorded campaign does not replace its board, tasks, or profiles. Older campaigns installed without a board are not retrofitted by `configure`. If a board slug is already occupied by another board or an installation is incomplete, report the conflict; do not delete anything to retry.

## Verification

For provisioning, reopen the campaign config, confirm its routing metadata matches the installation ledger, and verify the `agents` list against the present profiles. For config edits, verify the changed values. Summarize what was installed or changed and mention blockers. An installed team is not necessarily running or connected to the user's services.
