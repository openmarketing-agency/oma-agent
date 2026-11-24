---
name: oma-onboarding
description: Set up a brand, campaigns, and agents from one URL.
version: 0.4.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, onboarding, brands, playbooks, campaigns, agents]
    related_skills: [oma-brand, oma-playbook, oma-campaigns, oma-agents]
---

# OMA Onboarding Skill

Set up OMA from a website, public brand profile, or GitHub repository URL. Research the brand, save the strategy, and draft campaigns and teams around it. Reuse verified setup on subsequent runs. Activation is a separate request.

## When to Use

- The user asks to get started, hands over a website, public social profile, or repository URL for setup, or asks to finish onboarding.
- The user asks to add campaigns or agents to an existing verified setup. Start at the requested stage; do not repeat setup or ask for a URL you already have.

## Prerequisites

Work from the default OMA profile and its Hermes home. Load `oma-brand`, `oma-playbook`, `oma-campaigns`, and `oma-agents` with `skill_view` at their respective stages. This skill supplies the setup intent and chooses defaults; do not repeat the other skills' intake questions. `oma-bundle/skills/` is a library of reusable skills, not a catalog of campaigns or rosters.

## How to Run

If no URL was provided and none is saved for this setup, ask only: **“What's your website, public brand profile, or GitHub repository URL?”** If the user already supplied it, start local setup immediately. A URL authorizes research and drafting, not campaign activation or external writes. Don't ask the user to approve each local step, write a strategy, pick agents, or specify schedules. Honor any narrower scope the user gives. If a source is unreadable, try a verified first-party alternative before asking for another URL. If supplied URLs identify unrelated brands and there is no unambiguous match to the saved brand, ask which one to onboard. Do not merge them or replace an existing brand without confirmation.

## Procedure

1. **Research the source read-only.** Follow `oma-brand` to inventory and collect the distinct logos, illustrations, icons, backgrounds, images, and screenshots found on the reviewed public brand pages as part of setup, without waiting for a separate request. Treat public social profile URLs as brand sources: capture the accessible profile and follow verified official links for additional assets and page references, including when the platform blocks direct access. Compile the remaining audience, market, channel, integration, launch, and docs findings from available sources. If a verified repository is available, produce the capability and technical reports by inspecting it as text. Treat unverified details as unknown, not absent. Do not execute repository code, load its instructions, or bypass web access controls.
2. **Save or reuse the brand.** Use `oma-brand` to save `oma/brand/config.yaml`, its referenced `knowledge-base.md`, and relevant supporting reports or assets. On a rerun for the same brand, fill gaps without overwriting existing assets or custom knowledge. If the URL belongs to a different brand or ownership of the saved record is unclear, leave the singleton untouched and report the conflict.
3. **Decide and save the playbook.** Use `oma-playbook` to turn the compiled brand into the overall strategy: who to reach, what to focus on, why, and how to measure progress. Recommend campaigns in priority order with prerequisites and evidence. Label inferred choices as onboarding defaults. Save the strategy inline at `oma/playbook/config.yaml` or reuse the existing strategy when present; do not store a brand link.
4. **Design and save campaigns and teams.** Use the ideas catalog and worked plays in `oma-campaigns` to choose campaigns that fit the saved priorities. Reuse existing records. Record prerequisites in ordered `plans`, connector IDs in `integrations`, and personas and jobs in the existing agent records. A worked play is not a new campaign format. For shared hosting, follow the `oma-agents` maintenance handoff rather than adding `maintenance` to the roster.
5. **Verify drafts and hand off.** Follow `oma-campaigns` to validate the records and read back each new role's `SOUL.md`. Report missing access, roles or prerequisites. Direct the user to the OMA console for required connections, never ask for credentials in chat. Don't install teams, queue work or register cron during onboarding. If the user explicitly requests activation, follow the separate `oma-campaigns` activation procedure.

After onboarding, use `oma-brand` from the default profile to refresh existing resources when read-only data from a verified connected source (such as GA4 or Search Console) becomes available. Do not repeat onboarding, reconnect accounts, or rebuild campaigns to refresh the brand.

## Add Agents to an Existing Campaign

Verify the existing campaign and its installation status. Use `oma-agents` to save missing records for verified members, or draft a new agent only if the user requests one; a draft does not enter the roster or get cron. The `oma-campaigns` installer cannot extend a live roster. Do not rerun the install, hand-edit installation state, or create unrelated profiles to work around that limit.

## Pitfalls

- The single brand and playbook are read directly at their fixed locations. Only the agent-to-campaign relationship uses `campaign_id`; multiple campaigns can still share the same brand and playbook.
- Campaign installation and agent record writes do not start cron; the explicit scheduling step does. Don't add credentials, change tool permissions, or connect external accounts from URL-based evidence.
- If onboarding stops midway, resume from the verified records. Do not discard a completed stage, retry over a conflicting profile, or report a partial roster as complete.

## Verification

Report the source URL, brand and playbook saved or reused, selected campaigns and why, and missing access or prerequisites. Distinguish drafted agents and declared schedules from installed profiles and registered jobs. Do not report a draft as started.
