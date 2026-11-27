---
name: ga4-analytics
description: Read GA4 reports for the verified campaign website.
version: 0.1.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [analytics, ga4]
---

# GA4 Analytics Skill

Measure what people do after arriving on the campaign website. Use GA4 for traffic, on-site engagement, and tracked outcomes; use `google-search-analytics` for Google Search impressions, clicks, and queries.

## When to Use

- Site summary: start with `sessions`, `activeUsers`, `screenPageViews`, `engagedSessions`, and `engagementRate`.
- Acquisition, landing pages, key events, or ecommerce: choose the report below rather than mixing fields from different scopes into one request.

## Prerequisites

The campaign declares `google-analytics` and has a verified brand website. Use an authorized GA4 read-only MCP connection for the matching property, directly or through `composio-analytics`. If no authorized connection is available, report the gap and direct the operator to the OMA console; don't request credentials in chat.

## Quick Reference

These are GA4 Data API field names to look up, not a fixed tool schema. Request only the relevant fields and check compatibility for the selected property.

| Question | Dimensions to try | Metrics to try |
| --- | --- | --- |
| How much traffic did the site get? | None for the period total; `date` for a daily trend | `sessions`, `activeUsers`, `newUsers`, `screenPageViews`, `engagedSessions`, `engagementRate` |
| Which channels brought visits? | `sessionDefaultChannelGroup` or `sessionSourceMedium`; `sessionCampaignName` for a confirmed campaign tag | `sessions`, `engagedSessions`, `keyEvents`, `sessionKeyEventRate` |
| What brought new users the first time? | `firstUserSourceMedium` | `newUsers` |
| Which pages were viewed or started sessions? | `pagePath` for viewed pages; `landingPage` for session entry pages | `screenPageViews` for viewed pages; `sessions`, `engagedSessions`, `keyEvents` for landing pages |
| Which actions happened? | `eventName`; filter to verified event names when useful | `eventCount`, `keyEvents`; use the relevant `sessionKeyEventRate:<event_name>` only if available in property metadata |
| How did purchases perform? | None for a total; `date` or a compatible acquisition dimension for a breakdown | `ecommercePurchases`, `purchaseRevenue`; use `totalRevenue` only when its broader revenue definition is intended |
| How does performance vary by audience segment? | `deviceCategory` or `country` | `sessions`, `activeUsers`, `engagementRate` |

## Procedure

1. **Verify the site scope.** Discover read actions equivalent to GA4 Admin `accountSummaries.list` and `properties.dataStreams.list`. Match the authorized property and web stream to the verified website; do not confuse the numeric property ID, stream ID, and `G-...` measurement ID. If the property includes other sites or apps, constrain reports to the correct `streamId` and, if the stream is shared, the verified `hostName` where supported. If you cannot verify or isolate the site, ask for the correct scope instead of using property totals. A campaign-specific claim needs a verified filter (for example, the actual session campaign tag), not just the property match.
2. **Choose the period and check storage.** Use the property's timezone and explicit inclusive GA4 start/end dates. Compare equal-length complete periods; request today's data only when the question calls for partial or realtime results. Load `analytics-dataset` to read observations for the same property, filters, metrics, and period. Fetch only gaps and stale data.
3. **Run a small report before expanding.** Discover the read-only Data API report action (`runReport` or equivalent). Use `getMetadata` for property-specific/custom fields and `checkCompatibility` for a proposed metric/dimension/filter combination when exposed. For “last month's traffic and top landing pages,” request a site total without grouping, a `date` report only if a trend is needed, and a separate `landingPage` report with `sessions`, `engagedSessions`, and `keyEvents`. Translate GA4 names to the live tool schema, not UI labels or guessed argument names.
4. **Check coverage and definitions.** Match headers to values. Page stable reports with `offset`/`limit` against `rowCount` when exposed, or use the tool's continuation field. Mark a deliberate top-N as such. Check report metadata for sampling, thresholding, `(other)` aggregation, restricted metrics, timezone, and currency. Use separate provider totals rather than summing users or averaging row-level rates.
5. **Report and save.** State the property/site, local dates, filters, and coverage. Keep `engagementRate` and key-event rates as fractional `ratio` values if returned that way; give revenue its reported currency. Follow `analytics-dataset` for local-date boundaries, saving verified rows, and reading them back. Keep site totals, filtered campaign totals, and breakdowns distinct.

## Pitfalls

- `screenPageViews` includes app screens when the report is not web-only; repeated views count. `activeUsers` is not the same as sessions, and daily unique users do not sum to period-unique users.
- `eventCount` counts all occurrences of an event; `keyEvents` counts occurrences designated as key at the time. Neither is a raw event export. No ecommerce instrumentation or a missing custom metric is not proof of zero sales.
- GA4 organic sessions and Search Console clicks are different measurements. Keep them separate even when showing them side by side.

## Verification

Confirm the site filter, property, timezone, and date range match the request. Report the actual rows/periods covered, including limitations and any metrics you could not verify. Read back each saved scope before claiming it was stored.

## Official References

[GA4 dimensions and metrics](https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema) · [Web and app streams](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/properties.dataStreams/list) · [Report request](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport) · [Compatibility](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/checkCompatibility) · [Response metadata](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/ResponseMetaData)
