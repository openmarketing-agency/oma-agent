---
name: oma-playbooks
description: Manage playbooks, agent setup, and installed versions.
version: 0.1.0
author: Saurav Niraula (sauravniraula), Hermes Agent
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

Run from the `default` OMA Agent profile with the OMA Agent `hermes` launcher on `PATH` and Python 3 available. For source operations, use a trusted local checkout of `openmarketing-agency/openmarketing.agency`; the root contains `playbooks/` and shared `skills/`. Use the supplied checkout or locate the existing checkout in the workspace. If none is available, request a path or fetch the official checkout when authorized. Do not use a similarly named folder or an untrusted third-party checkout.

Use the `terminal` tool to run the bundled `scripts/playbook.py`. Resolve its absolute path relative to this installed skill (`skills/autonomous-ai-agents/oma-playbooks/` under the current profile home); `hermes config path` identifies that profile. Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces, and do not change `HERMES_HOME` or use a playbook profile to run the manager.

## Quick Reference

Pass these arguments to `scripts/playbook.py` using `terminal`:

| Arguments | What they do |
|---|---|
| `catalog --repo "<checkout>"` | Read the available source playbooks. |
| `plan <id> --repo "<checkout>" --version <version>` | Validate the source roster and show agent versions, skill dependencies, and declared jobs. |
| `install <id> --repo "<checkout>" --version <version>` | Provision new profiles and record the installed versions. |
| `list` | List all local installation records; no source checkout needed. |
| `status <id>` | Show a single record and which of its profiles still exist. |

`--version` is an exact assertion about the checked-out manifest, not an instruction to switch Git revisions. Use the version shown by `catalog` or the exact version requested by the user.

## Procedure

1. **Separate available from installed.** Read `list`, then `catalog` when a source checkout is available. Give users the playbook ID, description, and version; distinguish an available definition from a provisioned team. Do not install anything on a list or status request.
2. **Validate the selected team.** Run `plan` and check `playbooks/<id>/config.yaml` for the version, canonical orchestrator, and roster. Each listed ID must match `agents/<agent-id>/config.yaml` and its adjacent `SOUL.md`. Names such as `seo__researcher` are already Hermes profile names: never add a second prefix. Confirm each agent's `oma_skills` resolves uniquely by `SKILL.md` name in the repo's shared `skills/` or the owning `playbooks/<id>/skills/`. An empty list installs no OMA skill dependencies. Do not copy unrelated source skills.
3. **Install on request.** Run `install` with the verified ID and version. The helper uses native profile creation to publish each agent with its authored config, persona, and complete selected skill packages before it becomes visible. It strips source-only OMA metadata from runtime configs and adds a local scratch path to the installed SOUL. No launch credentials are copied, and declared cron jobs are recorded but neither registered nor started by installation. Do not clone `default`, seed tasks, or start an orchestrator turn as part of the install.
4. **Use the record, not session memory.** The installation record lives at `$HERMES_HOME/playbooks/<id>/installation.yaml`. It contains the playbook version, source manifest, orchestrator, timestamps, and each agent's profile ID, source version, OMA skills, declared jobs, scratch path, and provisioning state. Each profile gets a subdirectory named `tmp` under `agents/<agent-id>/` in that playbook directory. Use the full path from the installed SOUL for temporary files; the directory is not automatically cleaned or a security sandbox. Never put credentials, environment contents, or full agent configs into the ledger.
5. **Report what is ready.** Run `status <id>` after installation. Check that the record is `installed`, every agent is marked `installed`, and the present roster matches the manifest. Report missing profiles and a partial install as such. Model configuration, connected accounts, cron registration, Kanban bootstrap, and mission activation are separate from installed profiles.

## Pitfalls

- A same-version install does not overwrite the recorded profiles. A different version or incomplete record is not an upgrade request; report it and leave it intact. Never delete or overwrite a matching profile just to retry.
- An interrupted install can leave an `installing` record and some published profiles. Compare its roster with `status` and `hermes profile list` before discussing recovery. Do not create a replacement installation or remove its record or lock without authorization.
- This skill is preloaded on fresh root installations, not fresh named profiles. It is not the playbook orchestration skill used inside worker teams.

## Verification

Return the installed playbook version, orchestrator, agent IDs and versions, and the ledger path. Check installed skill IDs and independently confirm any integrations or jobs only if the user asks to set them up. Never describe an installed team as running solely because its YAML record exists.
