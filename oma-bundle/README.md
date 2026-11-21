# OMA source bundle

`skills/` contains reusable skill packages from [openmarketing.agency at `a711fad9`](https://github.com/openmarketing-agency/openmarketing.agency/tree/a711fad9fb7dc70d6096d5b265f6aa07c86b1d23), under the original [license](LICENSE). This bundle does not ship campaign or agent templates.

The shared coordination skill is `campaign-orchestration` in OMA Agent.

Docker seeds this skills bundle at `$HERMES_HOME/oma-bundle` (`/opt/data/oma-bundle` by default) when missing. Existing copies are preserved; campaign templates left on older volumes are ignored. For a native checkout, copy the bundle to the default Hermes home to make the shared skills available.

`search_skills` finds profile and shared skills; `skill_view` loads a match. Installed profile copies take precedence. `oma-campaigns` designs new teams from the saved brand and playbook and provisions from the editable OMA records, not from the bundle.
