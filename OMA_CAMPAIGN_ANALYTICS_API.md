# OMA Campaign Analytics API

**Availability:** The analytics runtime is on `oma-agent/main` at `06618d0ffb5`. This document describes the local `openmarketing.agency` HTTP handlers. The campaign analytics routes are not present on `openmarketing.agency/main` as checked at `33e845985645`; live availability has not been verified.

## Routes

`{id}` is the saved campaign ID. Use the console routes from a signed-in session. The VM routes are internal HTTP endpoints on the workspace Unix socket, not public URLs.

| Operation | Console route | Private VM route | Success |
| --- | --- | --- | --- |
| Read saved observations | `GET /api/campaigns/{id}/analytics` | `GET /workspace/campaigns/{id}/analytics` | `200 OK` |
| Queue a refresh | `POST /api/campaigns/{id}/analytics/refresh` | `POST /workspace/campaigns/{id}/analytics/refresh` | `202 Accepted` |
| Read Analyst refresh status | `GET /api/campaigns/{id}/analytics/status` | `GET /workspace/campaigns/{id}/analytics/status` | `200 OK` |

## Read saved observations

`GET /api/campaigns/{id}/analytics`

No request body. All query parameters are optional; unknown or repeated parameters are rejected.

| Parameter | Type | Meaning |
| --- | --- | --- |
| `source` | string | Exact, case-sensitive source ID, e.g. `oma-publications`, `google-analytics`, or `google-search-console`. |
| `account` | string | Exact, case-sensitive account or property ID. For `oma-publications`, this is the campaign ID. |
| `metric` | string | Exact, case-sensitive metric ID, e.g. `drafts_created`. |
| `start` | ISO date or timestamp | Include rows with `period_end > start`. |
| `end` | ISO date or timestamp | Include rows with `period_start < end`. If `start` is also supplied, `start` must precede `end`. |
| `limit` | integer | `1`–`100`; defaults to `50`. |
| `before` | integer | Exclusive observation ID bound, `1`–`9007199254740991`. Pass `next_cursor` from the preceding page. |

String labels must be nonblank, printable, and at most 512 characters. Dates in `YYYY-MM-DD` mean midnight UTC. Timestamps require a timezone; URL-encode a `+` in a timezone offset as `%2B`.

Example: `GET /api/campaigns/seo/analytics?source=oma-publications&metric=drafts_created&start=2026-11-01&end=2026-12-01&limit=25`

### Response schema (`200`)

```ts
type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

interface AnalyticsObservation {
  id: number;             // integer
  source: string;
  account: string;
  metric: string;
  period_start: string;   // UTC ISO timestamp, inclusive
  period_end: string;     // UTC ISO timestamp, exclusive
  dimensions: Record<string, Json>;
  value: Json;
  unit: string;
  collected_at: string;   // UTC ISO timestamp
}

interface AnalyticsResponse {
  campaign_id: string;
  observations: AnalyticsObservation[];
  last_collected_at: string | null;
  next_cursor: number | null;
}
```

Results are ordered by descending `id`. If there are more results, repeat the same filters with `before=<next_cursor>`; stop when `next_cursor` is `null`. `last_collected_at` is the newest saved observation timestamp across the campaign, regardless of filters. No matching rows returns `observations: []`, not a measurement of zero. The route works while the campaign is stopped and never calls a provider.

## Queue a refresh

`POST /api/campaigns/{id}/analytics/refresh`

Send **no body and no query parameters**; an empty JSON object (`{}`) is not accepted. Browser calls must be same-origin.

For any running campaign, the request queues the managed Analyst job for the next scheduler tick. In `approve` and `yolo`, that job also runs every six hours, and manual refresh does not move a future scheduled slot. In `control`, no scheduled analytics runs occur; this endpoint is the only way to request one. If an analytics run is already queued or running, the request returns its current state without scheduling another run. `202` confirms acceptance, not completion.

Both triggers refresh local OMA draft/publication counts and start a turn on the campaign's Analyst profile. The Analyst uses its analytics skills and authorized read-only integrations to collect and save verified measurements. Unavailable or partial sources are reported, not filled with zeros.

### Sources and history

Every managed Analyst has access to the OMA analytics skills. They guide the Analyst to check saved measurements first, discover authorized read-only tools for any gaps, and save verified observations. A legacy dataset mapping on an installed campaign is ignored; connectors do not need to advertise analytics datasets.

- [`google-search-analytics`](oma-bundle/skills/analytics/google-search-analytics/SKILL.md) and [`ga4-analytics`](oma-bundle/skills/analytics/ga4-analytics/SKILL.md) explain which metrics to request, how to match the verified website to its property, and how to handle reporting limits. Either can use a native MCP connection or Composio.
- [`composio-analytics`](oma-bundle/skills/analytics/composio-analytics/SKILL.md) explains how to discover read-only tools and schemas from connected integrations.
- [`social-media-analytics`](oma-bundle/skills/analytics/social-media-analytics/SKILL.md) covers post counts, per-post performance, and replied, unreplied, and unknown audience-comment counts.

The [`analytics-dataset` skill](oma-bundle/skills/analytics/analytics-dataset/SKILL.md) gives Analysts the observation format and save/read workflow. The Analyst's CLI reads and writes its own campaign's `data.sqlite3`. The default profile can also read saved observations. These commands do not contact providers.

```bash
python -m hermes_cli.oma_campaigns analytics-status <id>
python -m hermes_cli.oma_campaigns analytics-read <id> --source google-analytics --metric sessions
python -m hermes_cli.oma_campaigns analytics-breakdown <id> google-search-console page --metric clicks
python -m hermes_cli.oma_campaigns analytics-save <id> < observations.json
```

`analytics-read` supports `--source`, `--account`, `--metric`, `--start`, `--end`, `--breakdown`, `--limit`, and `--before`. The existing HTTP observations endpoint continues to return totals separately. `analytics-save` accepts 1–100 observations as a JSON array on stdin. Each row supplies `source`, `account`, `metric`, `period_start`, `period_end`, `value`, `unit`, and `dimensions`. Repeat saves update the same series and period. See each row's `collected_at` for external data freshness. No old saved observations are deleted.

### Response schema (`202`)

```ts
type RefreshResponse = Omit<AnalyticsStatusResponse, "state" | "last_successful_refresh_at"> & {
  state: "queued" | "running";
};
```

## Read Analyst refresh status

`GET /api/campaigns/{id}/analytics/status`

No query parameters or request body are needed.

### Response schema (`200`)

```ts
interface AnalyticsStatusResponse {
  campaign_id: string;
  state: "queued" | "running" | "idle" | "unavailable";
  running: boolean;
  run_id: string | null;
  last_outcome: string | null; // previous cron outcome, e.g. "ok", "error", "cancelled"
  last_finished_at: string | null; // ISO timestamp
  last_successful_refresh_at: string | null; // UTC ISO timestamp
}
```

- `queued`: Accepted and waiting to start. `running` is `false`.
- `running`: The managed analytics execution is active on the Analyst profile. `running` is `true`. Unrelated Analyst chats are not tracked by this endpoint.
- `idle`: The managed job exists, but no run is queued or running. This does not mean the campaign is started or the previous run succeeded.
- `unavailable`: The managed analyst or its job is not available.

Treat `run_id` as opaque: a queued refresh can return a timestamp that changes to an execution ID once it starts. Poll status after a `202`. `last_outcome` describes the completed cron run; `last_successful_refresh_at` is the local publication refresh timestamp. Use each external row's `collected_at` for its freshness: a finished run does not imply every provider returned data.

## Errors

The console returns `{ "error": "..." }`; the private VM socket returns `{ "message": "..." }` for handler errors.

| Status | Meaning |
| --- | --- |
| `401 Unauthorized` | Console session is not signed in. |
| `403 Forbidden` | Console rejected a cross-origin refresh request. |
| `404 Not Found` | Campaign or route not found. |
| `409 Conflict` | Refresh is blocked: the campaign is stopped, the Analyst is not installed, or the managed job is missing or paused. |
| `422 Unprocessable Content` | Invalid observation filters or pagination, or unexpected refresh input. |
| `503 Service Unavailable` | Analytics storage or runtime is unavailable, the agent image lacks analytics support, or the Analyst job could not be queued. |

## Implementation references

- [Observation validation, filters, and pagination](hermes_cli/oma_campaigns/analytics.py#L116)
- [Managed refresh and execution status](hermes_cli/oma_campaigns/analytics_cron.py#L52)
- [Analyst analytics skills](oma-bundle/skills/analytics/)
- Local sibling checkout: `openmarketing.agency/vm/workspace.py` (`campaign_analytics`, `WorkspaceHandler`)
- Local sibling checkout: `openmarketing.agency/oma/app/api/campaigns/[id]/analytics/[[...action]]/route.ts`
