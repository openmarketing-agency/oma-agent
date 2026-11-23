"""Reconcile only OMA-owned schedules in the owning profile's native cron store."""

from hashlib import sha256
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from cron.job_definition import merge_job_definition
from cron.jobs import _jobs_lock, compute_next_run, load_jobs, parse_schedule, save_jobs, use_cron_store
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


def _reconcile(current: list, definitions: dict) -> tuple[list, set[str]]:
    updated, removed = [], set()
    pending = dict(definitions)
    for existing in current:
        job_id = existing.get("id")
        source_id = existing.get(_OWNER) or _legacy_source(existing)
        if source_id in definitions:
            declaration = pending.pop(source_id, None)
            if declaration is None:
                raise ValueError("More than one native job matches an OMA declaration")
            if _OWNER not in existing and (existing.get("deliver") != "local" or any(
                existing.get(key) for key in ("script", "no_agent", "monitor_script", "monitor_url", "skills", "skill", "origin")
            )):
                raise ValueError("An existing job uses a reserved OMA name but is not a local OMA review")
            # Only replace the declared settings, not operator-owned delivery or native options.
            definition = {**existing, **{k: v for k, v in declaration.items() if k != "deliver"}}
            # An unchanged "in 2h" must keep its original absolute instant.
            display = declaration["schedule_display"]
            if display.startswith("once in ") and (existing.get("schedule") or {}).get("display") == display:
                definition["schedule"] = existing["schedule"]
            merged = merge_job_definition({**existing, _OWNER: source_id}, definition)
            times = merged["repeat"]["times"]
            if times is not None and merged["repeat"]["completed"] >= times and merged.get("enabled", True):
                merged.update(enabled=False, state="completed", next_run_at=None)
                merged.pop("pending_slot", None)
            updated.append(merged)
        elif _OWNER in existing:
            removed.add(job_id)
        else:
            updated.append(existing)
    native_ids = {job.get("id") for job in current}
    for source_id, declaration in pending.items():
        job_id = "oma-" + sha256(source_id.encode()).hexdigest()[:24]
        if job_id in native_ids:
            raise ValueError("An OMA job ID conflicts with an existing native job")
        if declaration["schedule"]["kind"] == "once" and compute_next_run(
            declaration["schedule"], timezone=declaration["timezone"],
        ) is None:
            raise ValueError(f"OMA job {source_id!r} has a one-time schedule in the past")
        created_at = now().isoformat()
        seed = {"id": job_id, _OWNER: source_id, "state": "paused", "enabled": False,
                "created_at": created_at, "paused_at": created_at, "next_run_at": None,
                "paused_reason": AWAITING_ACTIVATION}
        updated.append(merge_job_definition(seed, declaration))
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
