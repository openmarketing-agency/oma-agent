# Play schema

A play is a folder with a `play.yaml`, a `rules.md` and an `example.md`. Bundled plays live in `plays/<play-id>/` inside this skill. They are only examples: each shows catalog ideas worked out for a made-up business, and campaigns use them as references, never as templates. Plays you design for a business live in `oma/plays/<play-id>/` under the default Hermes home. Values for product types, stages, channels, fallbacks, write policies, approvals, toolsets, tools and slot sources come from `plays/vocab.yaml`, plus any additions in `oma/plays/vocab.yaml`. Run `scripts/plays.py validate <play-id>` after every change.

## Top-level fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Lowercase, hyphen-separated slug, the same as the folder name. Custom plays can't reuse a bundled id. |
| `version` | yes | Integer. Bump it when behavior changes: roster, channels, deliverables, approvals, limits, jobs, or the meaning of the rules. Fixing wording doesn't need a bump. |
| `based_on` | no | `<play-id>@<version>` of the play this one was adapted from. `plays.py new --from` sets it. |
| `name` | yes | Display name. |
| `summary` | yes | One sentence used when choosing plays. |
| `fits` | yes | `product_types`, `stages`, `best_when`, `avoid_when`. |
| `outcome` | yes | Goal template. Every `{slot}` placeholder must be a slot id. Becomes the campaign's first goal once filled. |
| `horizon` | yes | `ongoing`, or a duration such as `4w` for a time-boxed play. |
| `time_to_signal` | yes | When leading signals should appear, so reviews don't judge too early. |
| `requires` | yes | Channels the play reads or writes. See below. |
| `tools` | no | Extra capabilities such as `video_render`. |
| `roster` | yes | Roles. Must include `orchestrator` and `publisher`. See below. |
| `deliverables` | yes | What the campaign ships and how often. See below. |
| `jobs` | yes | Scheduled work. Must include `campaign-review` owned by the orchestrator. |
| `kpis` | yes | `leading`, `lagging`, `targets` and, for `after_baseline`, `baseline_weeks`. |
| `limits` | yes | Numeric caps, such as posts per day. An enforcement layer can read them, and agents must respect them. |
| `slots` | yes | Business-specific inputs to fill before install. |
| `kickoff` | yes | First tasks, queued for the orchestrator after install so day one has visible work. |
| `plan` | yes | 2 to 6 ordered steps. They become the campaign's `plans` once slots are filled. |
| `rules` | yes | Execution rules file inside the play folder, normally `rules.md`. Must contain `## Definition of done` and `## Non-negotiables`. |
| `ideas` | no | Catalog numbers from `ideas/catalog.yaml` that this play shows. Each must exist in the catalog. |
| `example` | no for custom plays | The worked example file inside the play folder, normally `example.md`. It must contain `## Business`, `## Campaign` and `## Team`. Bundled plays always have one. |
| `pairs_with` | no | Plays that complement this one. |

Unknown fields fail validation, so typos are caught. `TODO` anywhere in `play.yaml`, `rules.md` or `example.md` also fails validation, so a scaffold can't be used before it is finished.

## `requires`

`{channel, mode, fallback, optional, note}`

- `mode`: `read` or `write`.
- `fallback`: what happens when the channel is not connected. `assisted` (writes only): OMA prepares the work, a person publishes it, and the publisher reads it back and records the URL. `research_only` (reads only): the campaign runs on public data and makes no performance claims. `none`: the play is not eligible without this access.
- A write on a `human_only` channel must use `assisted`. A channel whose write policy is `none` can't be written.
- `optional: true` means the play uses the channel when it is there. Non-optional entries are the play's core channels.

## `roster`

`{role, does, per_run, toolsets, reads, writes, untrusted_input, skills}`

- Agent ids become `<campaign_id>__<role>`.
- `does` is the core of the agent's SOUL, together with the business specifics it needs and the path to `rules.md`.
- `per_run` is what the role hands over every time it runs, with a count where it has one: "Up to 15 new threads, each with link, venue rules and fit", "One finished article per task". A role with nothing to hand over doesn't belong on the team. Required in bundled plays; custom plays without it get a warning.
- `toolsets` use the vocabulary names. `integrations` stands for the connected-app toolsets on the instance (for example the Composio or MCP toolset that is actually configured): put the real toolset name in the agent record only when that integration is connected, and leave it out otherwise.
- `reads` and `writes` are the role's allowed channels. An enforcement layer should scope integration tools to them, with read-only actions for `reads`.
- Only `publisher` may have `writes`, and its `writes` must cover every write requirement. This keeps planning, making and publishing separate.
- Every read requirement must be read by at least one role.
- `untrusted_input: true` (the role reads public or inbound content) forbids `terminal`.
- The publisher never gets `browser`. It acts through official integrations, or packages work for a person.
- `skills` lists shared skill package IDs from `oma-bundle/skills/` (for example `copywriting`). They become the agent's `oma_skills` after `skills_search` confirms they exist. When a skill's advice conflicts with the play's rules or a platform rule, the rules win.

## `deliverables`

`{id, what, cadence, owner, approval, standing_ok}`

- `cadence`: `N/day`, `N/week`, `N/month`, `N/quarter`, `daily`, `weekly`, `monthly`, `per_event` or `once`. Cadences are drafting defaults, not campaign keys.
- `owner`: the role that makes the item. The publisher ships it.
- `approval`: `none` (internal work), `per_item`, or `batch` (a set approved together).
- `standing_ok: true`: after 10 approvals in a row without edits, the user may switch this deliverable to standing approval. Any edit, complaint or rule change switches it back.

## `jobs`

`{id, owner, cadence, checks, max_items, schedule_note}`

- `cadence` as above, `hourly` for lightweight activity checks, or `custom` with a `schedule_note` describing the schedule. Keep broader social performance reviews at weekly cadence.
- `checks` name the activity or data to read. Write them as activity ("new comments and replies on our posts"), never as access checks.
- `max_items` bounds each run.
- `scripts/plays.py jobs <campaign-id> --play <play-id> --agent <role> --sources "..."` drafts existing native `jobs` entries for one owning agent. It doesn't save or schedule them.

## `kpis`, `limits`, `slots`, `kickoff`, `plan`

- `kpis.targets`: `after_baseline` (with `baseline_weeks`) or `fixed` when the user gave a number. Never invent targets.
- `limits`: snake_case names with numbers, such as `max_posts_per_platform_per_day: 2` or `vote_requests: 0`. Platform rules live in the channel files. Put business-specific limits in the existing campaign `plans` and relevant personas.
- `slots`: `{id, required, source, ask}`. `source` says where to look first (`brand`, `playbook`, `research`, `user`, `integration`); `ask` says in plain words what the value is. When it can't be found, the campaign records it as missing (a need, or a first step in `plans`); campaigns are created without asking the user.
- `kickoff`: `{owner, task}`, at least 2.

## Channel rules

Platform rules live in `channels/<channel>.md` inside this skill, one file per channel, shared by every play and campaign. Each says when it was checked, who publishes, the rules, the limits and the sources to re-check. A file at `oma/plays/channels/<channel>.md` under the default home takes precedence, and is where rules for a new channel go. A play's `rules.md` points to the channel files in its Non-negotiables instead of copying them. `scripts/plays.py validate` warns when a play writes to a channel with no rules file, and `show` prints the paths a play uses.

## Ideas catalog

`ideas/catalog.yaml` lists the campaign ideas: `{id, name, what, integrations, for, section, gate, example, note}`. `for` is a hint, never a filter. Put setup and verified-access prerequisites in the existing campaign `plans` and select canonical connector IDs for `integrations`. `example` names the bundled play that shows a similar campaign. `scripts/plays.py ideas` prints it, and `validate` checks every `example` points to a play.

## Vocabulary additions

When a business needs a channel, product type, stage, tool or toolset the vocabulary lacks, add it in `oma/plays/vocab.yaml`:

```yaml
channels:
  etsy:
    name: Etsy shop
    write_policy: api
    note: Listings through Etsy's official tools. Reviews follow review_sites rules.
product_types:
  marketplace_seller: Sells mainly through third-party marketplaces.
```

Additions can't redefine existing values. Pick the strictest honest write policy: if you can't confirm from the platform's current official rules that automated posting is allowed, use `human_only`.

## How a play maps to campaign records

| Play | Campaign records |
|---|---|
| Idea IDs and play version | Drafting references only; don't add campaign keys |
| `outcome` with slots filled | First entry in `goals` |
| `plan` with slots filled | `plans` |
| `deliverables` | Outcomes to ship in `plans` and outputs in the owning agent's SOUL |
| `requires` (minus unused optional channels) | Connector IDs in `integrations`, suggested Composio labels in `integration_categories`, prerequisites in `plans` |
| `roster` | One existing agent record per role: verified toolsets and skill IDs, plus a SOUL with the role, per-run output, applicable rules and business limits, and saves path |
| `jobs` | The owning agent's `jobs` list, drafted with `scripts/plays.py jobs` |
| `kickoff` | One kickoff task for the orchestrator after install |
