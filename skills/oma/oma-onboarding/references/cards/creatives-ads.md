# Creatives: {name} — ads, labels, summary

Target: `{target}`. Load `oma-creatives` and follow its **How to Run** steps 3 to 6.

1. Run `{python} {collect} ads {brand} {target}`.
2. Run `{python} {collect} labels export {brand} {target}`, label every listed record from the taxonomy (view media with `vision_analyze` where the caption is not enough), write `landing_summary` for ads from `landing_facts`, and apply the labels with `{python} {collect} labels apply {brand} {target} <file>`.
3. Write `creatives.md` from the summary template, copying each source's coverage exactly.

**Check:** `{python} {validate_creatives} {brand} {target}` passes.
