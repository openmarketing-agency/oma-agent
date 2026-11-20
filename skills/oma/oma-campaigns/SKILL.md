---
name: oma-campaigns
description: Install and inspect local OMA campaigns.
version: 0.2.2
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, campaigns, provisioning, profiles]
    related_skills: [hermes-agent]
---

# OMA Campaigns Skill

Use this skill in the default OMA Agent profile to install a campaign already present on the runtime. A campaign defines a team; its orchestrator, not the default profile, plans and runs the work.

## When to Use

- The user asks to install a named local campaign, inspect an installed one, or save its goals, plans, or playbook link.

## Prerequisites

The runtime must provide campaign definitions at `/opt/opa/campaigns/<id>/config.yaml` and shared skill packages at `/opt/oma/skills`. A campaign may also include its own `skills/` directory. Use the default profile with the OMA Agent `hermes` launcher on `PATH` and Python 3 available. There is no network source, catalog, or version selection.

## How to Run

Use `terminal` to run `scripts/playbook.py` from the installed skill directory (`skills/oma/oma-campaigns/` under the current profile home). Use the directory reported by `skill_view` if the profile retains an older customized copy. Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces and do not switch to a campaign profile to run the helper.

| Arguments | What they do |
|---|---|
| `install <id>` | Create the campaign board, provision its agent profiles, and install their declared skills. |
| `list` | List installed campaigns, not available source definitions. |
| `status <id>` | Show an installation record and the profiles that still exist. |
| `configure <id>` | Create a missing campaign config or fill missing routing fields from the installation ledger. Does not reprovision agents or create a board. |

## Campaign Config

The default profile stores each installed campaign's editable config at `oma/campaigns/<campaign_dir>/config.yaml` under its Hermes home. Use the campaign ID as the directory name. For example:

```yaml
id: seo
name: SEO
description: Improve the site's organic visibility.
version: 0.1.0
orchestrator: seo__orchestrator
kanban_board: campaign-seo
kanban_board_name: SEO
goals:
  - Increase qualified organic traffic.
plans:
  - Review search performance and prioritize high-impact fixes.
playbook: organic-growth
```

Goals and plans are inline YAML lists of text. `playbook` is the ID of a saved playbook at `oma/playbooks/<id>/config.yaml` in the same Hermes home. Verify that record exists and its ID matches before linking it. Use `goals: []`, `plans: []`, and `playbook: null` until the user supplies or approves values. Keep this file separate from source definitions and the installation ledger.

`orchestrator` is the canonical profile ID declared in the source manifest's `orchestrator` field. The manifest's `agents` list defines the roster. Use those IDs unchanged. `kanban_board` is the board slug (`campaign-<id>`); `kanban_board_name` is its display name at installation. Use the slug in commands. Editing this metadata does not rename the board, reassign the orchestrator, or rebind profiles.

## Procedure

1. When asked what can be installed, inspect the campaign directories already present under `/opt/opa/campaigns` using `search_files`. Do not fetch or check for updates.
2. On request, run `install <id>` with the local campaign ID. The helper validates `orchestrator`, `agents`, and declared `oma_skills` from the manifest. It creates one Kanban board, enables the team's Kanban tools on that board, and tells the declared orchestrator to coordinate work there with its own roster. Do not switch the shared current board. Installation does not start agent turns, copy launch credentials, register cron jobs, or seed tasks.
3. Use `status <id>` to check the board slug, orchestrator, and profiles. To inspect the board from the CLI, use `terminal` with `hermes kanban --board <kanban_board> list`; a newly installed board can be empty. The ledger is `$HERMES_HOME/playbooks/<id>/installation.yaml`. Scratch paths live under that directory and are exposed in each installed agent's SOUL.
4. To save campaign goals, plans, or a playbook link, run `configure <id>` if the config is missing. Use `read_file` and `patch` on the campaign config to update only the requested fields. Saving a plan does not schedule or execute it.

## Pitfalls

- If the local definition or a declared skill is missing, report the missing input. Do not look for a remote source or a cached release.
- Installing an already recorded campaign does not replace its board, tasks, or profiles. Older campaigns installed without a board are not retrofitted by `configure`. If a board slug is already occupied by another board or an installation is incomplete, report the conflict; do not delete anything to retry.

## Verification

For provisioning, report the campaign ID, board slug, orchestrator, and present agent profiles. Reopen the campaign config and confirm its routing metadata matches the installation ledger. For config edits, verify the changed values and any playbook link. An installed team is not necessarily running or connected to the user's services.
