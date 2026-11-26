# Brand design system

Load `oma-brand` and its `references/design-system-template.md`, and do step 3 of **Capture visual references and reusable assets**: build `design/DESIGN.md` from the screenshots and assets the visuals card saved, the brand kit, and the brand's own creatives in `research/own/` (their `creatives.md`, records, and media). Foundations, components seen in at least three examples, layouts per platform and format, what performs, voice, website and social differences, rules, and coverage.

Merge `design_system: {guidelines: design/DESIGN.md}` into the config.

**Check:** every component and layout links its examples, and `{python} {campaign} validate brand {brand}/config.yaml` passes.
