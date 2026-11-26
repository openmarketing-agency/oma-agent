# Competitors: discover, score, tier

Load `oma-competitors` with `skill_view` and do steps 1 to 5 (frame, discover, score, tiers, depth) and the matching parts of step 9: write `research/competitors/index.yaml` and `research/competitors/discovery.md`. Use `knowledge-base.md` for the frame. Do not write profiles, teardowns, or creatives here.

Then run `{python} {board} fanout {home}`. It adds one profile card and two creatives cards per top-5 direct competitor, one card for the indirect profiles, and creatives cards for each reference, and makes the landscape card wait for them.

**Check:** the fan-out command printed the new cards, and `index.yaml` tiers and depths follow the skill's caps.
