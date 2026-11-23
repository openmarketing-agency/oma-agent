# Blog build campaign template

Use when the client has no verified blog and the playbook needs a place to answer audience questions or capture search demand. This example adds a blog to a self-hosted WordPress site. Reuse its CMS and public domain when they fit; if there is no site and the blog depends on it, resolve the website setup first.

```yaml
id: blog-build
name: Blog Build
description: Establish a discoverable blog with a useful first set of articles.
orchestrator: blog-build__orchestrator
agents: [blog-build__orchestrator, blog-build__publisher]
integrations: [wordpress, higgsfield]
goals:
  - Give the target audience a reliable place to find answers and take the next relevant step toward the product.
plans:
  - Confirm the audience questions, blog route, publishing workflow, and first topics that serve the playbook.
  - Reuse the verified CMS or have default route authorized hosting setup to maintenance through omactl if the platform is missing.
  - Prepare the blog index, navigation, and initial articles with source-backed claims and context-appropriate calls to action.
  - Prepare generated hero art where the content brief calls for it and review the assets before handoff.
  - Have the publisher apply the authorized changes and verify the public index, first article URLs, links, and feed if configured; hand off the verified blog URL for the brand record.
```

In `oma-agents`, load `references/owned-channel-orchestrator-template.md` and `references/owned-channel-publisher-template.md` and use their blog variants. For new hosting, load `references/maintenance-handoff.md`. Editorial and publishing work stays with the campaign; maintenance does not create posts or own the blog's schedule. Add a writer only when the volume or review needs justify a separate role.

For a new roster that needs a writer, load `references/blog-writer-template.md` from `oma-agents` and include `blog-build__writer`.

## Campaign integrations for generated media

The example uses `wordpress` for publishing and `higgsfield` for generated hero art. Omit the generator if approved assets already meet the brief, or select `runway` instead if the plan needs a generated demo clip and the connector supports it. Use the [integration intake guide](integration-intake.md) to verify the fit and ask the user for the selected connection only if it's missing.
