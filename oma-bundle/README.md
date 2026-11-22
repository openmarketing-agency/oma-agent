# OMA source bundle

`skills/` contains reusable skill packages. This bundle does not ship campaign or agent templates.

- The OMA skills came from [openmarketing.agency at `a711fad9`](https://github.com/openmarketing-agency/openmarketing.agency/tree/a711fad9fb7dc70d6096d5b265f6aa07c86b1d23) under the original [license](LICENSE).
- [`skills/marketingskills/`](skills/marketingskills/) contains all 53 skills from [Corey Haines's marketingskills at `5b2b400e`](https://github.com/coreyhaines31/marketingskills/tree/5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1), including their package-local references, assets, scripts, and eval fixtures, under the upstream [MIT license](skills/marketingskills/LICENSE). For relative links to `tools/` in the skills, see [the upstream tools registry and guides](https://github.com/coreyhaines31/marketingskills/tree/5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1/tools). OMA does not bundle or configure those separate integration CLIs.

The shared coordination skill is `campaign-orchestration` in OMA Agent.

Docker seeds this skills bundle at `$HERMES_HOME/oma-bundle` (`/opt/data/oma-bundle` by default) when missing. Existing copies are preserved; campaign templates left on older volumes are ignored. For a native checkout, copy the bundle to the default Hermes home to make the shared skills available.

To add the collection to an existing bundle, copy `skills/marketingskills/` as a new directory under `$HERMES_HOME/oma-bundle/skills/`. Leave the rest of the existing bundle intact.

`skills_search` finds profile and shared skills; `skill_view` loads a match. Installed profile copies take precedence. `oma-campaigns` designs new teams from the saved brand and playbook and provisions from the editable OMA records, not from the bundle.
