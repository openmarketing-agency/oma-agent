---
name: oma-playbook
description: Manage the brand's playbook and strategy.
version: 0.6.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, playbooks, strategy, planning]
    related_skills: [oma-brand, oma-campaigns]
---

# OMA Playbook Skill

Create, inspect, and update the single marketing playbook for the saved brand. It describes whom to reach, how the brand wins, and how to measure progress. It guides campaign selection without owning campaign rosters, individual deliverables, or schedules.

## When to Use

- The user asks to save, find, revise, or remove the brand strategy.
- Onboarding needs an initial strategy and campaign recommendations grounded in the compiled brand.

## Prerequisites

Resolve the default Hermes home with `hermes -p default config path`. Read `oma/brand/config.yaml`, its knowledge base, and relevant research, including market and competitor evidence, conversion paths, documentation, channels, and launches. Read referenced files only within `oma/brand/`. Inspect existing `oma/campaigns/` records so the strategy can recommend extending useful work. If the brand is missing, use `oma-brand` first.

## Record Format

Save the singleton at `oma/playbook/config.yaml` using the existing `id`, `name`, `description`, and `strategy` fields. Keep the stable ID and the fixed path; do not add a `brand_id` or a separate strategy file. `strategy` is inline text, typically a YAML block scalar; use `strategy: ""` if no strategy was requested or supplied. No required status line, headings, or source footer. See the [worked example](references/examples.md).

## Procedure

1. **Read before writing.** Reuse the saved strategy on onboarding reruns unless revision is in scope. If the user asks for a second playbook, explain the singleton limit and confirm whether they mean to replace the current strategy.
2. **Ground the strategy in the brand.** Briefly cover what the product is, its positioning, who it serves, and the outcome marketing can influence. Explain why buyers would choose it over alternatives without narrowing its audience or inventing evidence. Unchecked channels are unknown, not absent; detected instrumentation does not establish working reporting or access.
3. **Choose priorities and channels.** Explain what to build on, why, what must happen first, and what to defer. Give each channel a job and each audience a useful message within the same brand story. Include durable content themes, voice, and evidence-backed claims. Put the weight on strategic choices rather than reciting research.
4. **Define success.** Name a primary business outcome and supporting measures for each priority. Separate reach, adoption, and revenue where relevant. Identify tracking and proof gaps; set targets only when grounded in a baseline. Say what material changes would trigger a strategy review.
5. **Recommend campaigns, not execution.** Name the smallest useful set of campaigns, the priority each serves, and its prerequisites. Extend an existing campaign where it fits. Hand off execution design to `oma-campaigns`, which uses the ideas catalog and plays as references. Do not create campaign records, agents, or jobs when only drafting a playbook.
6. **Save and check.** Use `write_file` or `patch` on the fixed record. Preserve unrelated fields and do not migrate older records just to remove legacy metadata. Reopen with `read_file` and run the installed campaign helper's `validate playbook <path>` through `terminal`. Only remove the record on explicit request; don't follow paths outside `oma/playbook/`.

## Pitfalls

- Drafting or saving strategy does not authorize execution or make it approved.
- A list of channels is not a strategy. State what the brand will do differently, for whom, and why that should improve its business outcome.
- Don't turn unverified markets, performance targets, or claims into facts. Put operational cadence and team design in campaigns, not the playbook.

## Verification

Confirm the existing fields and requested inline text were saved. Report the strategic focus, priorities, recommended campaigns, and open prerequisites. Distinguish recommendations from provisioned work and do not reformat existing strategy just to match an example.
