---
name: oma-playbook
description: Manage the brand's playbook and strategy.
version: 0.2.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, playbooks, strategy, planning]
    related_skills: [oma-brand, oma-campaigns]
---

# OMA Playbook Skill

Create, inspect, and update the single marketing playbook for the saved brand. It records the overall strategy: who to reach, what to focus on, why, and how to measure progress. It guides campaign selection without owning campaign goals, execution plans, or agent rosters.

## When to Use

- The user asks to save, find, revise, or remove a playbook or its strategy.
- The user asks for the brand's approved strategy.
- Onboarding needs an initial strategy and campaign recommendations grounded in the compiled brand.

## Prerequisites

Use the default profile's Hermes home as the base for `oma/playbook/`. On the local CLI, `hermes -p default config path` identifies that home. Use `read_file`, `write_file`, and `patch` for the record. Before drafting or reassessing strategy, read `oma/brand/config.yaml` and its relevant compiled research. If the brand is missing, offer to set it up with `oma-brand` first.

## Record Format

Save the one playbook at `oma/playbook/config.yaml`. Keep its stable lowercase, hyphen-separated `id` independent of the display `name`; campaigns use the fixed path, not an ID link. Do not add a `brand_id` field: this playbook applies to the single brand in the same Hermes home.

`strategy` is the strategy text itself. Use a YAML block scalar for multiline content, not a filename or link to a separate strategy document. If the user has not supplied or asked you to draft a strategy, use `strategy: ""` and report it as unset.

## Playbook Templates

Use the [Presenton worked example](references/presenton-example.md) as the model for a complete playbook. Load it with `skill_view` (`name: oma-playbook`, `file_path: references/presenton-example.md`). For a different business model, load the relevant reference as well:

| Template | Use for |
| --- | --- |
| [B2B SaaS](references/b2b-saas-template.md) | Qualified trials or demos and product adoption. |
| [Open source](references/open-source-template.md) | Developer adoption through docs, releases, and existing communities. |
| [Ecommerce](references/ecommerce-template.md) | Product discovery, completed purchases, or repeat orders. |

Keep the following sections inside the inline `strategy` value, not as new YAML keys. Adapt them to the saved brand evidence and user constraints:

1. **What the product is:** Explain what it does and what users get in plain language.
2. **Positioning:** Name the main reason to choose it over alternatives and the evidence behind that difference.
3. **Who we market to:** Explain what each material audience needs and how it contributes to adoption, reach, or revenue. Keep one brand story; tailor the angle by audience.
4. **What success looks like:** Describe the progression from discovery to meaningful use and, where relevant, revenue or another business outcome.
5. **Channels and their roles:** Give each priority channel a distinct job. Separate ongoing work, release or proof amplifiers, and deferred channels. Name what would justify revisiting a deferred channel.
6. **What we talk about:** List durable themes and the demonstrations, workflows, or customer evidence that support them.
7. **Voice:** State how to write and what to avoid, including any differences by audience or channel.
8. **Measuring progress:** Connect each channel to downstream outcomes. Separate reach, adoption, and commercial measures where relevant; record attribution and data gaps without guessing.
9. **Claims:** Limit claims to what current, approved evidence supports. State what must not be claimed and how to handle comparisons.

Close with the material changes that should trigger a strategy review. Keep editorial calendars, individual deliverables, weekly decisions, agent rosters, and schedules in campaigns. The examples do not create additional records or authorize campaign execution.

## Build Strategy from the Compiled Brand

1. **Inventory the brand evidence.** Read the file referenced by `knowledge_base_file` (fall back to legacy inline `knowledge_base`), plus relevant market, competitor, and integration reports and summaries of product or repository documentation. Review the audience, positioning, product readiness, and usable assets. Check `website` and its conversion path; `channels.social`, `channels.blog`, and `channels.newsletter`; `documentation` and whether docs are public or internal; `integrations` for analytics, tracking, ads, and other tooling; and `launches` for Product Hunt and other launch platforms or marketplaces. Read referenced files only within `oma/brand/`.
2. **Distinguish facts from gaps.** An omitted or unchecked channel or launch is unknown, not absent. Use a recorded `not_found` only within the scope of the research, and check stale or decision-critical gaps through `oma-brand` or flag them for verification. An observed analytics tag is evidence of instrumentation on a page, not proof of authorized account access, working reporting, or active ads. Base measurement on available data; if access or baselines are missing, make that a prerequisite rather than assuming they exist.
3. **Choose and prioritize.** Define the audience, positioning, primary outcome, the channels and assets to prioritize or defer, and how to measure progress. Use the brand's evidence and the user's constraints to explain the choices. Identify dependencies and assumptions, and leave weaker opportunities for later rather than treating every gap as work to start now.

### Recommend campaigns from the strategy

Recommend the smallest set of campaigns that would advance the priorities, with the brand finding and reason for each, what must come first, and what to defer. For example:

| Brand finding | Campaign to consider |
| --- | --- |
| Research confirms the official website is absent and the audience needs a destination | A website-build campaign before sending traffic there. |
| No Product Hunt or other relevant launch found, and the audience and product are ready | A product-launch campaign on the platform that fits the audience; validate readiness and the conversion path first. |
| Research confirms the blog is absent and owned articles would serve the audience | A blog-build campaign; reuse the existing site or make hosting a prerequisite. |
| Verified social channels where the intended audience is active | A social campaign on those channels, building on existing accounts rather than automatically opening new ones. |
| Users need public docs to adopt the product | If absent after checking, recommend a public-docs build; if present but weak, recommend improving them. |
| The priority outcome cannot be measured with current access | Make measurement setup or verification a prerequisite; use a separate campaign only if the work warrants one. |

These are examples, not required campaigns. Include recommended priorities and their rationale in the inline strategy, then hand off campaign selection and execution design to `oma-campaigns`. Do not create rosters, campaign records, or jobs when only drafting the playbook.

## Procedure

1. **Read the singleton record.** Check `oma/playbook/config.yaml` first. Create it only when the user asks to set up the playbook and the record is absent. If the user asks for another, explain the one-playbook limit and confirm whether they intend to replace the existing strategy. Do not create a second record.
2. **Draft or revise when requested.** Use the compiled brand to form the strategy and recommend campaigns as above. Honor user-supplied priorities. Reuse the strategy on onboarding reruns unless revision is in scope; do not replace it just because new evidence was found.
3. **Save the requested changes.** Create or patch the fixed `config.yaml` path. Preserve the ID and fields the user did not ask to change. Ignore any legacy `brand_id` when reading the record; do not rewrite old records just to remove that field. Keep strategy in the `strategy` value; do not create a separate Markdown file.
4. **Inspect or remove on request.** Read the fixed record for lookups. Remove it only on explicit request. Do not follow paths or symlinks that escape `oma/playbook/`.

## Pitfalls

- Neither drafting nor saving a strategy authorizes executing it. Do not install campaigns, create jobs, or start agent turns as part of saving a record.
- Keep the strategy separate from campaign records and installation state. Use `oma-campaigns` to design and provision teams from the saved strategy.
- Older per-ID playbooks are not used as current records. If the user wants to carry one over, confirm which one and verify that its strategy applies to the saved brand. Do not move, merge, or overwrite legacy records automatically.

## Verification

Reopen `oma/playbook/config.yaml`. Confirm the ID, name, and description are present and `strategy` contains the requested text or is explicitly unset. For a drafted strategy, report the focus, what the evidence supports, which campaigns are recommended and why, and any open prerequisites. Do not report recommendations as provisioned campaigns.
