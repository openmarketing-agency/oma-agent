"""Discover campaign-bound MCP datasets and advance their resumable analytics streams."""

from calendar import monthrange
from datetime import date, timedelta
from functools import partial

from hermes_cli.oma_campaigns.analytics import AnalyticsError, _label
from hermes_cli.oma_campaigns.analytics_mcp import (
    _GA4, _GA4_TOOLS, _GSC, _GSC_TOOLS, _ga4_property, _search_property,
    discover_reports, ga4_page, search_page,
)
from hermes_cli.oma_campaigns.analytics_sync.data import Dataset, checkpoint
from hermes_cli.oma_campaigns.analytics_sync import composio

_LIST = "oma_analytics_list_datasets"
_READ = "oma_analytics_read_dataset"
_PAGE_SIZE = 100
_PAGES_PER_RUN = 3
_DAY = timedelta(days=1)
_SOURCE_ERRORS = (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError)
_GOOGLE = {
    _GSC: (_GSC_TOOLS, _search_property, search_page, 9, ("page", "query", "country", "device")),
    _GA4: (_GA4_TOOLS, _ga4_property, ga4_page, 7,
           ("pagePath", "eventName", "country", "deviceCategory", "sessionDefaultChannelGroup")),
}


def _history_start(source: str, today: date) -> date:
    if source == _GA4:
        # Start before GA4 existed and let the property API determine the earliest rows.
        return date(2019, 1, 1)
    year, month = divmod(today.year * 12 + today.month - 17, 12)
    return date(year, month + 1, min(today.day, monthrange(year, month + 1)[1]))


def _google_window(read, end, lower, offset, width):
    start = max(lower, end - timedelta(days=width - 1))
    rows, following_offset = read(start, end, offset)
    if following_offset is not None:
        if following_offset <= offset:
            raise ValueError("Provider pagination did not advance.")
        return rows, end, following_offset
    return rows, start - _DAY, 0


def _google_recent(read, progress, today, floor, width, replay):
    through = progress.get("through")
    anchor = date.fromisoformat(through) if through else today
    lower = max(floor, date.fromisoformat(progress["fresh_lower"]) if "fresh_lower" in progress
                else anchor - timedelta(days=replay))
    end = date.fromisoformat(progress.get("fresh_end", today.isoformat()))
    goal = progress.get("fresh_goal", today.isoformat())
    rows, following, offset = _google_window(read, max(lower, end), lower, progress.get("fresh_offset", 0), width)
    if following < lower:
        for key in ("fresh_end", "fresh_goal", "fresh_lower", "fresh_offset"):
            progress.pop(key, None)
        progress["through"] = goal
    else:
        progress.update(fresh_end=following.isoformat(), fresh_goal=goal, fresh_lower=lower.isoformat(),
                        fresh_offset=offset)
    return rows


def _google_history(directory, dataset, read, today, floor, width, replay, save) -> int:
    progress = checkpoint(directory, dataset)
    progress["from"] = floor.isoformat()
    archive_start = today - timedelta(days=replay + 1)
    progress.setdefault("archive_end", archive_start.isoformat())
    if date.fromisoformat(progress["archive_end"]) < floor:
        progress["archive_complete"] = True
    recent = _google_recent(read, progress, today, floor, width, replay)
    count = save(dataset, progress, _google_state(progress), observations=recent)
    for _ in range(_PAGES_PER_RUN - 1):
        end = date.fromisoformat(progress["archive_end"])
        if progress.get("archive_complete") or end < floor:
            break
        rows, following, offset = _google_window(read, end, floor, progress.get("archive_offset", 0), width)
        progress.update(archive_end=following.isoformat(), archive_offset=offset, archive_complete=following < floor)
        if not offset:
            progress["checked_from"] = (following + _DAY).isoformat()
        count += save(dataset, progress, _google_state(progress), observations=rows)
    return count


def _google_state(progress) -> str:
    return "current" if progress.get("archive_complete") and not progress.get("fresh_end") else "backfilling"


def _google(directory, reports, source, website, today, save) -> tuple[int, bool]:
    tools, match, page, recent_days, breakdowns = _GOOGLE[source]
    fallback = Dataset(source, "", "property", "")
    try:
        if not website:
            raise ValueError("Verified campaign website is missing.")
        read = reports.reader(tools)
        prop = match(read, website)
    except AnalyticsError:
        raise
    except _SOURCE_ERRORS:
        state = "connection_sync_required" if reports.composio_needs_sync else "unavailable"
        save(fallback, {}, state)
        return 0, False
    save(fallback, {}, "connected")
    account = prop.rsplit("/", 1)[-1] if source == _GA4 else prop
    streams = [("daily", (), 31), *((key, (key,), 1 if source == _GSC else 7) for key in breakdowns)]
    floor = _history_start(source, today)
    count, complete = 0, True
    for name, dimensions, width in streams:
        dataset = Dataset(source, "", name, account)
        read_page = partial(page, read, prop, dimensions=dimensions)
        try:
            count += _google_history(
                directory, dataset, lambda start, end, offset: read_page(start, end, offset=offset),
                today, floor, width, recent_days if name == "daily" else 2, save,
            )
        except _SOURCE_ERRORS as exc:
            if isinstance(exc, AnalyticsError) and exc.status == 409:
                raise
            save(dataset, checkpoint(directory, dataset), "read_error")
            complete = False
    return count, complete


def _token(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or not value.isprintable() or len(value) > 4096:
        raise ValueError("Invalid analytics continuation token.")
    return value


def _record_page(fetch, progress) -> tuple[list[dict], dict, str]:
    page = fetch({key: progress[key] for key in ("cursor", "checkpoint") if progress.get(key)})
    records = page["records"]
    if not isinstance(records, list) or len(records) > _PAGE_SIZE:
        raise ValueError("Invalid analytics records page.")
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
            raise ValueError("Invalid analytics record.")
    cursor = _token(page.get("next_cursor"))
    if cursor is not None:
        if cursor == progress.get("cursor"):
            raise ValueError("Analytics pagination did not advance.")
        return records, {**progress, "cursor": cursor}, "backfilling"
    marker = _token(page.get("checkpoint"))
    return records, {"checkpoint": marker}, "current"


def _record_stream(directory, dataset, fetch, save) -> tuple[int, bool]:
    progress = checkpoint(directory, dataset)
    count = 0
    try:
        for _ in range(_PAGES_PER_RUN):
            records, progress, state = _record_page(fetch, progress)
            count += save(dataset, progress, state, records=records)
            if state == "current":
                break
    except _SOURCE_ERRORS as exc:
        if isinstance(exc, AnalyticsError) and exc.status == 409:
            raise
        save(dataset, checkpoint(directory, dataset), "read_error")
        return count, False
    return count, True


def _advertised_page(read, campaign_id, dataset, progress):
    return read(_READ, {"campaign_id": campaign_id, "dataset_id": dataset.name, "integration": dataset.source,
                        "account_id": dataset.account, "limit": _PAGE_SIZE, **progress})


def _field(value, path):
    for key in path.split("."):
        value = value[key]
    return value


def _record_id(value) -> str:
    return _label(str(value) if type(value) is int else value)


def _configured_cursor(data, pagination, args, item_count):
    if not pagination:
        return None
    kind = pagination.get("kind", "cursor")
    if kind == "cursor":
        try:
            return _field(data, pagination["next"])
        except KeyError:
            return None
    page_size = args[pagination["size_parameter"]]
    if type(page_size) is not int or not 1 <= page_size <= _PAGE_SIZE or item_count > page_size:
        raise ValueError("Invalid analytics dataset page size.")
    position = args.get(pagination["parameter"], 1 if kind == "page" else 0)
    if type(position) is not int or position < 0:
        raise ValueError("Invalid analytics dataset page position.")
    return str(position + (1 if kind == "page" else item_count)) if item_count == page_size else None


def _configured_page(read, contract, progress):
    pagination = contract.get("pagination")
    args = dict(contract["arguments"])
    if pagination and (cursor := progress.get("cursor")):
        args[pagination["parameter"]] = cursor if pagination.get("kind", "cursor") == "cursor" else int(cursor)
    data = read(contract["tool"], args)
    items = _field(data, contract["items"])
    if not isinstance(items, list):
        raise ValueError("Analytics dataset item path must reference a list.")
    records = [{"id": _record_id(_field(item, contract["record_id"])), "data": item} for item in items]
    return {"records": records, "next_cursor": _configured_cursor(data, pagination, args, len(records))}


def _configured(directory, reports, campaign, sources, save) -> tuple[int, set[str], set[str]]:
    count = 0
    claimed, failed = set(), set()
    for name, spec in campaign.get("analytics_datasets", {}).items():
        dataset = Dataset(spec["integration"], spec["server"], name, spec["account"])
        if dataset.source not in sources:
            save(dataset, {}, "undeclared_integration")
            failed.add(dataset.source)
            continue
        claimed.add(dataset.source)
        reader = reports.direct_reader(dataset.server, (spec["tool"],))
        if reader is None:
            save(dataset, checkpoint(directory, dataset), "unavailable")
            failed.add(dataset.source)
            continue
        saved, ok = _record_stream(directory, dataset, partial(_configured_page, reader, spec), save)
        count += saved
        if not ok:
            failed.add(dataset.source)
    return count, claimed, failed


def _discover_server(server, read, campaign_id, sources, direct):
    manifest = read(_LIST, {"campaign_id": campaign_id, "integrations": sorted(sources)})
    entries = manifest["datasets"]
    if not isinstance(entries, list) or len(entries) > 200:
        raise ValueError("Invalid analytics dataset list.")
    datasets = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Invalid analytics dataset.")
        source = _label(item["integration"])
        # Shared connections may only supply declared sources. A campaign-owned direct
        # connector can advertise the integration matching its own configured name.
        if source in sources or (direct and source == server):
            datasets.add(Dataset(source, server, _label(item["id"]), _label(item["account_id"])))
    return sorted(datasets, key=Dataset.key)


def _generic(directory, reports, campaign, sources, save) -> tuple[int, set[str], set[str]]:
    claimed, failed = set(), set()
    count = 0
    for server in reports.tools:
        marker = Dataset("", server, "connection", "")
        reader = reports.direct_reader(server, (_LIST, _READ))
        if reader is None:
            save(marker, {}, "no_dataset_contract")
            continue
        try:
            datasets = _discover_server(server, reader, campaign["id"], sources, server in campaign.get("mcp_servers", {}))
        except _SOURCE_ERRORS as exc:
            if isinstance(exc, AnalyticsError) and exc.status == 409:
                raise
            save(marker, {}, "discovery_error")
            failed.add(server)
            continue
        save(marker, {}, "connected")
        for dataset in datasets:
            claimed.add(dataset.source)
            fetch = partial(_advertised_page, reader, campaign["id"], dataset)
            saved, ok = _record_stream(directory, dataset, fetch, save)
            count += saved
            if not ok:
                failed.add(dataset.source)
    return count, claimed, failed


def _composio_server(reports) -> str | None:
    if reports.pinned_composio:
        return "composio" if "composio" in reports.tools else None
    candidates = [name for name in reports.tools if reports.direct_reader(name, (composio.SEARCH,))]
    return candidates[0] if len(candidates) == 1 else None


def _collect_composio(directory, reports, sources, website, save) -> tuple[int, dict[str, str]]:
    server = _composio_server(reports)
    if server is None:
        states = {source: "connection_sync_required" for source in sources if composio.toolkit_for(source)}
        return 0, states if reports.composio_needs_sync else {}
    count, states = 0, {}
    for source in sorted(sources):
        toolkit = composio.toolkit_for(source)
        if not toolkit:
            continue
        try:
            state, actions, unsupported, reader = composio.discover(
                reports, server, source, toolkit, reports.scoped_url, website,
            )
        except _SOURCE_ERRORS as exc:
            if isinstance(exc, AnalyticsError) and exc.status == 409:
                raise
            states[source] = "discovery_error"
            continue
        for dataset, reason in unsupported:
            save(dataset, checkpoint(directory, dataset), reason)
        for action in actions:
            fetch = partial(composio.page, reader, action)
            saved, ok = _record_stream(directory, action.dataset, fetch, save)
            count += saved
            if not ok:
                state = "read_error"
        states[source] = state
    return count, states


def collect_integrations(directory, campaign, website, today, check_active, save) -> tuple[int, set[str]]:
    reports = discover_reports(check_active, campaign.get("mcp_servers", {}))
    sources = set(campaign.get("integrations", []))
    count, claimed, failed = _generic(directory, reports, campaign, sources, save)
    configured, configured_sources, configured_failures = _configured(directory, reports, campaign, sources, save)
    count += configured
    claimed.update(configured_sources)
    failed.update(configured_failures)
    routed, discovered = _collect_composio(directory, reports, sources - {_GSC, _GA4}, website, save)
    count += routed
    for source in sorted(sources):
        if source in _GOOGLE:
            saved, complete = _google(directory, reports, source, website, today, save)
            count += saved
            if not complete:
                failed.add(source)
        else:
            state = discovered.get(source, "unavailable")
            if source in claimed and state != "read_error":
                state = "connected"
            if state != "connected":
                failed.add(source)
            save(Dataset(source, "", "integration", ""), {}, state)
    return count, failed
