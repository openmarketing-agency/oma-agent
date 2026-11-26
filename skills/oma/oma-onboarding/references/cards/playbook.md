# Strategy: playbook and campaign choice

The brand, market, competitor landscape, and design system are done. Load `oma-playbook` and follow its **Procedure** end to end to save `oma/playbook/config.yaml`: grounded in `knowledge-base.md`, the repository reports, `research/market.md`, `research/competitors.md`, and the creatives summaries. Recommend the smallest useful set of campaigns in priority order, each with its job, prerequisites, and evidence.

Then load `oma-campaigns`, read its ideas catalog and **worked plays**, and choose the campaign IDs (lowercase, hyphenated) that execute the recommended campaigns, preferring a worked play where one fits. Run `{python} {board} campaigns {home} <id> <id> ...` in priority order. It adds one design card per campaign and the provisioning card.

**Check:** the playbook validates with the campaign helper as `oma-playbook` describes, and the campaigns command printed the new cards.
