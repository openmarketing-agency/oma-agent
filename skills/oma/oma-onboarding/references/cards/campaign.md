# Campaign: agents and plan for `{campaign}`

`{campaign}` is a draft in `oma/campaigns/{campaign}/config.yaml` with its name, description, and named agents. Load `oma-campaigns` and `oma-agents`, read the draft, the refreshed playbook, the brand record, `design/DESIGN.md`, and `research/competitors.md` if it exists, and do the campaign **Procedure** steps 1 to 5 for this one campaign only.

Keep its ID, name, and agents; change the roster only when the worked play it follows needs a role it lacks, and always keep the orchestrator and publisher. Adapt the best-fitting worked play (its roles, deliverables, and cadence) instead of a generic team, plan work that ships with concrete first outputs, and write the full definition to `oma/staging/{campaign}.yaml` (the draft's fields plus goals, plans, integrations, and the rest), each agent's `config.yaml`, and a role-specific `SOUL.md` grounded in this brand. Declare recurring work per the review signals, with schedules spread across different minutes and hours from other campaigns' jobs.

Do not edit the draft or provision: once every campaign card is done, the board replaces each draft with its staged definition, installs it, and starts it.

**Check:** `{python} {campaign} validate campaign oma/staging/{campaign}.yaml` and `validate agent <path>` pass for this campaign and each of its agents.
