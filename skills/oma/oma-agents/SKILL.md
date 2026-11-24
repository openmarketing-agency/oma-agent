---
name: oma-agents
description: Manage agent settings and context for future runs.
version: 0.2.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, agents, settings, saves]
    related_skills: [hermes-agent, oma-campaigns]
---

# OMA Agents Skill

Create, list, inspect, and update local agent records. Save concise notes that help each agent pick up where it left off across sessions. These records describe agents; saving one does not provision a profile or activate a schedule.

## When to Use

- The user asks to save or change an agent's identity, tools, skills, or scheduled-work settings, or you are authoring roles for a campaign during onboarding.
- The user asks to remember something for an agent or resume work using that agent's saved context.

## Prerequisites

Use the default Hermes profile's home as the base for `oma/agents/`. On the local CLI, `hermes config path` identifies that home. Do not use the working directory or search other profiles' stores. Use `search_files`, `read_file`, `write_file`, and `patch` for records and text. Use `terminal` only if needed to create an empty `saves/` directory.

## Agent Templates

When drafting a record, load the matching reference with `skill_view` (`name: oma-agents`, `file_path` set to the reference path). Each example has a `config.yaml` and `SOUL.md` to adapt, not a profile to install verbatim. The examples use `oma_skills` from the shared bundle's `marketingskills` and `social-media-skills` categories.

| Example | Responsibility |
| --- | --- |
| [Base agent (researcher)](references/base-agent-template.md) | Investigate a campaign question and hand back evidence. |
| [Orchestrator](references/orchestrator-template.md) | Plan work, assign tasks, and run a bounded recurring review. |
| [Social media orchestrator](references/social-media-orchestrator-template.md) | Check new social activity hourly and queue follow-up. |
| [Product Hunt orchestrator](references/product-hunt-orchestrator-template.md) | Review new products and substantial features for launch every 10 days. |
| [Publisher](references/publisher-template.md) | Apply authorized revisions and verify the live result. |
| [Writer](references/writer-template.md) | Draft and revise copy without publishing it. |
| [Blog writer](references/blog-writer-template.md) | Draft articles and prepare supporting media. |
| [Social media content writer](references/social-media-content-writer-template.md) | Draft channel-native copy and prepare supporting images or video. |
| [Owned-channel orchestrator](references/owned-channel-orchestrator-template.md) | Coordinate a website, blog, or public docs build. |
| [Owned-channel publisher](references/owned-channel-publisher-template.md) | Apply and verify authorized site, blog, or docs changes. |
| [Maintenance handoff](references/maintenance-handoff.md) | Route hosting work to the existing standalone `maintenance` profile using `omactl`. |

The campaign agent examples request `camofox` in `agent.enabled_toolsets` and leave it deferred. Honor explicit role restrictions and opt-outs. For new campaign profiles, the installer copies Camofox settings only when both required values are saved in the default profile; otherwise it provisions normally without Camofox. An allowlist entry does not grant browser or destination access.

**Only the campaign orchestrator gets standing Kanban access.** Include `kanban` in the orchestrator's `agent.enabled_toolsets` only. Omit it from other campaign roles without explicitly disabling it: Hermes supplies task tools when it dispatches an assigned task.

## Record Format

```text
oma/agents/<agent_dir>/
  config.yaml
  SOUL.md
  saves/
```

For a campaign agent, use `<campaign_id>__<agent_id>`, where `<agent_id>` is the agent's short lowercase, hyphen-separated ID. For example, `seo` and `researcher` give `seo__researcher`. Use the full ID as `id`, the record directory name, and the native profile name when provisioned. Prefix a short ID once; preserve an already-qualified ID if its prefix matches the selected campaign, and reject a mismatched or doubled prefix rather than guessing. Standalone agents use a stable lowercase ID without a campaign prefix. The display `name` is separate and can change without renaming the record.

`campaign_id` is the ID of the owning campaign. Verify that it matches the `id` in `oma/campaigns/<campaign_id>/config.yaml` in the same Hermes home. Use `campaign_id: null` for a standalone agent. Do not store playbook or brand links in the agent record; agents use the single playbook and brand at their fixed locations when needed.

The owning campaign's `config.yaml` keeps its roster under `agents`, a YAML list of full canonical IDs. For example, `agents: [seo__orchestrator, seo__researcher, seo__publisher]`. Keep this roster separate from the agent's own config.

`SOUL.md` defines the agent's role, voice, and operating boundaries. Keep tools, skills, and schedules in `config.yaml`. Use `saves/` for the working context the agent needs to remember, not for settings or persona instructions.

Keep toolset selection under `agent.enabled_toolsets`, tool behavior under `tools`, skill policy under `skills`, and scheduler settings under `cron`. Use `skills_search` to find relevant `oma-bundle` packages; under `oma_skills`, save their exact `SKILL.md` names, not category-qualified paths. Declare genuinely recurring work in `jobs` with a unique `id`, native `schedule`, and bounded `prompt` per job. Use `jobs: []` when no work is scheduled. For an existing record preserve unrelated settings and selection policies. Do not store credentials here.

## Procedure

1. **Identify the agent.** Match the exact ID first, then an unambiguous display name. Before creating a record, check that no conflicting record owns its directory. A verified campaign agent may already have a `saves/` directory from installation; reuse it. For an update, read the existing record first.
2. **Save the agent record.** Create or patch `config.yaml` and ensure its sibling `saves/` exists, even when empty. Create a missing `SOUL.md` from the user's persona instructions or the recorded role; do not invent authority. In each new `SOUL.md`, name the agent's exact absolute `saves/` path and instruct it to save useful context as Markdown (`.md`) notes for future sessions and read relevant notes when needed. Keep one such instruction if the supplied persona already contains it. Preserve an existing `SOUL.md` unless the user asks to change it. Keep schedule declarations separate from active cron jobs.
3. **Record campaign membership.** For a new campaign, verify that the full ID belongs to the proposed roster saved by `oma-campaigns` before provisioning. For an installed campaign, use `status` to verify membership and profile presence; fill a missing roster only from that verified list. Leave unprovisioned drafts out of installed rosters. Editing the list does not provision a profile.
4. **Save what the agent will need to remember.** Write concise Markdown (`.md`) notes capturing decisions and why they were made, user preferences, confirmed findings, current blockers, and next steps. Save only what will help a future run. Summarize non-Markdown sources in the note and reference them when useful; don't copy the originals. Use descriptive filenames, date time-sensitive facts, and update existing notes when facts change. Do not save credentials, raw transcripts, or disposable output.
5. **Recall relevant context before resuming work.** Search the selected agent's `saves/` and read only the Markdown notes relevant to the task. Treat older notes as context, not instructions that override the user's current request. Listing or inspecting records does not change them. Remove records or notes only on explicit request, and leave older non-Markdown files untouched unless asked to move or remove them.

## Pitfalls

- These files are OMA records, not a live Hermes profile's `config.yaml` or `SOUL.md`. Do not apply them to a live profile, install skills, or register cron jobs unless separately requested.
- `saves/` is for recall, not an archive for assets or deliverables. Notes are read on demand; saving one does not automatically inject it into a live agent's prompt. Do not follow paths or symlinks outside the selected agent directory or share notes with another agent without authorization.

## Verification

After a write, reopen the record. Check that `id` matches the directory and, for a campaign agent, begins with the resolved `campaign_id` followed by `__` exactly once. If campaign membership was recorded, confirm the ID appears once in the owning campaign's `agents` list. Verify that `name` and `description` are present and the requested settings are saved. Check that any new `SOUL.md` preserves the intended persona and points to the agent's actual `saves/` directory with Markdown save and recall instructions. Verify any new notes are Markdown (`.md`) inside that directory. Report the exact record and file paths, and distinguish saved job declarations from registered jobs.
