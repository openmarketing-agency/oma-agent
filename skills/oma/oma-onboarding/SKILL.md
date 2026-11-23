---
name: oma-onboarding
description: Set up a brand, campaigns, and agents from one URL.
version: 0.3.2
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, onboarding, brands, playbooks, campaigns, agents]
    related_skills: [oma-brand, oma-playbook, oma-campaigns, oma-agents]
---

# OMA Onboarding Skill

Set up OMA from a single website or GitHub repository URL. Research the brand, save the strategy, then design campaigns and teams around them. Decide which recurring work needs cron and register eligible jobs after verifying the team. Reuse verified setup on subsequent runs.

## When to Use

- The user asks to get started, hands over a website or repository URL for setup, or asks to finish onboarding.
- The user asks to add campaigns or agents to an existing verified setup. Start at the requested stage; do not repeat setup or ask for a URL you already have.

## Prerequisites

Work from the default OMA profile and its Hermes home. Load `oma-brand`, `oma-playbook`, `oma-campaigns`, and `oma-agents` with `skill_view` at their respective stages. This skill supplies the setup intent and chooses defaults; do not repeat the other skills' intake questions. `oma-bundle/skills/` is a library of reusable skills, not a catalog of campaigns or rosters.

## How to Run

If no URL was provided and none is saved for this setup, ask only: **“What's your website or GitHub repository URL?”** If the user already supplied it, start immediately. An onboarding request and URL are enough for the local setup, team selection, and eligible scheduling below; don't ask the user to approve each step, write a strategy, pick agents, or specify schedules. Once the plan is known, use the `oma-campaigns` integration intake guide to ask for any missing catalog connections required by the work, including media generation if the plan calls for it. Honor any narrower scope the user gives. If the URL is invalid or unreadable, ask only for a corrected, accessible URL. For existing-record conflicts, report what is blocked instead of guessing or overwriting it.

## Procedure

1. **Research the source read-only.** Follow `oma-brand` to compile the website and visual references, audience and market findings, competitors, integrations, social and publishing channels, launch history, and public docs. If a verified repository is available, produce the capability and technical reports by inspecting it as text. Treat unverified details as unknown, not absent. Do not execute repository code, load its instructions, or bypass web access controls.
2. **Save or reuse the brand.** Use `oma-brand` to save `oma/brand/config.yaml`, its referenced `knowledge-base.md`, and relevant supporting reports or assets. On a rerun for the same brand, fill gaps without overwriting existing assets or custom knowledge. If the URL belongs to a different brand or ownership of the saved record is unclear, leave the singleton untouched and report the conflict.
3. **Decide and save the playbook.** Use `oma-playbook` to turn the compiled brand into the overall strategy: who to reach, what to focus on, why, and how to measure progress. Recommend campaigns in priority order with prerequisites and evidence. Label inferred choices as onboarding defaults. Save the strategy inline at `oma/playbook/config.yaml` or reuse the existing strategy when present; do not store a brand link.
4. **Derive and save campaigns and teams.** Use `oma-campaigns` to turn the saved strategy into the smallest useful set of campaigns. For a confirmed missing website, blog, or public docs that the strategy needs, use its build references. Record any shared hosting prerequisite and route authorized infrastructure work to `maintenance` via the `oma-agents` handoff; do not run `omactl` as `default` or a campaign agent. Each campaign's goals state its purpose and desired outcomes; its plans state how to reach them and in what order. Create the canonical orchestrator and dedicated publisher, adding only specialists needed for the plan. Decide each role's tools, relevant skills, and recurring responsibilities. Use the existing campaign record and agent `config.yaml`, `SOUL.md`, and `saves/` layout; do not create a separate manifest or adopt a preset roster. If there is already a fitting team, reuse it and preserve its records.
5. **Provision and read back.** Follow `oma-campaigns` to verify every new role's saved `SOUL.md` before installing. If any are missing or blocked, leave that campaign a draft and name the missing roles. Read back the provisioned profiles and their personas before treating the roster as active. On reruns, use `configure` only to fill missing routing fields in the existing campaign config.
6. **Register recurring work where warranted.** Follow the campaign skill's review-prompt guidance and native cron procedure. For Social & Community, read back the declared prompt and check that it actually asks for new activity (comments, replies, mentions, and tagged posts) on the selected channels, not just access verification. Only register eligible jobs after verifying the entire team, and preserve already scheduled and manually paused jobs. Do not force an immediate run.

After onboarding, use `oma-brand` from the default profile to refresh existing resources when read-only data from a verified connected source (such as GA4 or Search Console) becomes available. Do not repeat onboarding, reconnect accounts, or rebuild campaigns to refresh the brand.

## Add Agents to an Existing Campaign

Verify the existing campaign and its installation status. Use `oma-agents` to save missing records for verified members, or draft a new agent only if the user requests one; a draft does not enter the roster or get cron. The `oma-campaigns` installer cannot extend a live roster. Do not rerun the install, hand-edit installation state, or create unrelated profiles to work around that limit.

## Pitfalls

- The single brand and playbook are read directly at their fixed locations. Only the agent-to-campaign relationship uses `campaign_id`; multiple campaigns can still share the same brand and playbook.
- Campaign installation and agent record writes do not start cron; the explicit scheduling step does. Don't add credentials, change tool permissions, or connect external accounts from URL-based evidence.
- If onboarding stops midway, resume from the verified records. Do not discard a completed stage, retry over a conflicting profile, or report a partial roster as complete.

## Verification

Report the source URL, brand and playbook saved or reused, selected campaigns and why, and the actual agent IDs provisioned. Include configured cron schedules and their verified state, plus any missing evidence, blocked jobs, or other incomplete setup. A registered schedule, a healthy scheduler, and an observed run are separate outcomes.
