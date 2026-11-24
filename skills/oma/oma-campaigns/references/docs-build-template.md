# Public docs build campaign template

Use when users need documentation and research confirms there is no public docs destination. This example builds a simple docs hub on WordPress.com. If the product needs a versioned docs stack, verify its deployment path and choose integrations that support it. For improving an existing docs site without building a new destination, use `references/docs-template.md`.

```yaml
id: docs-build
name: Public Docs Build
description: Give new users a public path from setup to their first success.
orchestrator: docs-build__orchestrator
agents: [docs-build__orchestrator, docs-build__publisher]
integrations: [wordpress-com]
goals:
  - Help new users complete a supported setup and first workflow without needing to contact support.
plans:
  - Choose the first supported workflow, verify the product version, and agree on a public docs URL and information architecture.
  - Reuse a suitable WordPress.com site and verify the publisher's access to the intended docs destination.
  - Prepare a docs index, tested quickstart, and troubleshooting pages using verified product behavior and reviewed examples.
  - Have the publisher apply the authorized pages and verify navigation, links, and the published quickstart against the supported product version; hand off the verified docs URL for the brand record.
```

If the client uses a self-hosted docs site instead, choose the integrations it actually uses and verify publishing access separately.

In `oma-agents`, load `references/owned-channel-orchestrator-template.md` and `references/owned-channel-publisher-template.md` for the matching agent examples. Load `references/maintenance-handoff.md` only if separate self-hosted infrastructure work is needed. Do not treat internal notes or a working CMS as published documentation. Add a technical writer or reviewer only if ownership or verification warrants a separate role.
