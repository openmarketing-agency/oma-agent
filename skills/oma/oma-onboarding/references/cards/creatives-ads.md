# Creatives: {name} — ads

Target: `{target}`. Its posts are collected and labelled, and its ad libraries are recorded as deferred. Load `oma-creatives` and follow its **How to Run** steps for ads.

1. Run `{python} {collect} ads {brand} {target}`. It searches every ad library in `sources.yaml` and replaces the deferred records.
2. Run `{python} {collect} labels export {brand} {target}`, label every listed ad from the taxonomy (view media with `vision_analyze` where the copy is not enough), write `landing_summary` from `landing_facts`, and apply the labels with `{python} {collect} labels apply {brand} {target} <file>`.
3. Update `creatives.md` with the ads and their winners, copying each source's coverage exactly.

**Check:** `{python} {validate_creatives} {brand} {target}` passes.
