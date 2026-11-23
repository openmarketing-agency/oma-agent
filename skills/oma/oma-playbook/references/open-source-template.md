# Open-source playbook template

Use when a repository-led developer product needs sustained adoption. Verify the official repo and docs, the supported installation path, and where users already ask questions before adapting this example.

```yaml
id: marketing-strategy
name: Open-Source Adoption Strategy
description: Help developers complete a first successful run of the project.
strategy: |-
  What the product is
  An open-source command-line tool that checks project configuration before a build.

  Positioning
  Local checks that developers can inspect and reproduce. Lead with a working example, the supported environments, and the tradeoff versus checking manually or in CI alone.

  Who we market to
  Platform engineers evaluate the tool for teams. Developers use it in their own repositories and surface rough edges. Maintainers and contributors improve coverage, examples, and trust.

  What success looks like
  Developers find the project, get a first valid check running, and return to it or recommend it. Useful feedback and contributions support continued adoption without overwhelming maintainers.

  Channels and their roles
  - GitHub and public docs: help evaluators understand the project and complete the quickstart on a supported release.
  - Existing communities: answer questions and learn where setup fails. Don't open new channels without demand and an owner.
  - Releases and demos: announce meaningful changes once install instructions and examples are ready. Defer paid promotion while discovery-to-first-run remains unclear.

  What we talk about
  Reproducible examples, supported checks, release improvements, and useful community contributions.

  Voice
  Technical, welcoming, and candid about limits. Lead with working commands and examples rather than hype.

  Measuring progress
  Treat repo traffic and stars as discovery, not install evidence. Measure successful first runs only with a consented source. Otherwise report release downloads and quickstart issues separately as imperfect indicators; note what cannot be attributed.

  Claims
  Verify supported platforms, versions, features, and license terms against the current release. Don't imply enterprise support or security guarantees without evidence.

  Revisit when the platform scope, contributor needs, or release strategy changes. Leave weekly execution decisions to campaigns.
```

For a maintained community project, discuss contribution or support load explicitly; don't assume growth is the only objective or add tracking just to make it measurable.
