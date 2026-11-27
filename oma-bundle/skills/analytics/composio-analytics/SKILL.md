---
name: composio-analytics
description: Collect read-only data from connected campaign apps.
version: 0.1.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [analytics, composio]
---

# Composio Analytics Skill

Use the campaign's existing Composio MCP connection to discover which apps, accounts, and read actions are usable for the question. The toolkit catalogue shows what might exist; the Analyst's live tools and authorized connection determine what can be read.

## When to Use

Use for analytics from apps connected through `composio`. For provider-specific reporting, use alongside `ga4-analytics`, `google-search-analytics`, or `social-media-analytics`.

## Prerequisites

The campaign declares the integration, the Analyst can see its configured `composio` MCP server, and an operator has authorized the intended account. If a direct MCP connection already supplies the requested report for that account, use it instead of collecting the same data twice. Follow a user-specified connection path when given.

## Quick Reference

Search by read intent, not by an assumed action slug. Examples:

| Request | First read to discover | Follow-up read to discover |
| --- | --- | --- |
| GA4 website traffic | List GA4 property summaries and retrieve the web streams for the intended property. | Run a GA4 Data API report for sessions and page views by date, scoped to the verified site. |
| Search Console clicks | List Search Console properties accessible to the connected account. | Query Search Analytics for clicks and impressions by date for the selected property. |
| Instagram comment coverage | List media owned by the authorized Instagram professional account. | List top-level comments, then list replies by parent comment with author identifiers. |

## Procedure

1. **Find the configured MCP tools.** Inspect the Analyst's enabled tool list; use `tool_search` (or its exposed alias) and the tool schema loader if deferred discovery is available. Hermes registers MCP tools under `mcp__<server>__…`; names can be shortened, so use the exposed name, not a name assembled from the examples below. Some servers expose individual provider reads directly. If those are the tools you have, inspect their schema and use the authorized read after verifying scope.
2. **Search for the specific reads.** When the Composio meta-tool is visible, start with `COMPOSIO_SEARCH_TOOLS`. Use one `queries[].use_case` per operation, naming the app and what it should read. Keep IDs out of free-form search text; use `known_fields` for minimal authorized identifiers if needed. Under the current schema, start a workflow with `session: {"generate_id": true}`, retain the returned `data.session.id`, and pass it as `session_id` to subsequent meta-tools when accepted. Continue the same discovery with `session.id`; start a new workflow if the task changes. If the search plan is off-target, narrow the query or retry with `search_strategy: tool_search` if offered.
3. **Verify connection and resource separately.** Inspect `toolkit_connection_statuses` and `has_active_connection` (or the live equivalent) for requested apps only. A toolkit slug is not an OMA integration ID, a Composio connected account ID is not a property/page/channel ID, and an active connection may have the wrong scopes. Use a read-only identity or resource-listing action to confirm the exact provider account/property; do not choose an arbitrary default or switch identities. If the connection is missing, expired, or can't read the resource, tell the operator which integration/account needs attention in the OMA console. Do not call `COMPOSIO_MANAGE_CONNECTIONS` to start or replace auth during analytics, or request tokens in chat.
4. **Read the actual schema and fetch a small first page.** Use the returned `tool_schemas`, or `COMPOSIO_GET_TOOL_SCHEMAS` for an incomplete schema or `schemaRef`. Select the discovered `tool_slug` only if the operation reads existing data; consult both its description and inputs. Call the provider action directly if exposed, or use `COMPOSIO_MULTI_EXECUTE_TOOL` with `tools: [{"tool_slug": "<discovered-slug>", "arguments": {…}}]` (shape illustration, not a literal payload). Use the same authorized account and workflow session. Batch only reads without dependencies; list the property or post IDs before using them in report/metrics actions. Keep responses small and inline when possible. Check each `data.results` entry and its provider response, not just the outer success flag. Follow provider cursors/offsets; a response preview or partial error is not complete data.
5. **Save scoped observations.** Load `analytics-dataset` before refetching or saving. Use the campaign integration ID as `source` and the verified provider account/property ID as `account`; do not save connector credentials, session metadata, raw responses, or personal data. Record only verified observations and read them back.

## Pitfalls

- Separate “no read action found,” “connection missing,” “wrong resource/insufficient scope,” and “read succeeded with no rows.” They have different next steps. Do not represent any as a numeric zero without evidence.
- Keep the workflow read-only even when search suggests auth management, proxy/raw API calls, export creation, posting, replies, or moderation. Do not use those actions to bypass what the connected analytics tools expose.

## Verification

Confirm the actual app, connected identity, resource, and reporting period. State which pages or dates were covered and which requested fields could not be verified. For multiple apps, report each app's result separately.

## Official References

[Search tools](https://docs.composio.dev/toolkits/meta-tools/search_tools) · [Get tool schemas](https://docs.composio.dev/toolkits/meta-tools/get_tool_schemas) · [Execute discovered tools](https://docs.composio.dev/toolkits/meta-tools/multi_execute_tool) · [GA4 toolkit](https://docs.composio.dev/toolkits/google_analytics) · [Search Console toolkit](https://docs.composio.dev/toolkits/google_search_console) · [Hermes MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
