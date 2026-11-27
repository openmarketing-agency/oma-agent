---
name: google-search-analytics
description: Read Search Console reports for a verified site.
version: 0.1.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [analytics, search-console]
---

# Google Search Analytics Skill

Measure how a verified site performs in Google Search with first-party Search Console data. This is not a live rank tracker, an Ads report, or a substitute for GA4 sessions.

## When to Use

Use for clicks, impressions, CTR, and average position. Find which pages or visible queries gained or lost clicks, which device or country drove a change, or where high impressions and low CTR warrant review.

## Prerequisites

The campaign declares `google-search-console` and has a verified website. Use an authorized Search Console MCP connection for that property, directly or through `composio-analytics`. If it is missing, direct the operator to the OMA console; don't request credentials.

## Quick Reference

Search Analytics returns `clicks`, `impressions`, `ctr` (a fraction), and `position` (average position) for each row. Choose grouping separately from filters:

| Question | Query shape |
| --- | --- |
| How did the site perform or trend? | No dimensions for the period total; `date` for the daily trend. |
| Which URLs or searches changed? | Separate `page` and `query` reports. Use `page` plus `query` only for a targeted diagnosis; filter to the exact page or prefix when needed. |
| Did country or device mix change? | Group by `country` or `device`; request both together only if the question requires it. |
| Which result features appeared? | Discover values with `searchAppearance` on its own; then filter by the returned value in a separate breakdown. |

Use `type: web` as the default for ordinary web search. Query `image`, `video`, `news` (News tab), `googleNews`, or `discover` separately when requested and supported. Discover and Google News are distinct surfaces, not web-search rankings; not every dimension or metric applies on every surface.

## Procedure

1. **Resolve the exact property.** Discover read actions equivalent to `sites.list` and `searchanalytics.query`. Use the returned `siteUrl` verbatim, such as `sc-domain:example.com` (all protocols/subdomains) or `https://www.example.com/` (exact URL prefix scope). If only a broader domain is accessible, use an appropriate page filter for a narrower site and label the resulting page aggregation. If multiple scopes fit, ask rather than guessing or summing overlapping properties.
2. **Check existing data and freshness.** Load `analytics-dataset` and read the same property, search type, filters, and dates before fetching. Search Console dates are Pacific Time (`America/Los_Angeles`); the API's `startDate` and `endDate` are inclusive. Use `dataState: final` (or the default) for comparisons. If recent finalized coverage is unclear, check a recent unfiltered `date` report; data is typically delayed 2–3 days and missing daily rows are omitted. For an explicitly fresh report, use `all` when supported and label incomplete dates from response metadata where provided.
3. **Read the total, then diagnose.** Start with a total for each matching complete period and search type. For “why did clicks fall last month?”, compare those totals, then query daily, top pages, and visible queries separately. Map `rows[].keys` to dimensions in request order. Use `aggregationType: auto` when grouping/filtering by page, or the tool's equivalent; report the response aggregation type if available. Page results with the live schema's `startRow` and `rowLimit` (API maximum 25,000 per call) or its continuation primitive. Fetch bounded pages, and say whether a table is top-N or incomplete; even full pagination is subject to upstream limits.
4. **Interpret and save.** Use provider totals for CTR and position. If computing CTR for a known complete compatible set with impressions above zero, divide total clicks by total impressions, not the mean of row CTRs. Save verified values using `analytics-dataset`; store `ctr` as `ratio`, `position` as a rank/position unit, and counts as `count`. Preserve search type and any filters in dimensions so different scopes don't overwrite one another. Convert the inclusive last day to the following local midnight for OMA's exclusive end.

## Pitfalls

- Anonymized queries and other omitted rows mean visible breakdowns need not reconcile to site totals. Search Analytics returns top rows and can cap detailed results; a missing query or day is not a verified zero.
- Average position is a provider aggregate, not your site's current rank or a row average you can combine unweighted. Page data generally uses Google's canonical URL; page- and property-aggregated totals can differ. Don't imply campaign attribution from a property-wide change.

## Verification

Confirm property, search type, filters, Pacific dates, and finalized/partial status. Describe what portion of the breakdown is visible and read back the saved observations in the same scope.

## Official References

[List Search Console properties](https://developers.google.com/webmaster-tools/v1/sites/list) · [Search Analytics query reference](https://developers.google.com/webmaster-tools/v1/searchanalytics/query) · [Aggregation, row limits, and pagination](https://developers.google.com/webmaster-tools/v1/how-tos/all-your-data)
