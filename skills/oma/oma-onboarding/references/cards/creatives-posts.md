# Creatives: {name} — posts and summary

Target: `{target}`. Load `oma-creatives` with `skill_view` and follow its **How to Run** steps for organic posts. Ads are their own stage, so this card records the ad libraries as deferred instead of opening them.

1. **Plan.** For `own`, run `{python} {collect} sources {brand} own` and review the result against `channels.social`. For a competitor, review `research/competitors/{target}/sources.yaml`, written by its profile card, against `profile.md` and `gtm.md`; if it is missing, write it from the sources template at `{sources_template}`, and search the competitor's own site header and footer for any profile it misses.
2. **Collect posts.** Run `{python} {collect} organic {brand} {target}`. Do not stop on a `limited` or `blocked` platform; the script records it with proof and moves on.
3. **Defer the ad libraries.** Run `{python} {collect} ads {brand} {target} --defer "Ads are collected in the ads stage."`. It records each library as `not_checked` with that reason without opening it.
4. **Label.** Run `{python} {collect} labels export {brand} {target}`, label every listed post from the taxonomy (view media with `vision_analyze` where the caption is not enough), and apply the labels with `{python} {collect} labels apply {brand} {target} <file>`.
5. **Summarize.** Write `creatives.md` from the summary template, copying each source's coverage exactly.

**Check:** `{python} {validate_creatives} {brand} {target}` passes, and the script's per-platform results are in your completion summary.
