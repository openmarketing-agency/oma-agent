# OMA source bundle

`campaigns/` and `skills/` are a snapshot of the matching trees in [openmarketing.agency at `a711fad9`](https://github.com/openmarketing-agency/openmarketing.agency/tree/a711fad9fb7dc70d6096d5b265f6aa07c86b1d23). The copied files and their source [license](LICENSE) are unchanged. The architecture and jobs notes describe the sibling project's VM, not the OMA Agent Docker bootstrap.

Docker copies this source bundle into `$HERMES_HOME/oma-bundle` (`/opt/data/oma-bundle` by default) when the directory is missing. Existing copies are not overwritten. The installer reads campaign definitions and skill packages from that copy. In a source checkout outside Docker, copy this directory into the default Hermes home to make it available.

`search_skills` finds both profile skills and the bundle's shared `skills/`; `skill_view` loads a matching skill. Installed profile copies take precedence. Campaign-private skills remain private to the campaign installation; the search tool does not scan `campaigns/`.
