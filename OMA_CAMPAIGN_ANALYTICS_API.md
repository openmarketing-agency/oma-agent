# OMA Campaign Analytics API

**Availability:** The analytics runtime is on `oma-agent/main` at `06618d0ffb5`. This document describes the local `openmarketing.agency` HTTP handlers. The campaign analytics routes are not present on `openmarketing.agency/main` as checked at `33e845985645`; live availability has not been verified.

## Routes

`{id}` is the saved campaign ID. Use the console routes from a signed-in session. The VM routes are internal HTTP endpoints on the workspace Unix socket, not public URLs.

| Operation | Console route | Private VM route | Success |
| --- | --- | --- | --- |
| Read saved observations | `GET /api/campaigns/{id}/analytics` | `GET /workspace/campaigns/{id}/analytics` | `200 OK` |
| Queue a refresh | `POST /api/campaigns/{id}/analytics/refresh` | `POST /workspace/campaigns/{id}/analytics/refresh` | `202 Accepted` |
| Read collector status | `GET /api/campaigns/{id}/analytics/status` | `GET /workspace/campaigns/{id}/analytics/status` | `200 OK` |

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

For a running `approve` or `yolo` campaign, the request queues the managed analyst collector for the next scheduler tick. It does not change the job's hourly schedule. If a run is already queued or running, the request returns its current state instead of starting a duplicate. `202` confirms acceptance, not completion. In `control`, the collector still runs on its hourly schedule while the campaign is running, but this manual refresh request is rejected.

The collector reads external data through the Analyst profile's enabled MCP servers. It stores successful pages and their checkpoints together. A source error makes the overall refresh incomplete while other sources continue. OMA publication counts come from the campaign's local history.

### Sources, detail, and history

The built-in Search Console and GA4 readers use the verified brand website to match properties. They collect daily totals and backfill report history in bounded pages across runs. Search Console adds page, query, country, and device breakdowns. GA4 adds page path, event name, country, device category, and session channel group. Coverage describes what the provider returned within its history, row limits, and scopes. For example, [Search Console can omit rows](https://developers.google.com/webmaster-tools/v1/how-tos/all-your-data). GA4 event-name breakdowns are aggregate reports.

MCP servers can advertise multiple campaign datasets using two tools with `readOnlyHint: true`:

- `oma_analytics_list_datasets(campaign_id, integrations)` returns `{"datasets": [{"integration": "...", "id": "...", "account_id": "..."}]}`. The server must enumerate only the campaign's authorized accounts and resources.
- `oma_analytics_read_dataset(campaign_id, integration, dataset_id, account_id, limit, cursor?, checkpoint?)` returns `{"records": [{"id": "...", "data": {...}}], "next_cursor": "...", "checkpoint": "..."}`. Start with accessible history, return `next_cursor` to continue, and optionally return a `checkpoint` on the final page for incremental reads. A connector without a checkpoint can enumerate its cursor sequence again on later runs. Use stable string record IDs. Include date, timestamp, and breakdown fields in `data` where the provider exposes them.

For an existing read-only MCP tool, add a dataset to the campaign's `config.yaml` and sync the campaign. The tool must have `readOnlyHint: true`. Use arguments that scope the request to the campaign's approved account or resources. Keep credentials in the connection configuration.

```yaml
integrations: [example-service]
analytics_datasets:
  team-events:
    integration: example-service
    server: example-service
    tool: list_events
    account: team-42
    arguments: { team_id: team-42, limit: 50 }
    items: response.events
    record_id: id
    pagination: { parameter: cursor, next: response.next_cursor }
```

Omit `pagination` for a tool that returns the full dataset in one response of up to 100 records. For offset or page-number pagination, set `kind` to `offset` or `page` and set `size_parameter` to the argument that supplies the page size. Set the size in `arguments` and use a maximum of 100 records per page.

For Composio, the Analyst uses the campaign's saved `integrations` and the existing MCP connection. It calls [Search Tools](https://docs.composio.dev/toolkits/meta-tools/search_tools) for the connected toolkit, retrieves missing input schemas, and collects through the same session with [Multi Execute](https://docs.composio.dev/toolkits/meta-tools/multi_execute_tool). Composio collection needs no `analytics_datasets` entries. The collector accepts actions with a read-only tag or annotation, plus a set of documented read actions for router versions that omit tags. It supplies pagination parameters and can bind a required website argument from the verified brand website. Read actions that need another resource ID, an unsupported input, or a complete schema are shown in coverage. Results are saved under the action slug in lowercase with hyphens, such as `stripe-list-charges`. Provider search results and account scopes determine which reads are available. When the Analyst's active Composio connection differs from the campaign's saved connection, collection reports `connection_sync_required`.

Use the campaign-local CLI to read details. The daily observations endpoint continues to return totals separately.

```bash
python -m hermes_cli.oma_campaigns analytics-status <id>
python -m hermes_cli.oma_campaigns analytics-records <id> stripe stripe-list-charges
python -m hermes_cli.oma_campaigns analytics-breakdown <id> google-search-console page --metric clicks
```

The two data-read commands accept `--limit` and `--before` for cursor pagination.

### Response schema (`202`)

```ts
type RefreshResponse = Omit<AnalyticsStatusResponse, "state" | "last_successful_refresh_at" | "datasets"> & {
  state: "queued" | "running";
};
```

## Read collector status

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
  datasets: {
    source: string;
    server: string;
    dataset: string;
    account: string;
    state: string;
    last_successful_at: string | null;
    requested_from: string | null;
    checked_from: string | null;
    collected_through: string | null;
  }[];
}
```

- `queued`: Accepted and waiting to start. `running` is `false`.
- `running`: The collector is executing. `running` is `true`.
- `idle`: The managed job exists, but no run is queued or running. This does not mean the campaign is started or the previous run succeeded.
- `unavailable`: The managed analyst or its job is not available.

Treat `run_id` as opaque: a queued refresh can return a timestamp that changes to an execution ID once it starts. Poll status after a `202`. When the run settles, use `last_outcome` for the previous result and `last_successful_refresh_at` for freshness. The latter advances after a cycle without a source failure. A dataset can still be `backfilling` across successful cycles. Check each dataset for its own state, including `current`, `read_error`, `connection_required`, `no_readable_tools`, and `read_inputs_required`. A partial failure can leave saved results available without advancing the campaign timestamp.

## Errors

The console returns `{ "error": "..." }`; the private VM socket returns `{ "message": "..." }` for handler errors.

| Status | Meaning |
| --- | --- |
| `401 Unauthorized` | Console session is not signed in. |
| `403 Forbidden` | Console rejected a cross-origin refresh request. |
| `404 Not Found` | Campaign or route not found. |
| `409 Conflict` | Refresh is blocked: the campaign is stopped or in `control`, the analyst is not installed, or the managed job is missing or paused. |
| `422 Unprocessable Content` | Invalid observation filters or pagination, unexpected refresh input, or invalid campaign analytics configuration. |
| `503 Service Unavailable` | Analytics storage or runtime is unavailable, the agent image lacks analytics support, or the collector could not be queued. |

## Implementation references

- [Observation validation, filters, and pagination](hermes_cli/oma_campaigns/analytics.py#L116)
- [Managed refresh and execution status](hermes_cli/oma_campaigns/analytics_cron.py#L52)
- [MCP report reads](hermes_cli/oma_campaigns/analytics_mcp.py)
- Local sibling checkout: `openmarketing.agency/vm/workspace.py` (`campaign_analytics`, `WorkspaceHandler`)
- Local sibling checkout: `openmarketing.agency/oma/app/api/campaigns/[id]/analytics/[[...action]]/route.ts`
