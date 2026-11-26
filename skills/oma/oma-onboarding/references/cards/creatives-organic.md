# Creatives: {name} — organic posts

Target: `{target}`. Load `oma-creatives` with `skill_view` and follow its **How to Run** steps 1 and 2.

1. **Plan.** For `own`, run `{python} {collect} sources {brand} own` and review the result against `channels.social`. For a {plan}, write `research/competitors/{target}/sources.yaml` from the sources template at `{sources_template}`, using the verified profiles in its `profile.md` and `gtm.md` (search the target's own site for missing profile links before leaving a platform out).
2. **Collect.** Run `{python} {collect} organic {brand} {target}`. Do not stop on a `limited` or `blocked` platform; the script records it with proof and moves on.

Labels and the summary come in the ads card.

**Check:** every platform in `sources.yaml` has `socials/<platform>/index.yaml` with a coverage status, and the script's per-platform results are in your completion summary.
