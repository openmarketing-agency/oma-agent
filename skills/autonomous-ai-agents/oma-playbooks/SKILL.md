---
name: oma-playbooks
description: Manage playbooks, agent setup, and installed versions.
version: 0.2.2
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, playbooks, provisioning, profiles]
    related_skills: [hermes-agent]
---

# OMA Playbooks Skill

You are the default OMA Agent: talk to the user, help them choose a playbook, and set up its named agents. A playbook is a team definition, not a fixed workflow. Its own orchestrator plans the mission; do not replace it or copy its persona into `default`.

## When to Use

- The user asks what teams are available, what is installed, or which versions were installed.
- The user asks to install a named OMA playbook and its agents.

## Prerequisites

Run from the `default` OMA Agent profile with the OMA Agent `hermes` launcher on `PATH` and Python 3 available. Public source operations only need access to Cloudflare R2; no Git, credentials, or local checkout are required.

## How to Run

Use the `terminal` tool to run the bundled `scripts/playbook.py`. Resolve its absolute path relative to this installed skill (`skills/autonomous-ai-agents/oma-playbooks/` under the current profile home); `hermes config path` identifies that profile. Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces, and do not change `HERMES_HOME` or use a playbook profile to run the manager.

## Quick Reference

Pass these arguments to `scripts/playbook.py` using `terminal`:

| Arguments | What they do |
|---|---|
| `check` | Read the release manifest on R2 and report cache status without downloading ZIPs. |
| `fetch` | Cache the latest playbooks and skills without installing profiles. |
| `catalog` | List playbooks from the latest public version, fetching it if needed. |
| `plan <id> --tag <tag> --version <version>` | Validate the roster and show agent versions, skill dependencies, and declared jobs. |
| `install <id> --tag <tag> --version <version>` | Provision new profiles and record the installed versions. |
| `list` | List local installation records without network access. |
| `status <id>` | Show a single record and which of its profiles still exist. |

The default follows `latest.yaml` on R2. If that object returns 404, the manager uses the existing `v0.1.1` snapshot. `--tag` selects a specific release via `<tag>/release.yaml` (the legacy `v0.1.1` snapshot needs no manifest); `--version` asserts the playbook's own manifest version. Keep both values from `catalog` when planning and installing. Use `--repo <checkout>` instead of `--tag` only for an explicitly selected trusted local checkout.

The helper downloads `<tag>/playbooks.zip` and `<tag>/skills.zip` from `https://pub-d3419a6b761b48b38897cf50a5056136.r2.dev`. It checks that both ZIPs identify the selected commit before caching them together under `$HERMES_HOME/cache/oma-playbooks-r2/<commit>/`. If an archive is missing, report the failed download and leave the existing cache intact. A cache refresh never updates already installed agents.

## Procedure

1. **Separate available from installed.** Read `list`, then `catalog` for the latest source. Give users the playbook ID, description, version, and source tag; distinguish an available definition from a provisioned team. Do not install anything on a list or status request.
2. **Validate the selected team.** Run `plan` and check `playbooks/<id>/config.yaml` for the version, canonical orchestrator, and roster. Each listed ID must match `agents/<agent-id>/config.yaml` and its adjacent `SOUL.md`. Names such as `seo__researcher` are already Hermes profile names: never add a second prefix. Confirm each agent's `oma_skills` resolves uniquely by `SKILL.md` name in the repo's shared `skills/` or the owning `playbooks/<id>/skills/`. An empty list installs no OMA skill dependencies. Do not copy unrelated source skills.
3. **Install on request.** Run `install` with the verified ID and version. The helper uses native profile creation to publish each agent with its authored config, persona, and complete selected skill packages before it becomes visible. It strips source-only OMA metadata from runtime configs and adds a local scratch path to the installed SOUL. No launch credentials are copied, and declared cron jobs are recorded but neither registered nor started by installation. Do not clone `default`, seed tasks, or start an orchestrator turn as part of the install.
4. **Use the record, not session memory.** `$HERMES_HOME/playbooks/<id>/installation.yaml` stores the playbook description and version, source repository/tag/commit and R2 base URL for new public installs, and each agent's profile ID, version, skills, declared jobs, scratch path, and state. The source manifest stays in the cache. Each agent gets a scratch directory named `tmp` beneath its own `agents/<agent-id>/` directory in the installed playbook. Use the full path from its installed SOUL. Never put credentials or full agent configs in the ledger.
5. **Report what is ready.** Run `status <id>` after installation. Check that the record is `installed`, every agent is marked `installed`, and the present roster matches the manifest. Report missing profiles and a partial install as such. Model configuration, connected accounts, cron registration, Kanban bootstrap, and mission activation are separate from installed profiles.

## Pitfalls

- A same-version install does not overwrite the recorded profiles. A different version or incomplete record is not an upgrade request; report it and leave it intact. Never delete or overwrite a matching profile just to retry.
- An interrupted install can leave an `installing` record and some published profiles. Compare its roster with `status` and `hermes profile list` before discussing recovery. Do not create a replacement installation or remove its record or lock without authorization.
- This skill is available on demand in the default profile; it is not preloaded. It is not the playbook orchestration skill used inside worker teams.

## Verification

Return the installed playbook version, orchestrator, agent IDs and versions, and the ledger path. Check installed skill IDs and independently confirm any integrations or jobs only if the user asks to set them up. Never describe an installed team as running solely because its YAML record exists.
