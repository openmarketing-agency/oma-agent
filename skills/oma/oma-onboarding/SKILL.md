---
name: oma-onboarding
description: Set up a brand, campaigns, and agents from one URL.
version: 0.6.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, onboarding, brands, playbooks, campaigns, agents]
    related_skills: [oma-brand, oma-creatives, oma-competitors, oma-playbook, oma-campaigns, oma-agents]
---

# OMA Onboarding Skill

Set up OMA from a website, public brand profile, or GitHub repository URL: research the brand, its creatives and competitors, save the strategy, and create paused campaigns with their teams and Kanban boards. The work runs as a graph of cards on the `oma-onboarding` Kanban board, one stage per card, so each stage gets a fresh context and finishes only when its check passes. This session plans the board and reports on it; it does not do the stages itself. Starting a campaign is a separate request.

## When to Use

- The user asks to get started, hands over a website, public social profile, or repository URL for setup, or asks how onboarding is going or to finish it.
- The user asks to add campaigns or agents to an existing verified setup. Start at the requested stage; do not repeat setup or ask for a URL you already have.

## Prerequisites

Work from the default OMA profile. The Kanban dispatcher runs inside the gateway (always on in the Docker image) and starts each card as a worker of the default profile. Run the board script with `terminal` and the Hermes environment's Python: `python3 <skill_dir>/scripts/board.py`, using the `skill_dir` from `skill_view`. The stage skills (`oma-brand`, `oma-creatives`, `oma-competitors`, `oma-playbook`, `oma-campaigns`, `oma-agents`) are loaded by the cards, not here.

## How to Run

If no URL was provided and none is saved for this setup, ask only: **“What's your website, public brand profile, or GitHub repository URL?”** If the user already supplied it, start immediately. This does not authorize starting campaigns or writing to external accounts. Don't ask the user to approve local steps, write a strategy, pick agents, or specify schedules. If supplied URLs identify unrelated brands and there is no unambiguous match to the saved brand, ask which one to onboard; do not merge them or replace an existing brand without confirmation.

## Procedure

1. **Check for a board in progress.** Run `board.py status <home>`. If onboarding cards exist and are not all done, report progress (step 4) instead of starting over.
2. **Start the board.** Run `board.py start <home> --url <url>`, adding `--repo <url>` when the user gave a repository or the brand is a repository. Add `--synthesis-model <model>` only when the user or operator asked for a different model for the strategy and campaign cards. The command is idempotent: on a rerun it returns the existing cards.
3. **Report and end the turn.** Tell the user the board is running in the background, list its stages, and say that campaigns are created paused at the end. Do not do any card's work in this session, and do not wait in a loop.
4. **On a status request,** run `board.py status <home>` and summarize: cards done, running, and waiting; for a `blocked` card, its failure reason and what would unblock it (a missing access, a source to retry later). Unblock a card with `hermes kanban --board oma-onboarding unblock <id>` only after the cause is fixed.
5. **When the provisioning card is done,** report as in Verification.

The card graph `start` creates (the discovery and playbook cards add the rest):

| Stage | Card | Waits for |
| --- | --- | --- |
| Brand | brand core (website, every platform's profile status, launches, integrations, technologies, docs) | — |
| Brand | repository analysis (when there is a repository) | brand core |
| Brand | screenshots and visual assets; market research | brand core |
| Creatives | the brand's own posts, then its ads, labels, and summary | brand core |
| Competitors | discovery, scoring, and tiers; it adds a profile card and two creatives cards per top-5 direct competitor, one card for the indirect profiles, and creatives cards per reference | brand core |
| Competitors | patterns, landscape, and validation | every competitor card, the brand's creatives |
| Brand | design system | visual assets, the brand's creatives |
| Strategy | playbook; it chooses the campaigns and adds one design card per campaign | brand core, repository, market, landscape, design system |
| Campaigns | provisioning of paused teams | every campaign design card |

If cards stay `ready` for more than five minutes with none `running`, the dispatcher is not running: ask the user to start the gateway, or run one pass with `hermes kanban --board oma-onboarding dispatch`. Do not run the stages in this session instead.

After onboarding, use `oma-brand` from the default profile to refresh resources when read-only data from a verified connected source (such as GA4 or Search Console) becomes available. Do not repeat onboarding, reconnect accounts, or rebuild campaigns to refresh the brand.

## Add Agents to an Existing Campaign

Verify the existing campaign and its installation status. Use `oma-agents` to save missing records for verified members, or draft a new agent only if the user requests one; a draft does not enter the roster or get cron. The `oma-campaigns` installer cannot extend a live roster. Do not rerun the install, hand-edit installation state, or create unrelated profiles to work around that limit.

## Pitfalls

- The single brand and playbook are read directly at their fixed locations. Only the agent-to-campaign relationship uses `campaign_id`; multiple campaigns can still share the same brand and playbook.
- New campaigns stay paused even if the installer provisions a managed analytics schedule. Don't add credentials or connect external accounts from URL-based evidence.
- Cards write the config only through `board.py merge-config`; a card that edits `config.yaml` directly can overwrite a parallel card's keys.
- A card that could not pass its check is blocked, and the cards after it wait. Report the blocker; do not complete the card by hand or redo its stage here.

## Verification

Report the source URL, the brand and playbook saved or reused, the creatives coverage per target (including `limited` and `blocked` sources and why), and which campaigns were installed with a team and board. Say that new campaigns are paused. Report any failed provisioning as a blocker, and list the access or prerequisites needed before starting.
