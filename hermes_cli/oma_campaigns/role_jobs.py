"""Reconcile only OMA-owned schedules in the owning profile's native cron store."""

from pathlib import Path
from uuid import uuid4

from agent.runtime_scope import bind_profile_scope
from cron.job_definition import JOB_DEFINITION_FIELDS, merge_job_definition
from cron.jobs import _jobs_lock, compute_next_run, is_job_runnable, load_jobs, parse_schedule, save_jobs, use_cron_store
from cron.jobs_time import normalize_timezone
from cron.lifecycle_guard import check_gateway_lifecycle
from hermes_cli.oma_campaigns.source import _job_ids, _member
from hermes_time import now

_OWNER = "oma_job_id"
_LEGACY_PREFIX = "oma:"
AWAITING_ACTIVATION = "Created by OMA sync; awaiting operator activation."


def _verify_paths(profile: Path) -> None:
    root = _member(profile, "cron")
    _member(root, "jobs.json")
    _member(root, ".jobs.lock")


def _definitions(declarations: list) -> dict:
    definitions = {}
    for raw in declarations:
        source_id = raw["id"]
        prompt = raw["prompt"].strip()
        schedule = parse_schedule(raw["schedule"])
        zone = normalize_timezone(raw.get("timezone"))
        check_gateway_lifecycle(prompt, None)
        definitions[source_id] = {
            "name": raw.get("name", _LEGACY_PREFIX + source_id).strip(), "prompt": prompt,
            "schedule": schedule, "schedule_display": schedule.get("display", raw["schedule"]),
            "timezone": zone, "repeat": {"times": raw.get("repeat", 1 if schedule["kind"] == "once" else None)},
            "deliver": "local",
        }
    return definitions


def _legacy_source(job: dict) -> str | None:
    name = job.get("name")
    if isinstance(name, str) and name.startswith(_LEGACY_PREFIX):
        return name.removeprefix(_LEGACY_PREFIX)
    return None


def _can_manage_legacy_job(job: dict) -> bool:
    # A creator origin does not change local delivery. Never take over a job
    # that can send externally or runs extra automation outside the declaration.
    return (
        job.get("deliver") == "local"
        and job.get("failure_deliver") in (None, "local")
        and not any(job.get(key) for key in (
            "script", "no_agent", "monitor_script", "monitor_url", "skills", "skill", "attach_to_session", "context_from",
        ))
    )


def _matches_declaration(job: dict, declaration: dict) -> bool:
    old_schedule = job.get("schedule") or {}
    display = declaration["schedule_display"]
    # Parsing "in 2h" again computes a new instant, not a new declaration.
    same_relative_delay = display.startswith("once in ") and old_schedule.get("display") == display
    return (
        (same_relative_delay or old_schedule == declaration["schedule"])
        and all(job.get(key) == declaration[key] for key in ("name", "prompt", "timezone"))
        and (job.get("repeat") or {}).get("times") == declaration["repeat"]["times"]
    )


def _new_job(source_id: str, declaration: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    # Preserve native options that OMA does not declare, not old scheduler state.
    options = {k: v for k, v in previous.items() if k in JOB_DEFINITION_FIELDS}
    definition = {**options, **declaration, "deliver": previous.get("deliver", "local")}
    schedule = declaration["schedule"]
    runnable = bool(previous) and previous.get("state") != "completed" and is_job_runnable(previous)
    one_time = schedule["kind"] == "once"
    next_run = compute_next_run(schedule, timezone=declaration["timezone"]) if runnable or one_time else None
    if one_time and next_run is None:
        raise ValueError(f"OMA job {source_id!r} has a one-time schedule in the past")
    created_at = now().isoformat()
    seed = {"id": "oma-" + uuid4().hex[:24], _OWNER: source_id, "created_at": created_at, "enabled": False}
    if "interpreter" in previous:
        seed["interpreter"] = previous["interpreter"]
    replacement = merge_job_definition(seed, definition)
    replacement.update(
        enabled=runnable, state="scheduled" if runnable else "paused", next_run_at=next_run if runnable else None,
        paused_at=None if runnable else previous.get("paused_at") or created_at,
        paused_reason=None if runnable else previous.get("paused_reason") or AWAITING_ACTIVATION,
    )
    return replacement


def _reconcile(current: list, definitions: dict) -> tuple[list, set[str]]:
    updated, removed = [], set()
    pending = dict(definitions)
    for existing in current:
        job_id = existing.get("id")
        source_id = existing.get(_OWNER) or _legacy_source(existing)
        if isinstance(source_id, str) and source_id in definitions:
            declaration = pending.pop(source_id, None)
            if declaration is None:
                raise ValueError("More than one native job matches an OMA declaration")
            if _OWNER not in existing and not _can_manage_legacy_job(existing):
                raise ValueError("An existing job uses a reserved OMA name but is not a local OMA review")
            if _matches_declaration(existing, declaration):
                updated.append({**existing, _OWNER: source_id})
            else:
                updated.append(_new_job(source_id, declaration, existing))
                removed.add(job_id)
        elif _OWNER in existing:
            removed.add(job_id)
        else:
            updated.append(existing)
    for source_id, declaration in pending.items():
        updated.append(_new_job(source_id, declaration))
    return updated, removed


def plan_role_jobs(profile: Path, declarations: list | None) -> dict | None:
    if declarations is None:
        return None
    _job_ids(declarations, profile.name)
    _verify_paths(profile)
    with bind_profile_scope(profile, hydrate_secrets=False), use_cron_store(profile):
        definitions = _definitions(declarations)
        if definitions or (profile / "cron" / "jobs.json").exists():
            _reconcile(load_jobs(), definitions)
    return definitions


def apply_role_jobs(profile: Path, definitions: dict | None) -> bool:
    if definitions is None or (not definitions and not (profile / "cron" / "jobs.json").exists()):
        return False
    _verify_paths(profile)
    with use_cron_store(profile), _jobs_lock():
        current = load_jobs()
        updated, removed = _reconcile(current, definitions)
        if updated == current:
            return False
        save_jobs(updated, removed_ids=removed)
        return True
