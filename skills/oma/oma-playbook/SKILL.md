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

Create, inspect, and update the single OMA playbook for the saved brand. It records the user's strategy; it is not an installable campaign or a running workflow.

## When to Use

- The user asks to save, find, revise, or remove a playbook or its strategy.
- The user asks for the brand's approved strategy.

## Prerequisites

Use the default profile's Hermes home as the base for `oma/playbook/`. On the local CLI, `hermes config path` identifies that home. Use `read_file`, `write_file`, and `patch` for the record. Read brand context directly from `oma/brand/config.yaml` when needed; if it is missing, offer to set it up with `oma-brand` first.

## Record Format

Save the one playbook at `oma/playbook/config.yaml`. Keep its stable lowercase, hyphen-separated `id` independent of the display `name`; campaigns use the fixed path, not an ID link. Do not add a `brand_id` field: this playbook applies to the single brand in the same Hermes home.

```yaml
id: product-launch
name: Product Launch
description: Plan the marketing rollout for a new product.
strategy: |-
  Focus on existing customers first. Use their feedback to refine the
  messaging before expanding outreach. Measure qualified sign-ups.
```

`strategy` is the strategy text itself. Use a YAML block scalar for multiline content, not a filename or link to a separate strategy document. If the user has not supplied or asked you to draft a strategy, use `strategy: ""` and report it as unset.

## Procedure

1. **Read the singleton record.** Check `oma/playbook/config.yaml` first. Create it only when the user asks to set up the playbook and the record is absent. If the user asks for another, explain the one-playbook limit and confirm whether they intend to replace the existing strategy. Do not create a second record.
2. **Save the requested changes.** Create or patch the fixed `config.yaml` path. Preserve the ID and fields the user did not ask to change. Ignore any legacy `brand_id` when reading the record; do not rewrite old records just to remove that field. Keep strategy in the `strategy` value; do not create a separate Markdown file.
3. **Inspect or remove on request.** Read the fixed record for lookups. Remove it only on explicit request. Do not follow paths or symlinks that escape `oma/playbook/`.

## Pitfalls

- Neither drafting nor saving a strategy authorizes executing it. Do not install campaigns, create jobs, or start agent turns as part of saving a record.
- Keep the strategy separate from campaign records and installation state. Use `oma-campaigns` to design and provision teams from the saved strategy.
- Older per-ID playbooks are not used as current records. If the user wants to carry one over, confirm which one and verify that its strategy applies to the saved brand. Do not move, merge, or overwrite legacy records automatically.

## Verification

Reopen `oma/playbook/config.yaml`. Confirm the ID, name, and description are present and `strategy` contains the requested text or is explicitly unset. Report what changed.
