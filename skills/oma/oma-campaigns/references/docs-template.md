# Docs campaign template

Use when the playbook prioritizes helping users complete onboarding or other important workflows through documentation. Before drafting, identify the affected audience, product version, canonical docs repository or CMS, and the evidence for the largest gaps (such as recurring support questions or a failing quickstart).

## Example campaign config

This example assumes the docs source is on GitHub. Replace the integration and role IDs as needed; don't assume GitHub is the publishing destination.

```yaml
id: docs
name: Documentation
description: Help new users complete setup without contacting support.
orchestrator: docs__orchestrator
agents:
  - docs__orchestrator
  - docs__writer
  - docs__publisher
integrations: [github]
goals:
  - Increase the share of new users who complete the first successful setup and reduce repeat setup questions.
plans:
  - Reproduce the current quickstart against the supported release and rank gaps using issue and support evidence.
  - Rewrite the highest-friction steps, test the examples end to end, and prepare a reviewed change for the canonical docs.
  - After the publisher applies the authorized change, verify the rendered docs, links, and examples; reassess completion and repeat questions before choosing the next page.
```

- **Team:** Keep the orchestrator and publisher. Add a docs writer when separate writing and technical verification are useful. The publisher applies the authorized change through the docs release process and records the live page or revision.
- **Review:** Start with a daily scan when releases or feedback generate actionable changes. Check new release notes, docs issues, and failed examples since the last review. Use setup completion where instrumented, or tracked repeat setup questions when available; don't infer either from page views.
