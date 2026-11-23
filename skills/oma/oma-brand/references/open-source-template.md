# Open-source brand template

Use for a repository-led developer product. The example project and URLs are fictional. Verify the repository and official site refer to the same project before recording them together.

## `config.yaml`

```yaml
id: configtrail
name: ConfigTrail
description: Open-source command-line checks for project configuration.
website:
  status: verified
  url: https://configtrail.example/
repositories:
  - id: configtrail
    url: https://github.com/EXAMPLE-OWNER/EXAMPLE-REPO
documentation:
  public:
    status: verified
    url: https://configtrail.example/docs/
knowledge_base_file: knowledge-base.md
```

## `knowledge-base.md`

```markdown
# ConfigTrail brand knowledge

- Audience: The [project overview](https://configtrail.example/) describes developers and platform teams checking configuration before a build.
- Adoption: The [quickstart](https://configtrail.example/docs/quickstart) describes installation and the first check. Supported releases and platforms come from first-party release and install documentation; successful execution was not verified during this review.
- Claims and reuse: Verify the repository license and any asset-specific notices before reusing logos or fonts. A public repository does not make every asset reusable.
- Open questions: Confirm the preferred adoption outcome, maintained support channels, and who owns release communications.
```

The record above assumes repository identity was checked but a source analysis has not been saved. After static inspection, set `repositories[].analyzed_commit` to the actual commit and `repositories[].internal_docs` to its saved report index together. If a public-docs summary is saved, use `documentation.internal_reference` with the real index path and `mode: summarized`; use `mirrored` only when copying is permitted.
