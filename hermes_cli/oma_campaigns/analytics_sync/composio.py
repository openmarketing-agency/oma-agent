"""Discover safe reads in a campaign's Composio session and normalize their paginated results.

Use published action classifications where present and vetted action slugs for older
router responses. Provider guidance and returned data never select executable actions.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from referencing import Registry
from referencing.exceptions import Unresolvable

from hermes_cli.oma_campaigns.analytics import AnalyticsError, _label
from hermes_cli.oma_campaigns.analytics_sync.data import Dataset
from hermes_cli.oma_campaigns.integrations import integration_catalog

SEARCH = "COMPOSIO_SEARCH_TOOLS"
SCHEMAS = "COMPOSIO_GET_TOOL_SCHEMAS"
# The search API may omit behavior tags. These documented actions only read an
# authenticated account and can be invoked from their input schemas.
_DOCUMENTED_READS = frozenset({
    "AIRTABLE_LIST_BASES",
    "GITHUB_LIST_REPOSITORIES", "GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER",
    "GMAIL_FETCH_EMAILS", "GMAIL_LIST_LABELS", "GMAIL_LIST_THREADS",
    "GOOGLEADS_LIST_ACCESSIBLE_CUSTOMERS", "GOOGLEDRIVE_FIND_FILE", "GOOGLEDRIVE_LIST_FILES",
    "HUBSPOT_LIST_COMPANIES", "HUBSPOT_LIST_CONTACTS", "HUBSPOT_LIST_DEALS",
    "INSTAGRAM_GET_IG_USER_MEDIA", "INSTAGRAM_GET_USER_INFO", "INSTAGRAM_GET_USER_INSIGHTS",
    "METAADS_GET_AD_ACCOUNTS", "METAADS_GET_INSIGHTS", "METAADS_LIST_CAMPAIGNS",
    "SLACK_LIST_CONVERSATIONS", "STRIPE_LIST_CHARGES", "STRIPE_LIST_CHECKOUT_SESSIONS",
    "THREADS_LIST_MY_POSTS", "TWITTER_GET_POST_ANALYTICS", "TWITTER_GET_USER_POSTS", "TWITTER_USER_LOOKUP_ME",
    "YOUTUBE_LIST_CHANNELS",
})
_WRITE_TAGS = {"createHint", "updateHint", "destructiveHint"}
_PAGE_SIZE = 20
_SIZE = ("limit", "per_page", "page_size", "pageSize", "max_results", "maxResults", "count", "first")
_CURSORS = ("cursor", "page_token", "pageToken", "pagination_token", "next_token", "after",
            "start_cursor", "starting_after", "offset")
_NEXT_PATHS = (
    ("next_cursor",), ("nextCursor",), ("next_page_token",), ("nextPageToken",), ("offset",),
    ("response_metadata", "next_cursor"), ("paging", "next", "after"),
    ("meta", "next_token"), ("pageInfo", "endCursor"),
)
_SCOPE = {"site_url": "url", "siteUrl": "url", "website_url": "url", "domain": "host", "hostname": "host"}


@dataclass(frozen=True)
class Action:
    dataset: Dataset
    slug: str
    schema: dict
    arguments: dict
    cursor: str | None
    size: int | None


def toolkit_for(source: str) -> str | None:
    row = integration_catalog().get(source, {})
    return row.get("composio")


def _is_read(slug: str, schema: dict) -> bool:
    tags = schema.get("tags")
    tags = {tag for tag in tags if isinstance(tag, str)} if isinstance(tags, list) else set()
    annotations = schema.get("annotations")
    annotations = annotations if isinstance(annotations, dict) else {}
    if _WRITE_TAGS.intersection(tags) or annotations.get("destructiveHint") is True:
        return False
    if annotations.get("readOnlyHint") is False:
        return False
    return slug in _DOCUMENTED_READS or "readOnlyHint" in tags or annotations.get("readOnlyHint") is True


def _account(connection: dict, scoped_url: str | None) -> tuple[str, str | None] | None:
    accounts = connection.get("accounts", [])
    active = [row for row in accounts if isinstance(row, dict) and str(row.get("status", "")).upper() == "ACTIVE"]
    if len(active) == 1:
        identifier = _label(active[0]["id"])
        return identifier, identifier
    if len(active) > 1 or connection.get("account_selection") == "required":
        return None
    details = connection.get("connection_details")
    identifier = details.get("connected_account_id") if isinstance(details, dict) else None
    if isinstance(identifier, str) and identifier:
        return _label(identifier), identifier
    # Legacy search may omit account IDs. Campaign provisioning pins the account
    # to its saved URL. The digest separates checkpoints after a connection change.
    if scoped_url:
        return "session-" + sha256(scoped_url.encode()).hexdigest()[:24], None
    return None


def _valid_args(schema: dict, args: dict) -> bool:
    try:
        # A provider schema may use local references. It cannot cause network lookups.
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, registry=Registry()).is_valid(args)
    except (SchemaError, Unresolvable, ValueError, TypeError, LookupError):
        return False


def _argument_plan(schema: dict, website: str, slug: str) -> tuple[dict, str | None, int | None] | None:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict) or not all(isinstance(value, dict) for value in properties.values()):
        return None
    required = set(schema.get("required", []))
    args = {}
    site = {"url": website, "host": urlsplit(website).hostname} if website else {}
    for field, kind in _SCOPE.items():
        if field in required and site.get(kind):
            args[field] = site[kind]
    if slug == "YOUTUBE_LIST_CHANNELS" and "mine" in properties:
        args["mine"] = True
    for field in ("user_id", "userId"):
        if field in required and properties.get(field, {}).get("default") == "me":
            args[field] = "me"
    size = None
    for field in _SIZE:
        spec = properties.get(field, {})
        if spec.get("type") != "integer":
            continue
        upper = spec.get("maximum", _PAGE_SIZE)
        lower = spec.get("minimum", 1)
        if type(upper) is int and type(lower) is int and 1 <= lower <= min(_PAGE_SIZE, upper):
            size = min(_PAGE_SIZE, upper)
            args[field] = size
            break
    cursor = next((name for name in _CURSORS if properties.get(name, {}).get("type") == "string"), None)
    if cursor is None and size is not None:
        cursor = next((name for name in ("offset", "page") if properties.get(name, {}).get("type") == "integer"), None)
    if cursor and properties[cursor].get("type") == "integer":
        args[cursor] = properties[cursor].get("default", 1 if cursor == "page" else 0)
    if required - args.keys() or not _valid_args(schema, args):
        return None
    return args, cursor, size


def _matching_tools(result: dict, toolkit: str) -> dict[str, dict]:
    candidates = result.get("tool_schemas", {})
    if not isinstance(candidates, dict):
        raise ValueError("Invalid Composio tool search result.")
    return {
        slug: meta for slug, meta in candidates.items()
        if isinstance(meta, dict) and meta.get("tool_slug") == slug
        and str(meta.get("toolkit", "")).lower() == toolkit
        and re.fullmatch(r"[A-Z0-9_]{1,180}", slug)
        and slug.startswith(toolkit.upper().replace("-", "_") + "_")
        and not slug.startswith("COMPOSIO_")
        and _is_read(slug, meta)
    }


def _load_schema(reports, server: str, slug: str, meta: dict, session: str) -> dict | None:
    if isinstance(meta.get("input_schema"), dict) and meta.get("hasFullSchema") is not False:
        return meta["input_schema"]
    reader = reports.composio_metadata(server, SCHEMAS)
    if reader is None:
        return None
    data = reader(SCHEMAS, {"tool_slugs": [slug], "session_id": session, "include": ["input_schema"]})
    table = data.get("tool_schemas", data.get("schemas", data.get("tools", {})))
    entry = table.get(slug, {}) if isinstance(table, dict) else {}
    schema = entry.get("input_schema") if isinstance(entry, dict) else None
    return schema if isinstance(schema, dict) else None


def _action_schema(reports, server: str, slug: str, metadata: dict, session: str) -> dict | None:
    try:
        return _load_schema(reports, server, slug, metadata, session)
    except AnalyticsError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        return None


def discover(reports, server: str, source: str, toolkit: str, scoped_url: str | None, website: str):
    """Return the coverage state, verified callable actions, and their session reader."""
    search = reports.composio_metadata(server, SEARCH)
    if search is None:
        return "unavailable", [], [], None
    tasks = (
        "list historical records, transactions, posts, and events",
        "read reports, analytics, and breakdowns",
        "list account resources and data collections",
    )
    result = search(SEARCH, {
        "queries": [{"use_case": f"In the {toolkit} toolkit, {task} with the connected account using read-only tools."}
                    for task in tasks],
        "session": {"generate_id": True},
        "search_strategy": "tool_search",
    })
    connection = next((row for row in result.get("toolkit_connection_statuses", ())
                       if row.get("toolkit") == toolkit), {})
    if not connection:
        return "unavailable", [], [], None
    if connection.get("has_active_connection") is not True:
        return "connection_required", [], [], None
    scope = _account(connection, scoped_url)
    if scope is None:
        return "account_scope_required", [], [], None
    account, selector = scope
    candidates = _matching_tools(result, toolkit)
    if not candidates:
        return "no_readable_tools", [], [], None
    session = _label(result["session"]["id"])
    read = reports.composio_reader(server, frozenset(candidates), session, selector)
    if read is None:
        return "unavailable", [], [], None
    actions, unsupported = [], []
    for slug, metadata in sorted(candidates.items()):
        dataset = Dataset(source, server, slug.lower().replace("_", "-"), account)
        schema = _action_schema(reports, server, slug, metadata, session)
        if schema is None:
            unsupported.append((dataset, "schema_unavailable"))
            continue
        if (plan := _argument_plan(schema, website, slug)) is None:
            unsupported.append((dataset, "read_inputs_required"))
            continue
        args, cursor, size = plan
        actions.append(Action(dataset, slug, schema, args, cursor, size))
    return ("connected" if actions else "no_readable_tools"), actions, unsupported, read


def _value_at(data: dict, path: tuple[str, ...]):
    value = data
    for field in path:
        if not isinstance(value, dict):
            return None
        value = value.get(field)
    return value


def _record_id(item: dict, index: str) -> str:
    for field in ("id", "record_id", "messageId", "uuid", "urn", "key", "ts"):
        value = item.get(field)
        if type(value) in (str, int) and str(value).strip() and len(str(value)) <= 400:
            return f"{index}{value}"
    content = json.dumps(item, sort_keys=True, ensure_ascii=True, allow_nan=False)
    return index + sha256(content.encode()).hexdigest()


def _records(data: dict) -> list[dict]:
    groups = [(key, value) for key, value in data.items() if isinstance(value, list)]
    if not groups:
        return [{"id": "snapshot", "data": data}] if data else []
    records = []
    for name, items in groups:
        for raw in items:
            item = raw if isinstance(raw, dict) else {"value": raw}
            prefix = "" if len(groups) == 1 else sha256(name.encode()).hexdigest()[:8] + ":"
            records.append({"id": _record_id(item, prefix), "data": item})
    return records


def _next(data, arguments, action: Action, records):
    cursor = action.cursor
    page_info = data.get("pageInfo")
    if isinstance(page_info, dict) and page_info.get("hasNextPage") is False:
        return None
    more = data.get("has_more", data.get("hasMore"))
    if more is False:
        return None
    if cursor and action.schema["properties"][cursor].get("type") == "integer":
        full = action.size is not None and len(records) == action.size
        if more is True or full:
            return str(arguments[cursor] + (1 if cursor == "page" else len(records)))
    token = next((value for path in _NEXT_PATHS
                  if isinstance(value := _value_at(data, path), str) and value.strip()), None)
    if token is None and _value_at(data, ("paging", "next")):
        token = _value_at(data, ("paging", "cursors", "after"))
        if not token:
            raise ValueError("Composio returned a continuation link without a cursor.")
    if cursor == "starting_after" and records and more is True:
        token = records[-1]["id"]
    if (token is not None and cursor is None) or (more is True and token is None):
        raise ValueError("Composio returned continuation without a supported pagination argument.")
    return token


def page(read, action: Action, progress: dict) -> dict:
    arguments = dict(action.arguments)
    if cursor := progress.get("cursor"):
        if not action.cursor:
            raise ValueError("The Composio action no longer accepts its saved continuation.")
        spec = action.schema["properties"][action.cursor]
        arguments[action.cursor] = int(cursor) if spec.get("type") == "integer" else cursor
    if not _valid_args(action.schema, arguments):
        raise ValueError("Composio arguments do not match the discovered input schema.")
    data = read(action.slug, arguments)
    for wrapper in ("data", "body", "result"):
        nested = data.get(wrapper)
        if isinstance(nested, dict):
            data = {**{key: value for key, value in data.items() if key != wrapper}, **nested}
    if data.get("error") or data.get("errors") or data.get("ok") is False:
        raise ValueError("Composio returned a provider error.")
    records = _records(data)
    following = _next(data, arguments, action, records)
    if records and records[0]["id"] != "snapshot" and not progress.get("cursor"):
        summary = {name: data[name] for name in ("totals", "summary", "breakdown", "aggregates") if name in data}
        if summary:
            records.append({"id": "@oma-report-summary", "data": summary})
    return {"records": records, "next_cursor": following}
