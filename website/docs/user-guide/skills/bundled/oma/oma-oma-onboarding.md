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
| Version | `0.6.0` |
| Author | Open Marketing Agency (OMA) |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `oma`, `onboarding`, `brands`, `playbooks`, `campaigns`, `agents` |
| Related skills | [`oma-brand`](../../bundled/oma/oma-oma-brand.md), [`oma-creatives`](../../bundled/oma/oma-oma-creatives.md), [`oma-competitors`](../../bundled/oma/oma-oma-competitors.md), [`oma-playbook`](../../bundled/oma/oma-oma-playbook.md), [`oma-campaigns`](../../bundled/oma/oma-oma-campaigns.md), [`oma-agents`](../../bundled/oma/oma-oma-agents.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# OMA Onboarding Skill

Set up OMA from a website, public brand profile, or GitHub repository URL in stages on the `oma-onboarding` Kanban board, one stage per card, so each stage gets a fresh context and finishes only when its check passes. The first stage researches the brand, its market, and its own posts, saves the strategy, and creates its campaigns as drafts with their agents named, then waits for the user's confirmation. Once they confirm, it captures the brand's visuals, builds the design system, refreshes the strategy, writes each campaign's agents and plan, and installs and starts the campaigns. Competitor research and ads are separate stages that run only when the user asks for them. Repositories are never cloned or analysed. This session plans the board, extends it, and reports on it; it does not do the stages itself.

## When to Use

- The user asks to get started, hands over a website, public social profile, or repository URL for setup, asks how onboarding is going, or confirms that onboarding should continue.
- The user asks for competitor research, or a generation task needs competitor evidence that `research/competitors.md` does not have yet.
- The user asks for ads (the brand's own, or competitors'), or a generation task needs ad evidence the creatives records do not have yet.
- The user asks to add campaigns or agents to an existing verified setup. Start at the requested stage; do not repeat setup or ask for a URL you already have.

## Prerequisites

Work from the default OMA profile. The Kanban dispatcher runs inside the gateway (always on in the Docker image) and starts each card as a worker of the default profile. Run the board script with `terminal` and the Hermes environment's Python: `python3 <skill_dir>/scripts/board.py`, using the `skill_dir` from `skill_view`. The stage skills (`oma-brand`, `oma-creatives`, `oma-competitors`, `oma-playbook`, `oma-campaigns`, `oma-agents`) are loaded by the cards, not here.

## How to Run

If no URL was provided and none is saved for this setup, ask only: **“What's your website, public brand profile, or GitHub repository URL?”** If the user already supplied it, start immediately. This does not authorize starting campaigns or writing to external accounts. Don't ask the user to approve local steps, write a strategy, pick agents, or specify schedules. If supplied URLs identify unrelated brands and there is no unambiguous match to the saved brand, ask which one to onboard; do not merge them or replace an existing brand without confirmation.

## Procedure

1. **Check for a board in progress.** Run `board.py status <home>`. If onboarding cards exist, report progress (step 4) instead of starting over; if `awaiting_confirmation` is true, also say that the rest runs once they confirm.
2. **Start the board.** Run `board.py start <home> --url <url>`. Add `--synthesis-model <model>` only when the user or operator asked for a different model for the strategy and campaign cards. The command is idempotent: on a rerun it returns the existing cards.
3. **Report and end the turn.** Tell the user the board is running in the background, list its stages, and say that it ends with the strategy and the campaigns created as drafts, and that their agents are written and the campaigns started once they confirm. Do not do any card's work in this session, and do not wait in a loop.
4. **On a status request,** run `board.py status <home>` and summarize: the stage, cards done, running, and waiting; for a `blocked` card, its failure reason and what would unblock it (a missing access, a source to retry later). Unblock a card with `hermes kanban --board oma-onboarding unblock <id>` only after the cause is fixed.
5. **When the first stage is done,** report as in Verification, and say that onboarding is waiting for their confirmation.
6. **On confirmation** (the user, or the app on their behalf, says to continue), run `board.py confirm <home>`. It adds the deferred cards, wired to the cards they need, and schedules the campaigns' installation and start; it is idempotent. Report the stages it added and end the turn.
7. **When the deferred stage is done,** `status` shows `provisioned` with each campaign's install state; report as in Verification. If a campaign is not `installed`, or the campaign cards are done and nothing was provisioned (the gateway's cron scheduler is not running), run `board.py provision <home>` in this session and report its result.
8. **On a request for competitor research,** run `board.py competitors <home>`. It adds discovery, profiles of the top five direct competitors, their posts, and the landscape. Never add it unasked.
9. **On a request for ads,** run `board.py ads <home>`. It adds the brand's ads and, when competitor research is on the board, the five competitors' ads and a landscape update with them; asked again after competitor research, it adds just the competitors' ads. Competitor research never collects ads. Never add either unasked.

Both on-request commands are idempotent. Report the cards a command added and end the turn.

Card workers cannot change the board, so a card whose target comes from an earlier card is a fixed slot: the worker runs `board.py brief` to get its instructions, and an empty slot completes on its own. Installing a campaign creates its Kanban board, which a card cannot do either, so `confirm` registers a script-only cron job that runs `board.py provision` every ten minutes: once every campaign card is done, it replaces each draft with its staged definition, installs it, starts it, and removes itself.

**First stage** (`start`):

| Stage | Card | Waits for |
| --- | --- | --- |
| Brand | brand core (website, every platform's profile status, launches, integrations, technologies, docs) | — |
| Brand | market research | brand core |
| Creatives | the brand's own posts, labels, and summary; its ad libraries are recorded as deferred | brand core |
| Strategy | playbook; it names the campaigns and their agents' roles and saves them as drafts with `board.py campaigns` | brand core, market, the brand's posts |

**After confirmation** (`confirm`):

| Stage | Card | Waits for |
| --- | --- | --- |
| Brand | screenshots and visual assets | brand core |
| Brand | design system | visual assets, the brand's posts |
| Strategy | playbook refresh | the playbook, design system |
| Campaigns | one slot per draft campaign (up to five): its agents' configs and souls, goals, plans, and schedules; then the cron job installs and starts the campaigns | playbook refresh |

**Competitor research, on request** (`competitors`):

| Stage | Card | Waits for |
| --- | --- | --- |
| Competitors | discovery (every source, up to 30 candidates), with the top five direct competitors at `full` depth | brand core |
| Competitors | five profile and teardown slots | discovery |
| Creatives | posts, labels, and summary for each of the five; their ad libraries are recorded as deferred | that slot's profile |
| Competitors | landscape, against the validator with `--full 5 --light 0` | every profile and posts card, the brand's posts |

**Ads, on request** (`ads`):

| Stage | Card | Waits for |
| --- | --- | --- |
| Creatives | the brand's ads and labels, replacing the deferred records | the brand's posts |
| Creatives | each of the five competitors' ads and labels (when competitor research is on the board) | that competitor's posts, the landscape |
| Competitors | landscape with ads (when competitor research is on the board) | every ads card |

If cards stay `ready` for more than five minutes with none `running`, the dispatcher is not running: ask the user to start the gateway, or run one pass with `hermes kanban --board oma-onboarding dispatch`. Do not run the stages in this session instead.

After onboarding, use `oma-brand` from the default profile to refresh resources when read-only data from a verified connected source (such as GA4 or Search Console) becomes available. Do not repeat onboarding, reconnect accounts, or rebuild campaigns to refresh the brand.

## Add Agents to an Existing Campaign

Verify the existing campaign and its installation status. Use `oma-agents` to save missing records for verified members, or draft a new agent only if the user requests one; a draft does not enter the roster or get cron. The `oma-campaigns` installer cannot extend a live roster. Do not rerun the install, hand-edit installation state, or create unrelated profiles to work around that limit.

## Pitfalls

- The single brand and playbook are read directly at their fixed locations. Only the agent-to-campaign relationship uses `campaign_id`; multiple campaigns can still share the same brand and playbook.
- Onboarding starts the campaigns only after the user confirms and their cards are done; until then they are drafts. Don't add credentials or connect external accounts from URL-based evidence: a started campaign reports the connections it still needs.
- Cards write the config only through `board.py merge-config`; a card that edits `config.yaml` directly can overwrite a parallel card's keys.
- A card that could not pass its check is blocked, and the cards after it wait. Report the blocker; do not complete the card by hand or redo its stage here.

## Verification

After the first stage, report the source URL, the brand and playbook saved or reused, the brand's own posts coverage (including `limited` and `blocked` sources and why), and the draft campaigns with their named agents and prerequisites, and say what runs after confirmation. After the deferred stage, report the design system, the refreshed strategy, and each campaign installed and started with its team and board; report any failed installation as a blocker, and list the access or connections each campaign still needs. After competitor research, report the five competitors and their posts coverage per source; after the ads stage, the ads coverage per library for the brand and each competitor.
