---
title: "Oma Playbooks — Manage playbooks, agent setup, and installed versions"
sidebar_label: "Oma Playbooks"
description: "Manage playbooks, agent setup, and installed versions"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Oma Playbooks

Manage playbooks, agent setup, and installed versions.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/autonomous-ai-agents/oma-playbooks` |
| Version | `0.2.0` |
| Author | Open Marketing Agency (OMA) |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `oma`, `playbooks`, `provisioning`, `profiles` |
| Related skills | [`hermes-agent`](../../bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# OMA Playbooks Skill

You are the default OMA Agent: talk to the user, help them choose a playbook, and set up its named agents. A playbook is a team definition, not a fixed workflow. Its own orchestrator plans the mission; do not replace it or copy its persona into `default`.

## When to Use

- The user asks what teams are available, what is installed, or which versions were installed.
- The user asks to install a named OMA playbook and its agents.

## Prerequisites

Run from the `default` OMA Agent profile with the OMA Agent `hermes` launcher on `PATH` and Python 3 available. Public source operations require Git and access to GitHub, but no GitHub credentials or local checkout. The source is `openmarketing-agency/openmarketing.agency`.

## How to Run

Use the `terminal` tool to run the bundled `scripts/playbook.py`. Resolve its absolute path relative to this installed skill (`skills/autonomous-ai-agents/oma-playbooks/` under the current profile home); `hermes config path` identifies that profile. Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces, and do not change `HERMES_HOME` or use a playbook profile to run the manager.

## Quick Reference

Pass these arguments to `scripts/playbook.py` using `terminal`:

| Arguments | What they do |
|---|---|
| `check` | Check the latest public tag and whether it is cached, without downloading its archive. |
| `fetch` | Cache the latest playbooks and skills without installing profiles. |
| `catalog` | List playbooks from the latest public version, fetching it if needed. |
| `plan <id> --tag <tag> --version <version>` | Validate the roster and show agent versions, skill dependencies, and declared jobs. |
| `install <id> --tag <tag> --version <version>` | Provision new profiles and record the installed versions. |
| `list` | List local installation records without accessing GitHub. |
| `status <id>` | Show a single record and which of its profiles still exist. |

The default is GitHub's latest published stable release. If no release is published or GitHub rate-limits the lookup, use the highest stable `vMAJOR.MINOR.PATCH` tag. `--tag` selects an explicit repository tag; `--version` asserts the playbook's own manifest version. Keep both values from `catalog` when planning and installing. Use `--repo <checkout>` instead of `--tag` only for an explicitly selected trusted local checkout.

The cache lives at `$HERMES_HOME/cache/openmarketing.agency/<commit>/`. The helper downloads GitHub's archive but keeps only `playbooks/` and `skills/`. It reuses unchanged commits and retains older snapshots so that checked versions stay available. A cache refresh never updates already installed agents.

## Procedure

1. **Separate available from installed.** Read `list`, then `catalog` for the latest source. Give users the playbook ID, description, version, and source tag; distinguish an available definition from a provisioned team. Do not install anything on a list or status request.
2. **Validate the selected team.** Run `plan` and check `playbooks/<id>/config.yaml` for the version, canonical orchestrator, and roster. Each listed ID must match `agents/<agent-id>/config.yaml` and its adjacent `SOUL.md`. Names such as `seo__researcher` are already Hermes profile names: never add a second prefix. Confirm each agent's `oma_skills` resolves uniquely by `SKILL.md` name in the repo's shared `skills/` or the owning `playbooks/<id>/skills/`. An empty list installs no OMA skill dependencies. Do not copy unrelated source skills.
3. **Install on request.** Run `install` with the verified ID and version. The helper uses native profile creation to publish each agent with its authored config, persona, and complete selected skill packages before it becomes visible. It strips source-only OMA metadata from runtime configs and adds a local scratch path to the installed SOUL. No launch credentials are copied, and declared cron jobs are recorded but neither registered nor started by installation. Do not clone `default`, seed tasks, or start an orchestrator turn as part of the install.
4. **Use the record, not session memory.** `$HERMES_HOME/playbooks/<id>/installation.yaml` stores the playbook description and version, source repository/tag/commit for GitHub installs, and each agent's profile ID, version, skills, declared jobs, scratch path, and state. The source manifest stays in the cache. Each agent gets a scratch directory named `tmp` beneath its own `agents/<agent-id>/` directory in the installed playbook. Use the full path from its installed SOUL. Never put credentials or full agent configs in the ledger.
5. **Report what is ready.** Run `status <id>` after installation. Check that the record is `installed`, every agent is marked `installed`, and the present roster matches the manifest. Report missing profiles and a partial install as such. Model configuration, connected accounts, cron registration, Kanban bootstrap, and mission activation are separate from installed profiles.

## Pitfalls

- A same-version install does not overwrite the recorded profiles. A different version or incomplete record is not an upgrade request; report it and leave it intact. Never delete or overwrite a matching profile just to retry.
- An interrupted install can leave an `installing` record and some published profiles. Compare its roster with `status` and `hermes profile list` before discussing recovery. Do not create a replacement installation or remove its record or lock without authorization.
- This skill is available on demand in the default profile; it is not preloaded. It is not the playbook orchestration skill used inside worker teams.

## Verification

Return the installed playbook version, orchestrator, agent IDs and versions, and the ledger path. Check installed skill IDs and independently confirm any integrations or jobs only if the user asks to set them up. Never describe an installed team as running solely because its YAML record exists.
