# Website build campaign template

Use when brand research confirms the client has no official website and needs a public destination. This example uses WordPress.com. Verify the intended site, domain, and ownership before publishing. If a blog or docs hub will share the site, plan its route and reuse the same site.

```yaml
id: website-build
name: Website Build
description: Give prospective customers an official site and a clear next step.
orchestrator: website-build__orchestrator
agents: [website-build__orchestrator, website-build__publisher]
integrations: [wordpress-com]
goals:
  - Give the primary audience an official site where they can understand the offer and complete the agreed conversion.
plans:
  - Plan the essential pages, navigation, brand assets, and primary conversion path with the client.
  - Verify the WordPress.com connection and the publisher's access to the intended site. Prepare pages while site setup or access is pending.
  - Verify staging, mobile layout, accessibility, and the primary conversion path; have the campaign publisher apply the authorized site changes and verify the live result.
  - Record verified public URLs and remaining gaps, then hand off the confirmed website URL for the saved brand record.
```

If the client chooses self-hosted WordPress instead, omit `wordpress-com` unless it is actually used, and verify the publisher's CMS access separately. An installed app is not proof of authenticated access.

## Handoffs

- In `oma-agents`, load `references/owned-channel-orchestrator-template.md` and `references/owned-channel-publisher-template.md` for the matching agent examples. Load `references/maintenance-handoff.md` only if separate self-hosted infrastructure work is needed.
- Consider the campaign complete only after the intended public pages and primary call to action work on the approved URL. Report any unconfigured DNS, TLS, analytics, or CMS access separately.
