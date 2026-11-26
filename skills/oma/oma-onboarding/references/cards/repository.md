# Brand repository analysis

Repository: {repo}

Load `oma-brand` and follow **Clone and document GitHub repositories** end to end: the shallow no-checkout clone, the commit, the reports under `docs/repository/<repo-id>/` (`index.md`, `capabilities.md`, `architecture.md`, `key-workflows.md`), citing the commit and files.

Then add a **Product capabilities (verified in code, commit `<short sha>`)** section to `knowledge-base.md`: the user-facing capabilities, delivery modes, and limits, each linked to the repository reports. Merge `repositories` (with `analyzed_commit` and `internal_docs`) into the config.

Not in this card: website research, assets, or any other stage.

**Check:** the four reports exist and cite the commit; `{python} {campaign} validate brand {brand}/config.yaml` passes.
