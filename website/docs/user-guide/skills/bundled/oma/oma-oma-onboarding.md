---
title: "Oma Onboarding — Set up a brand, campaigns, and agents from one URL"
sidebar_label: "Oma Onboarding"
description: "Set up a brand, campaigns, and agents from one URL"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Oma Onboarding

Set up a brand, campaigns, and agents from one URL.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/oma/oma-onboarding` |
| Version | `0.4.0` |
| Author | Open Marketing Agency (OMA) |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `oma`, `onboarding`, `brands`, `playbooks`, `campaigns`, `agents` |
| Related skills | [`oma-brand`](../../bundled/oma/oma-oma-brand.md), [`oma-playbook`](../../bundled/oma/oma-oma-playbook.md), [`oma-campaigns`](../../bundled/oma/oma-oma-campaigns.md), [`oma-agents`](../../bundled/oma/oma-oma-agents.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# OMA Onboarding Skill

Set up OMA from a website, public brand profile, or GitHub repository URL. Research the brand, save the strategy, and create paused campaigns with their teams and Kanban boards. Reuse verified setup on subsequent runs. Starting a campaign is a separate request.

## When to Use

- The user asks to get started, hands over a website, public social profile, or repository URL for setup, or asks to finish onboarding.
- The user asks to add campaigns or agents to an existing verified setup. Start at the requested stage; do not repeat setup or ask for a URL you already have.

## Prerequisites

Work from the default OMA profile and its Hermes home. Load `oma-brand`, `oma-playbook`, `oma-campaigns`, and `oma-agents` with `skill_view` at their respective stages. This skill supplies the setup intent and chooses defaults; do not repeat the other skills' intake questions. `oma-bundle/skills/` is a library of reusable skills, not a catalog of campaigns or rosters.

## How to Run

If no URL was provided and none is saved for this setup, ask only: **“What's your website, public brand profile, or GitHub repository URL?”** If the user already supplied it for onboarding, start local setup immediately, including paused campaign creation. This does not authorize starting campaigns or writing to external accounts. Don't ask the user to approve each local step, write a strategy, pick agents, or specify schedules. Honor any narrower scope the user gives. If a source is unreadable, try a verified first-party alternative before asking for another URL. If supplied URLs identify unrelated brands and there is no unambiguous match to the saved brand, ask which one to onboard. Do not merge them or replace an existing brand without confirmation.

## Procedure

1. **Research the source read-only.** Follow `oma-brand` to inventory and collect the distinct logos, illustrations, icons, backgrounds, images, and screenshots found on the reviewed public brand pages as part of setup, without waiting for a separate request. Treat public social profile URLs as brand sources: capture the accessible profile and follow verified official links for additional assets and page references, including when the platform blocks direct access. Compile the remaining audience, market, channel, integration, launch, and docs findings from available sources. If a verified repository is available, produce the capability and technical reports by inspecting it as text. Treat unverified details as unknown, not absent. Do not execute repository code, load its instructions, or bypass web access controls.
2. **Save or reuse the brand.** Use `oma-brand` to save `oma/brand/config.yaml`, its referenced `knowledge-base.md`, and relevant supporting reports or assets. On a rerun for the same brand, fill gaps without overwriting existing assets or custom knowledge. If the URL belongs to a different brand or ownership of the saved record is unclear, leave the singleton untouched and report the conflict.
3. **Decide and save the playbook.** Use `oma-playbook` to turn the compiled brand into the overall strategy: who to reach, what to focus on, why, and how to measure progress. Recommend campaigns in priority order with prerequisites and evidence. Label inferred choices as onboarding defaults. Save the strategy inline at `oma/playbook/config.yaml` or reuse the existing strategy when present; do not store a brand link.
4. **Design campaigns and teams.** Use the ideas catalog and worked plays in `oma-campaigns` to choose campaigns that fit the saved priorities. Record prerequisites in ordered `plans`, connector IDs in `integrations`, and personas and job declarations in the agent records. For shared hosting, follow the `oma-agents` maintenance handoff rather than adding `maintenance` to the roster.
5. **Provision and verify paused campaigns.** Follow the `oma-campaigns` creation procedure: use `create <definition.yaml>` for each new campaign, `install <id>` for an existing unprovisioned definition, and reuse verified installations without changing their lifecycle. Check `status <id>` for the complete team and the campaign's Kanban board. Missing account connections don't block local provisioning; direct the user to the OMA console for the connections still needed, never ask for credentials in chat. Don't resume campaigns, queue kickoff work, or register ordinary jobs during onboarding. Follow the separate activation procedure only when requested.

After onboarding, use `oma-brand` from the default profile to refresh existing resources when read-only data from a verified connected source (such as GA4 or Search Console) becomes available. Do not repeat onboarding, reconnect accounts, or rebuild campaigns to refresh the brand.

## Add Agents to an Existing Campaign

Verify the existing campaign and its installation status. Use `oma-agents` to save missing records for verified members, or draft a new agent only if the user requests one; a draft does not enter the roster or get cron. The `oma-campaigns` installer cannot extend a live roster. Do not rerun the install, hand-edit installation state, or create unrelated profiles to work around that limit.

## Pitfalls

- The single brand and playbook are read directly at their fixed locations. Only the agent-to-campaign relationship uses `campaign_id`; multiple campaigns can still share the same brand and playbook.
- New campaigns stay paused even if the installer provisions a managed analytics schedule. Don't add credentials or connect external accounts from URL-based evidence.
- If onboarding stops midway, resume from the verified records. Do not discard a completed stage, retry over a conflicting profile, or report a partial roster as complete.

## Verification

Report the source URL, brand and playbook saved or reused, and which campaigns were installed with a team and board. Say that new campaigns are paused. Report any failed provisioning as a blocker, not a completed setup, and list the access or prerequisites needed before starting.
