# Product launch campaign template

Use for a time-bound product or feature release. Before drafting, confirm the launch date and timezone, release readiness owner, audience, approved claims, primary call to action, and embargo or staged rollout constraints.

## Example campaign config

This example assumes a WordPress.com landing page, LinkedIn announcements, and GA4 attribution. Replace them with the destinations and measurement integrations actually in scope; don't add channels just because a launch could use them.

```yaml
id: product-launch
name: Product Launch
description: Turn release interest into qualified adoption of the new feature.
orchestrator: product-launch__orchestrator
agents:
  - product-launch__orchestrator
  - product-launch__content-creator
  - product-launch__publisher
integrations: [wordpress-com, linkedin, google-analytics]
goals:
  - Increase qualified feature activations from the launch audience during the agreed measurement window.
plans:
  - Before launch, confirm release readiness, baseline the activation event, test the primary conversion path, and prepare the landing page and announcements with tracked links.
  - At launch, confirm the release is available and the embargo has lifted; have the publisher apply authorized changes in the agreed order and verify live links and calls to action.
  - After launch, review activation and audience questions at the agreed checkpoints, prioritize corrective edits or follow-ups, and capture what to carry into the next release.
```

- **Team:** Keep the orchestrator and publisher. Add a content creator if landing-page copy, announcements, or assets need a separate owner. The publisher records the live URL or revision for each authorized change.
- **Review:** Check readiness and blockers before launch, and check live assets, audience feedback, and conversion evidence more frequently only during the launch window. Set the cadence and post-launch end point explicitly. Keep the timed publication and go/no-go decision as separate Kanban work; a recurring review does not authorize publication.

If the campaign covers Product Hunt, load the Product Hunt orchestrator example with `skill_view` (`name: oma-agents`, `file_path: references/product-hunt-orchestrator-template.md`) for a 10-day review of potential launches. Use it for the existing orchestrator role, not a second orchestrator. Include `product-hunt` in the campaign's integrations only if it is needed for the plan.
