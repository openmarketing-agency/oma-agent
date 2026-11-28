# Competitors: discover, score and tier

The user asked for competitor research. Load `oma-competitors` with `skill_view` and do steps 1 to 5 (frame, discover, score, tiers, depth) and the matching parts of step 9: write `research/competitors/index.yaml` and `research/competitors/discovery.md`. Use `knowledge-base.md` for the frame. Run every discovery source for the brand's `business_type`, in order, up to 30 unique candidates, and score each one as the skill says. If an index exists from an earlier run, keep its candidates and evidence and update them.

Set `depth: full` on the top five direct competitors by the skill's sort order and `index_only` on every other candidate, direct or indirect. Do not add references. The board's five profile cards take the `full` entries in index order, and its creatives cards take the same five. Do not write profiles, teardowns, or creatives here, and do not merge config keys: the landscape card merges `research.competitors`.

**Check:** `{python} {board} slots {home}` prints the assignment without an error; it also records which competitor each profile and creatives card takes.
