# OMA source bundle

`skills/` contains reusable skill packages. This bundle does not ship campaign or agent templates.

- The OMA skills came from [openmarketing.agency at `a711fad9`](https://github.com/openmarketing-agency/openmarketing.agency/tree/a711fad9fb7dc70d6096d5b265f6aa07c86b1d23) under the original [license](LICENSE).
- [`skills/marketingskills/`](skills/marketingskills/) contains all 53 skills from [Corey Haines's marketingskills at `5b2b400e`](https://github.com/coreyhaines31/marketingskills/tree/5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1), including their package-local references, assets, scripts, and eval fixtures, under the upstream [MIT license](skills/marketingskills/LICENSE). For relative links to `tools/` in the skills, see [the upstream tools registry and guides](https://github.com/coreyhaines31/marketingskills/tree/5b2b400eec1e7e1cec76245a715d0b0d4fd2a9c1/tools). OMA does not bundle or configure those separate integration CLIs.
- [`skills/social-media-skills/`](skills/social-media-skills/) contains all 106 skill packages, including references and eval fixtures, from [Frank Heijdenrijk's Social Media Skills at `f28cef2b`](https://github.com/social-media-skills/skills/tree/f28cef2b7067ec64e79c9d85421c022c06659e03) under the upstream [MIT license](skills/social-media-skills/LICENSE). Bundling the skills does not install any tool mentioned in them or connect any social account.

The shared coordination skill is `campaign-orchestration` in OMA Agent.

Docker and the OMA POSIX source installer seed this skills bundle at `$HERMES_HOME/oma-bundle` when missing (`/opt/data/oma-bundle` in Docker and `./oma-agent-data/oma-bundle` for a fresh direct install). Existing copies are preserved; campaign templates left on older volumes are ignored. For a manual checkout not managed by the installer, copy the bundle to the default Hermes home to make the shared skills available.

To add either collection to an existing bundle, copy `skills/marketingskills/` or `skills/social-media-skills/` as a new directory under `$HERMES_HOME/oma-bundle/skills/`. Leave the rest of the existing bundle intact.

`skills_search` finds profile and shared skills; `skill_view` loads a match. Installed profile copies take precedence. `oma-campaigns` designs new teams from the saved brand and playbook and provisions from the editable OMA records, not from the bundle.
