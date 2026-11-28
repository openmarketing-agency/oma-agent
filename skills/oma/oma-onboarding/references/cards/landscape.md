# Competitors: landscape

The top five direct competitors are profiled and their posts are collected. Ads are their own stage. Load `oma-competitors` and:

1. Complete each of the five competitors' `gtm.md` **What's working** and **Adaptable patterns** sections from its `creatives.md`, the posts it links, and the teardown (step 7); mark the ad-based parts `not_checked` with the reason "ads are collected in the ads stage".
2. Write `research/competitors.md` from the landscape template (step 8), including crowded and open angles counted from every competitor's `creatives.md`, compared with `research/own/creatives.md`.
3. Write or update `research/competitors/changes.md`, and merge `research: {competitors: [{id, name, website, report}, ...], competitor_report: research/competitors.md}` into the config, with `report` pointing at each profiled competitor's `profile.md`.

**Check:** `{python} {validate_competitors} {brand} --full 5 --light 0` passes. It also runs the creatives validator for the brand and each of the five competitors; a failure there means that target's posts card must be rerun, so block this card naming it.
