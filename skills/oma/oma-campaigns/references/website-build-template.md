# Website build campaign template

Use when brand research confirms the client has no official website and needs a public destination. This example uses self-hosted WordPress, not WordPress.com. Verify the intended domain, hosting decision, and ownership before publishing. If a blog or docs hub will share the site, plan its route now and reuse the app rather than provisioning it again.

```yaml
id: website-build
name: Website Build
description: Give prospective customers an official site and a clear next step.
orchestrator: website-build__orchestrator
agents: [website-build__orchestrator, website-build__publisher]
integrations: [wordpress]
goals:
  - Give the primary audience an official site where they can understand the offer and complete the agreed conversion.
plans:
  - Plan the essential pages, navigation, brand assets, and primary conversion path with the client.
  - Reuse a suitable existing host, or have default route an authorized WordPress hosting handoff to maintenance using omactl; prepare pages while hosting is pending.
  - Verify staging, mobile layout, accessibility, and the primary conversion path; have the campaign publisher apply the authorized site changes and verify the live result.
  - Record verified public URLs and remaining gaps, then hand off the confirmed website URL for the saved brand record.
```

An installed CMS is not a finished site or confirmation of authenticated CMS access.

## Handoffs

- In `oma-agents`, load `references/owned-channel-orchestrator-template.md` and `references/owned-channel-publisher-template.md` for the matching agent examples. Load `references/maintenance-handoff.md` for the operations request when hosting is needed.
- Consider the campaign complete only after the intended public pages and primary call to action work on the approved URL. Report any unconfigured DNS, TLS, analytics, or CMS access separately.
