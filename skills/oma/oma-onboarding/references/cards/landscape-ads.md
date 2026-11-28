# Competitors: landscape with ads

The brand's ads and the five competitors' ads are collected. Load `oma-competitors` and:

1. In each of the five competitors' `gtm.md`, complete the ad-based parts of **What's working** and **Adaptable patterns** from its ads in `creatives.md` and the records it links, replacing what the landscape marked `not_checked`.
2. Update `research/competitors.md`: paid angles, formats, and offers counted from every competitor's ads, compared with the brand's own ads in `research/own/creatives.md`.
3. Add the update to `research/competitors/changes.md`.

**Check:** `{python} {validate_competitors} {brand} --full 5 --light 0` passes. A creatives failure there means that target's ads card must be rerun, so block this card naming it.
