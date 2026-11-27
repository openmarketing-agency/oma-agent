---
name: analytics-dataset
description: Format, save, and read campaign analytics observations.
version: 0.1.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [analytics, campaign, storage]
---

# Analytics Dataset Skill

Use one observation format across analytics sources. Save and load observations through the campaign CLI; it uses the campaign's `oma/campaigns/<id>/data.sqlite3` under the workspace Hermes home. Do not edit the database directly. This skill does not configure a dataset or call a provider.

## When to Use

Load before checking existing campaign measurements or saving newly verified metrics. Use the relevant provider skill for deciding what to measure and fetching missing data.

## Prerequisites

Use `terminal` from the installed Analyst profile for the campaign you intend to write. The default OMA profile may also read saved observations. Use only that campaign's authorized sources and keep provider credentials, personal information, and raw provider responses out of the store.

## Observation Format

Send a JSON array. Each row must contain exactly these fields:

| Field | What to put in it |
| --- | --- |
| `source` | The campaign integration ID, such as `google-analytics`. `oma-publications` is reserved for the local job. |
| `account` | A stable provider account, property, or site ID. |
| `metric` | A consistent metric name, such as `sessions` or `screenPageViews`. |
| `period_start`, `period_end` | Inclusive start and exclusive end. Use ISO dates for UTC day boundaries or timezone-aware timestamps for provider-local periods. End must be after start. |
| `value`, `unit` | The observed JSON value and its unit. Use numbers for counts and rates, and distinguish units such as `count`, `ratio`, and `percent`. |
| `dimensions` | A JSON object. Use `{}` for an unqualified total; add stable scope keys for filtered totals and use `breakdown` only for grouped rows, such as `{"breakdown":"post","post_id":"post-123"}`. |

Example daily total (illustrative data only):

```json
[
  {
    "source": "google-analytics",
    "account": "property-123",
    "metric": "sessions",
    "period_start": "2026-01-01",
    "period_end": "2026-01-02",
    "value": 42,
    "unit": "count",
    "dimensions": {}
  }
]
```

## Keep Measurements Comparable

- **Use the provider's local boundaries.** Convert an inclusive last day into midnight at the start of the next local day. For Search Console January 1 in Pacific Time, use `2026-01-01T00:00:00-08:00` through `2026-01-02T00:00:00-08:00`. Take the offset at each boundary if daylight saving time changes. The CLI normalizes timestamps to UTC.
- **Preserve scope in the row key.** Use the verified provider resource ID, not a Composio connection ID. Examples of scope keys: `{"search_type":"web"}` for a Search Console total, `{"breakdown":"page","search_type":"web","page":"https://example.com/"}` for a grouped row, and `{"stream_id":"123","hostname":"example.com"}` for a filtered GA4 total. Keep additional filters, differing aggregation bases, and alternate currencies distinct when relevant. Use the same conventions on later reads and saves; dimensions are part of the upsert key.
- **Separate activity from snapshots.** Save cumulative post metrics with `{"breakdown":"post","post_id":"post-123","basis":"lifetime_snapshot"}` and use the observation day's boundaries. This gives one updatable snapshot per day for that scope; `collected_at` shows when the latest value was saved, not when the activity occurred. Do not backdate a snapshot to the publication day or add snapshots together.
- **Keep only usable evidence.** Save a complete observed metric as a numeric value with a consistent unit (for example, `ratio` for fractional CTR, `count` for comments, or a reported currency code for revenue). A complete metric from a partial report can still be saved in its verified scope, for example one video's views when another video is inaccessible. Do not save missing figures as zero or partial/provisional totals under the finalized key. Do not persist sensitive query strings, comment text, user identifiers, or raw responses.

## Procedure

1. **Read first.** Use `terminal` with `python -m hermes_cli.oma_campaigns analytics-read demo --source google-analytics --account property-123 --metric sessions --start 2026-01-01 --end 2026-01-02`, substituting the real campaign and reporting scope. `--start` and `--end` select overlapping periods; check the returned boundaries and scope dimensions before reusing a row. Without `--breakdown` the command excludes breakdown rows; pass `--breakdown post` (or the exact saved name) to read those rows. Follow `next_cursor` with `--before` until it is null when a complete read is needed. `--limit` accepts 1–100 and defaults to 50.
2. **Save verified data.** Use `terminal` with `python -m hermes_cli.oma_campaigns analytics-save demo`, passing the JSON array on stdin (for example, redirect an `observations.json` file in a POSIX shell). Save 1–100 rows per batch, at most 256 KiB. Do not send readback metadata such as `id` or `collected_at`. The `saved` count should match the number of rows submitted.

## Pitfalls

- Re-saving the same source, account, metric, period, and dimensions replaces its value and unit rather than adding another row. Keep those fields consistent when refreshing the same observation.
- Missing, unsupported, or partial data must not become a verified zero or complete total. Keep cumulative snapshots distinct from activity measured within a period.
- Do not sum totals and breakdown rows together. `analytics-read` loads saved data only; it does not fetch missing values.

## Verification

Read back the same source, account, period, metric, and breakdown. Check `observations` for the expected values and units. Use each row's `collected_at` to assess save freshness, not the local publication refresh timestamp.
