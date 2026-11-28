# Strategy: playbook and campaigns

The brand core, market research, and the brand's own posts are done. Load `oma-playbook` and follow its **Procedure** end to end to save `oma/playbook/config.yaml`: grounded in `knowledge-base.md`, `research/market.md`, and `research/own/creatives.md`. Competitor research and ads run only when the user asks for them, so note them as not run instead of looking for them; the design system comes after the user confirms. Recommend the campaigns in priority order, each with its job, prerequisites, and evidence.

Then create the campaigns, by name only. Load `oma-campaigns` and read its ideas catalog and **worked plays**. For each recommended campaign, in priority order and at most five, choose an ID (lowercase, hyphenated) and a short name, write a one-line description of its job, and name the agent roles it needs: the roles of the best-fitting worked play, always including `orchestrator` and `publisher`. Do not write agent configs, souls, goals, plans, or schedules: they are written after the user confirms. Write the list to a YAML file in this card's workspace:

```yaml
campaigns:
  - id: <campaign-id>
    name: <Short name>
    description: <One line: the job this campaign does for the brand>
    agents: [orchestrator, <role>, <role>, publisher]
```

Run `{python} {board} campaigns {home} <file>`. It saves each campaign as a draft in `oma/campaigns/<id>/config.yaml` with its agents named `<id>__<role>`.

**Check:** the playbook validates with the campaign helper as `oma-playbook` describes, and the campaigns command printed the drafts.
