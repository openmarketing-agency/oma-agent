# Public docs build campaign template

Use when users need documentation and research confirms there is no public docs destination. This example builds a simple docs hub in an owned, self-hosted WordPress site. If the product needs a versioned docs stack, check the actual deployment path and catalog support instead of assuming `omactl` can install an arbitrary docs generator. For improving an existing docs site without building a new destination, use `references/docs-template.md`.

```yaml
id: docs-build
name: Public Docs Build
description: Give new users a public path from setup to their first success.
orchestrator: docs-build__orchestrator
agents: [docs-build__orchestrator, docs-build__publisher]
integrations: [wordpress]
goals:
  - Help new users complete a supported setup and first workflow without needing to contact support.
plans:
  - Choose the first supported workflow, verify the product version, and agree on a public docs URL and information architecture.
  - Reuse the existing site where it fits; if a supported hosting app is missing, have default route an authorized setup handoff to maintenance using omactl.
  - Prepare a docs index, tested quickstart, and troubleshooting pages using verified product behavior and reviewed examples.
  - Have the publisher apply the authorized pages and verify navigation, links, and the published quickstart against the supported product version; hand off the verified docs URL for the brand record.
```

In `oma-agents`, load `references/owned-channel-orchestrator-template.md` and `references/owned-channel-publisher-template.md` and use their docs variants. For new hosting, load `references/maintenance-handoff.md`. Do not treat internal notes or a healthy CMS as published documentation. Add a technical writer or reviewer only if ownership or verification warrants a separate role.
