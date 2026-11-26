# Competitors: patterns, landscape, validation

Every competitor profile and creatives card is done. Load `oma-competitors` and:

1. Complete each top-5 direct competitor's `gtm.md` **What's working** and **Adaptable patterns** sections from its `creatives.md` and the records it links (step 7).
2. Write `research/competitors.md` from the landscape template (step 8), including crowded and open angles counted from every `creatives.md`, compared with `research/own/creatives.md`.
3. Write or update `research/competitors/changes.md`, and merge `research: {competitors: [...], competitor_report: research/competitors.md}` into the config.

**Check:** `{python} {validate_competitors} {brand}` passes. It also runs the creatives validator for the brand and every collected competitor; a failure there means a creatives card must be rerun, so block this card naming it.
