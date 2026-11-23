# SEO campaign template

Use when the playbook prioritizes qualified organic discovery. Before drafting, identify the target audience and search intent, verified site property, owned publishing destination, and primary organic conversion.

## Example campaign config

This example uses Search Console, WordPress.com, and GA4. Replace the IDs with the catalog integrations the brand actually needs for search evidence, publishing, and measurement.

```yaml
id: seo
name: SEO
description: Attract qualified organic traffic to priority product pages.
orchestrator: seo__orchestrator
agents:
  - seo__orchestrator
  - seo__researcher
  - seo__publisher
integrations: [google-search-console, wordpress-com, google-analytics]
goals:
  - Increase qualified sign-ups from organic search for the priority use case.
plans:
  - Baseline query and landing-page performance and qualified organic sign-ups; prioritize pages with relevant demand and a clear content or indexing gap.
  - Prepare targeted page, internal-link, or technical fixes; create new content only when existing pages don't serve the intent.
  - Have the publisher apply approved changes and verify the live pages; compare indexing, clicks, and organic sign-ups over comparable periods before choosing the next changes.
```

- **Team:** Keep the orchestrator and publisher. Add an SEO researcher when query analysis or technical diagnosis warrants a separate role. The publisher records the changed URL or revision.
- **Review:** A daily scan can catch actionable indexing or site changes. Assess search and conversion trends only after enough comparable data has accumulated; a ranking movement alone isn't a conversion result.
