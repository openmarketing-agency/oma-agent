# Campaigns: provision paused teams

Every campaign design card is done. Campaigns: {ids}

Load `oma-campaigns` and do step 6 for each campaign in order: `create <definition.yaml>` (or `install <id>` for an existing unprovisioned definition; reuse verified installations), then `status <id>` for the full team and its Kanban board. Campaigns stay paused. Missing account connections do not block provisioning; list them.

**Check:** `status` shows every campaign with its complete team and board. Report each campaign, its team, and the connections the user must add in the OMA console. Report any failed provisioning as a blocker.
