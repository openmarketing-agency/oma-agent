---
title: "Oma Playbooks — Manage user playbooks and their strategies"
sidebar_label: "Oma Playbooks"
description: "Manage user playbooks and their strategies"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Oma Playbooks

Manage user playbooks and their strategies.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/oma/oma-playbooks` |
| Version | `0.1.0` |
| Author | Open Marketing Agency (OMA) |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `oma`, `playbooks`, `strategy`, `planning` |
| Related skills | [`oma-brands`](../../bundled/oma/oma-oma-brands.md), [`oma-campaigns`](../../bundled/oma/oma-oma-campaigns.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# OMA Playbooks Skill

Create, list, inspect, and update a user's playbooks and strategy. A playbook here is a local record of what the user wants to do and how they want to approach it, not an installable campaign or a running workflow.

## When to Use

- The user asks to save, find, revise, or remove a playbook or its strategy.
- The user asks for the approved strategy to use for a named playbook.

## Prerequisites

Use the active profile's Hermes home as the base for `oma/playbooks/`. On the local CLI, `hermes config path` identifies that home. Use `search_files`, `read_file`, `write_file`, and `patch` for records. Do not use the current working directory or another profile's home.

## Record Format

Save each playbook at `oma/playbooks/<playbook_dir>/config.yaml`. Use a stable lowercase, hyphen-separated ID for both `id` and `<playbook_dir>`. Keep the display `name` separate so renaming the playbook does not change its ID or folder.

```yaml
id: product-launch
name: Product Launch
description: Plan the marketing rollout for a new product.
strategy: |-
  Focus on existing customers first. Use their feedback to refine the
  messaging before expanding outreach. Measure qualified sign-ups.
```

`strategy` is the strategy text itself. Use a YAML block scalar for multiline content, not a filename or link to a separate strategy document. If the user has not supplied or asked you to draft a strategy, use `strategy: ""` and report it as unset.

## Procedure

1. **Identify the record.** List only playbooks under the active profile's `oma/playbooks/`. Match the exact ID first, then an unambiguous name. Ask which playbook the user means if multiple records match. For a new record, verify that the ID and directory are unused.
2. **Save the requested changes.** Create or patch the selected `config.yaml`. Preserve the ID and fields the user did not ask to change. Keep strategy content in the `strategy` value; do not create a separate Markdown file.
3. **Inspect or remove on request.** Read the selected record for lookups. Remove a record only on explicit request. Do not follow paths or symlinks that escape the active profile's playbook directory.

## Pitfalls

- Neither drafting nor saving a strategy authorizes executing it. Do not install campaigns, create jobs, or start agent turns as part of saving a record.
- Do not confuse these records with campaign definitions under `/opt/oma/campaigns` or installation records under `$HERMES_HOME/playbooks/`. Use `oma-campaigns` for campaign installation, not playbook authoring.

## Verification

Reopen the saved YAML. Confirm the ID matches the folder, `name` and `description` are present, and `strategy` contains the requested text or is explicitly unset. Report the record path and what changed.
