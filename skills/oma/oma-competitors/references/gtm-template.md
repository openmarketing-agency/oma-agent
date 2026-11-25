# GTM Teardown Template

Save to `research/competitors/<id>/gtm.md`. Direct competitors get every section. Indirect competitors get only **Snapshot** and **Channels**. Activity counts cover the 90 days before the check date. Write `not_found` or `not_checked: <reason>` instead of leaving a section empty.

```markdown
# <Name>: GTM teardown

- **Last checked:** YYYY-MM-DD  ·  **Window:** last 90 days

## Snapshot
- Primary motion: product-led | sales-led | community-led | content/SEO-led | paid-led | marketplace-led | mixed (pick one, justify in one line).
- Primary conversion: free signup | trial | demo | purchase | waitlist | install | contact.

## Channels
| Channel | Profile / evidence URL | Posts or ads in window | Cadence | Engagement signal | Weight |
| --- | --- | --- | --- | --- | --- |
Weight is `high`, `medium` or `low`. Use `high` only when activity and engagement are both clearly above the other channels. List every channel checked, including the ones that are `not_found`.

## Messaging
- Homepage headline and subhead (paraphrased) and the main claims.
- Angles used, from the `oma-creatives` taxonomy, as counted in this competitor's `creatives.md`.
- Proof types used: logos, numbers, testimonials, reviews, awards.

## Offer and funnel
Path from the landing page to the primary conversion: CTAs, trial length, free plan, lead magnets, pricing page structure, onboarding observed without signing up. Email sequences: `not_checked: no authorized inbox` unless the operator gave you one.

## SEO and content
Content clusters and page types observed (blog, comparison pages, templates, tools, docs), category terms they rank for (from the discovery SERPs), and their own comparison or alternatives pages.

## Launches, PR, and partnerships
Dated launches (Product Hunt, Hacker News, marketplaces), press coverage, integrations, affiliate or partner programs.

## Community
Owned communities (Discord, Slack, forum, subreddit) with their size if shown, and founder-led presence.

## What's working
Up to 5 signals, each backed by evidence. Examples: an ad running 30+ days, posts with clearly higher engagement, a page ranking for a core term, repeated praise in reviews. Pull creative winners from `creatives.md` and link the records.

## Gaps and openings
Channels, angles or buyer needs they ignore or handle badly, and only where our brand can back the opening with its knowledge base.

## Adaptable patterns
| Pattern | Evidence | How our brand could adapt it | Needs |
| --- | --- | --- | --- |
Describe the mechanism, not the asset. "Needs" lists what our brand must already have for the pattern to be honest (feature, proof, budget, channel). Follow the "Adapting, Not Copying" rules in SKILL.md.
```
