---
name: oma-campaigns
description: Install and inspect local OMA campaigns.
version: 0.3.1
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, campaigns, provisioning, profiles]
    related_skills: [hermes-agent]
---

# OMA Campaigns Skill

Use this skill in the default OMA Agent profile to design and provision campaigns from the saved brand and playbook. Each campaign has one orchestrator to plan and assign work on its Kanban board and a separate publishing agent to apply authorized content or edits. There are no campaign or agent templates.

## When to Use

- The user asks to create or provision a campaign, inspect an installed one, or save its goals or plans.

## Prerequisites

Resolve the default Hermes home with `hermes -p default config path`. Read `oma/brand/config.yaml` and `oma/playbook/config.yaml` from that home before designing a team. For record formats load `oma-agents` with `skill_view`. `oma-bundle/skills/` supplies reusable skills only; find them with `search_skills` and read relevant ones with `skill_view`. Do not look for campaign templates or use the onboarding URL as a source of executable definitions.

## How to Run

Use `terminal` to run `scripts/campaign.py` from the installed skill directory (`skills/oma/oma-campaigns/` under the default Hermes home, as reported by `skill_view`). Use `python3` on macOS/Linux and `python` on Windows. Quote paths containing spaces and stay in the default profile. If an older customized copy lacks the current launcher, use the current bundled launcher rather than modifying the custom copy.

| Arguments | What they do |
|---|---|
| `install <id>` | Provision the saved campaign and agent records, create the board, and install declared shared skills. |
| `list` | List installed or incomplete campaigns. |
| `status <id>` | Show the saved roster, provisioning state, and profiles verified against the campaign board. |
| `configure <id>` | Fill missing routing fields in the existing campaign config from the verified board and profiles. Does not reprovision agents or create a board. |
| `integrations` | List candidate integration IDs from observed brand integrations and verified social channels. Does not check account access. |
| `validate <kind> <path>` | Check a `brand`, `playbook`, `campaign`, or `agent` YAML record without applying it. |

## Campaign Config

Save the editable config at `oma/campaigns/<campaign_id>/config.yaml`. Use the campaign ID as the directory name. For example, not as a template to install verbatim:

```yaml
id: seo
name: SEO
description: Improve the site's organic visibility.
orchestrator: seo__orchestrator
agents:
  - seo__orchestrator
  - seo__researcher
  - seo__publisher
kanban_board: campaign-seo
kanban_board_name: SEO
integrations: [google-search-console, wordpress-com, google-analytics]
goals:
  - Help prospective buyers discover the product through organic search and increase qualified sign-ups from that channel.
plans:
  - First, review Search Console performance and prioritize topics and landing-page fixes that match buyer intent.
  - Then, publish the prioritized blog posts and apply the landing-page and internal-link edits on the brand's WordPress.com site.
  - After publication, review qualified organic visits and sign-ups in Google Analytics, then decide which pages to improve next.
```

- **Playbook — overall strategy:** `oma/playbook/config.yaml` defines what marketing should focus on and why across all campaigns. Use its priorities to decide which campaigns are needed, not as a list of tasks.
- **Campaign `goals` — purpose and outcomes:** Say why this campaign exists, what should change, and how to recognize success when measurable. Publishing a blog post is an action, not the outcome it serves.
- **Campaign `plans` — approach and sequence:** Say how the campaign will reach its goals: what to create, publish, or edit, on which channels, what must happen first, and how results will inform the next steps. Keep the campaign-level sequence here and let the orchestrator break it into Kanban tasks.

Goals and plans are inline YAML lists of text. Do not add a `playbook` field or rewrite older records just to remove it. Do not add `version` to campaign or agent records. The helper stores `installation_state` in the campaign config; do not set it by hand.

Use exactly one orchestrator, `<campaign_id>__orchestrator`, in the ordered `agents` list. Use canonical `<campaign_id>__<agent_id>` IDs unchanged and without duplicates. Before provisioning, the list is the proposed roster; after provisioning verify it against `present_profiles`. The helper fills missing `kanban_board` and `kanban_board_name`. Use the board slug in commands. Editing a record does not reconfigure an installed board or profile.

## Campaign Integrations

- Every campaign must declare a non-empty `integrations` list in its `config.yaml`. Use unique canonical OMA catalog IDs, not display names, URLs, or connector aliases. Select the smallest set that the campaign needs for its plans and measurement; don't copy the brand's entire inventory. If no catalog integration fits, leave the campaign unprovisioned and report the gap rather than adding an unrelated integration.
- Start with the saved brand's `integrations` and `channels` (social, blog, newsletter). Use `integrations` in the launcher to shortlist observed integrations and verified social channels. Compare what best serves the campaign with what the brand already uses. Prefer a verified, usable existing connection when it meets the need; if no existing connection meets the need, declare the best-fit required integration and report it as a setup blocker.
- Brand evidence and a saved integration ID do not prove access. Before activating the campaign or enabling its jobs, verify each required connection for the intended account or property and the owning profile's needed read or write permissions. If a required connection is missing or unverified, save the campaign without activating it or enabling jobs and report what must be connected. This is a skill check, not a gate enforced by the YAML validator or lifecycle command.

## Publishing Agent

- Include `<campaign_id>__publisher` in every new campaign roster, with its own `config.yaml` and `SOUL.md`. The publisher owns applying authorized changes to the campaign's destination: publishing new content, editing existing content, or applying a prepared change such as a website, CMS, or documentation edit. Assign research, drafting, and review separately as needed; the orchestrator decides the handoffs on Kanban.
- Give the publisher only the tools and authorized destinations it needs. Before publishing or editing, verify the destination and the exact version or change to apply, and satisfy any required review. Read it back afterward and record the resulting URL, revision, or other confirmation on the task. If access, authorization, or a required review is missing, leave the work unpublished and report the blocker. A publishing role does not itself authorize a live change or require a cron job.
- If an installed campaign lacks a verified publishing agent, report the gap. Do not append a draft to its installed roster, assign publishing to another role as a workaround, or rerun `install` to try to extend the team.

## Schedule the Orchestrator

- Give every campaign a recurring review owned by `<campaign_id>__orchestrator`. Declare it in that agent's `jobs` list with a stable ID such as `campaign-review`, a native Hermes `schedule`, and a bounded `prompt`. Use the user's cadence when specified. Otherwise, choose the slowest cadence that meets the campaign's response needs, given data freshness, rate limits, and run cost. Reuse an existing equivalent job and preserve operator pauses.
- Name the checks in the saved `prompt` itself. For Social & Community, tell the orchestrator to read new comments and replies on the brand's posts, @mentions and tagged posts, and any relevant community threads. Include inbox messages only where the campaign covers them and read access is authorized. Name the verified channels/accounts and their available read tools; verifying access or reading engagement totals is not a substitute for checking activity. For other campaigns, use their own signals (e.g. search performance for SEO).
- Each review checks the saved goals and plans, the campaign's Kanban board, and new evidence since the last review. Decide what to continue, change, or queue; propose changes outside the orchestrator's authority and route authorized publication or edits to the publisher. Record material decisions and stop without creating duplicate tasks or rewriting plans when nothing meaningful changed. When data or access is missing, note the gap rather than inventing a trend.

Example Social & Community review prompt (replace the channel and account with the campaign's own verified targets):

> On the connected account `example` on LinkedIn, check new comments and replies on our posts, @mentions, and posts tagging the brand since the last successful check. Record the links or item IDs and keep a checkpoint for each source in your saves notes. If a source can't be read, report what wasn't checked and don't advance its checkpoint. Compare actionable items with the campaign goals, plan, and open Kanban tasks. Queue only new follow-up work; route authorized replies or edits to the publisher. Do not post or send messages from this review. Record material decisions and stop.

## Procedure

1. **Derive campaigns from the strategy.** Read the singleton playbook's priorities and recommendations alongside the compiled brand. Choose the smallest set of campaigns that advances those priorities, considering channel fit, existing work, prerequisites, and verified capabilities. For each, identify the strategic priority it serves, write a distinct outcome in `goals`, and put the actions and their order in `plans`. Include the orchestrator and publisher, then add only specialists with distinct responsibilities and handoffs. Use `list` and `status` first on a rerun; reuse installed teams and preserve edits, notes, and manual pauses rather than creating duplicates.
2. **Save the campaign and agent records.** Select and save the required `integrations` as described above. Use `write_file` or `patch` for the campaign config and each `oma/agents/<agent-id>/config.yaml` and `SOUL.md`. Record canonical `id`, `name`, `description`, and `campaign_id` for each role; use the same ID for the future profile. Give the orchestrator responsibility for deciding Kanban tasks and handoffs rather than hardcoding a pipeline. Choose only needed toolsets and existing shared skills; use `oma_skills` for exact package IDs to install, or `[]` for none. Keep `saves/` and link each persona to its own absolute saves path. Never copy credentials or grant authority inferred from a website.
3. **Declare the orchestrator review and any other recurring work.** Follow the review guidance above. Assign each other genuine recurring obligation to exactly one role. A specialist can own an independent check it can actually perform; do not schedule it to duplicate the orchestrator's review. Leave one-off work, handoffs, and event-driven work on Kanban. Save `jobs: []` for unscheduled specialists. For each job use a stable `id`, a native Hermes `schedule`, and a bounded `prompt` with clear stop conditions; add `timezone` or positive `repeat` only when needed. Do not add per-job skills, scripts, or remote delivery.
4. **Provision and verify.** For a new campaign, use `read_file` to verify that every ID in `agents` has a nonempty, role-specific `oma/agents/<agent-id>/SOUL.md` beside its `config.yaml`, with the correct saves path. YAML validation alone doesn't check the persona. If a write was blocked or a file is missing, report the affected role and leave the campaign a draft. Do not bypass the block or substitute `default`'s SOUL. Once the records are complete, run `install <id>`. Before enabling jobs, check that `status <id>` reports `installed`, the expected orchestrator and board, and a complete `present_profiles` list; resolve each profile's home via `hermes -p <agent-id> config path` and verify its adjacent `SOUL.md`. The helper wires the same board into the team without switching the shared current board. It does not start turns, copy launch credentials, create jobs, or seed tasks. Use `configure <id>` to fill missing routing fields in the existing config without reinstalling.
5. **Register eligible jobs.** After verifying required integration access, use each verified owning profile's native cron commands in the next section when provisioning includes scheduling. When editing only goals or plans, patch those fields without registering jobs or starting campaign work.

## Register Campaign Cron Jobs

1. Read `jobs` from each verified owning agent's `oma/agents/<agent-id>/config.yaml`. List the owning profile's jobs with `terminal` and `hermes -p <agent-id> cron list --all`. Match by the exact existing declaration ID or the stable native name `oma:<declared-id>`. Preserve active, completed, and operator-paused jobs. If identity or state is unclear, report it instead of creating a duplicate or resuming a job.
2. Use `hermes -p <agent-id> cron create --name 'oma:<declared-id>' --deliver local -- <schedule> <prompt>` for a missing eligible job. Pass schedule and prompt as separate literal arguments. Put any validated `--timezone` or `--repeat` before `--`; omit unset options. Do not use `cron run` or edit the job store by hand. Register only work the owning profile can perform. Only enable jobs that make external changes if the integration, target, and standing authorization are already verified; otherwise leave them unscheduled and report why. A URL alone does not authorize publication, messaging, or external modifications.
3. Read back the job and its state in the owning profile with `cron list --all`; check scheduler health with `cron status`. If the gateway is not serving that profile, report the schedule as waiting without starting or restarting services.

## Pitfalls

- A missing optional skill does not prevent authoring a team that does not need it. Never look for another campaign template or fetch a cached release.
- Installing an already recorded campaign does not replace its board, tasks, or profiles. Older campaigns installed without a board are not retrofitted by `configure`. If a board slug is already occupied by another board or an installation is incomplete, report the conflict; do not delete anything to retry.

## Verification

Check that the saved campaign declares a non-empty `integrations` list and that each ID serves a need in the plan or its measurement. Report any missing declaration on existing campaigns during inspection; don't silently change their records or running state. Report which required connections were verified and which still block activation.

Verify the campaign config, the canonical roster (including the orchestrator and publisher), the agent records and saves paths, and the routing from `status <id>`. Check that the publisher's persona specifies what it can publish or edit and that its profile appears in `present_profiles` after provisioning. Read the saved orchestrator job prompt and confirm it names the channels and tells the agent what activity to check; if scheduling was in scope, verify the registered prompt, cadence, and state in the orchestrator's own cron store. New agents get a `tmp/` directory beside their `config.yaml` for scratch files. Report what was provisioned, which jobs were registered or skipped, and any blockers. A saved job, an enabled job, a healthy scheduler, and an observed run are separate outcomes.
