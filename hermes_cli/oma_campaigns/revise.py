"""Revise an installed campaign's goals, plans and tools, then sync its team.

A tool change is a plan change: an added integration must be named by a plan, and a
removed one must no longer be. Otherwise the record lists a tool that no agent is
given work for, or work for a tool the team no longer has.
"""

from hashlib import sha256
import json
from pathlib import Path

from agent.runtime_scope import bind_profile_scope
from hermes_cli import kanban_db
from hermes_cli.config import atomic_config_write
from hermes_cli.config_backend import require_file_tooling
from hermes_cli.kanban_db_connect import connect_closing
from hermes_cli.oma_campaigns.install import (
    MANAGED_FIELDS, _campaign_config_path, _campaigns_dir, _install_lock, _real_path, _status,
)
from hermes_cli.oma_campaigns.integrations import campaign_warnings, mentions, with_needed_tools
from hermes_cli.oma_campaigns.schema import validate_record
from hermes_cli.oma_campaigns.source import DEFAULT_CAMPAIGN_MODE, read_mapping
from hermes_cli.oma_campaigns.sync import sync_campaign


def _without_analyst(campaign_id: str, agents: list[str]) -> list[str]:
    return [agent for agent in agents if agent != f"{campaign_id}__analyst"]


def _check_unchanged(saved: dict, proposed: dict) -> None:
    campaign_id = saved["id"]
    if proposed.get("orchestrator", saved["orchestrator"]) != saved["orchestrator"] or (
            _without_analyst(campaign_id, proposed.get("agents", saved["agents"]))
            != _without_analyst(campaign_id, saved["agents"])):
        raise ValueError(f"{campaign_id}: revise keeps the installed roster; create a new campaign for another team")
    if proposed.get("mode", saved.get("mode", DEFAULT_CAMPAIGN_MODE)) != saved.get("mode", DEFAULT_CAMPAIGN_MODE):
        raise ValueError(f"{campaign_id}: change the mode with `mode {campaign_id} <mode>` while the campaign is stopped")


def _tool_change(saved: dict, revised: dict) -> tuple[list[str], list[str]]:
    before, after = saved.get("integrations", []), revised.get("integrations", [])
    added = [key for key in after if key not in before]
    removed = [key for key in before if key not in after]
    plans = revised.get("plans", [])
    problems = [f"{key} was added but no plan uses it; add a plan saying what it produces and which role owns it"
                for key in added if not mentions(key, plans)]
    problems += [f"{key} was removed but a plan still uses it; rewrite or remove that plan"
                 for key in removed if mentions(key, plans)]
    if problems:
        raise ValueError(f"{saved['id']}: " + "; ".join(problems))
    return added, removed


def _replan_body(config_path: Path, added: list[str], removed: list[str]) -> str:
    changes = [f"added {', '.join(added)}" if added else "", f"removed {', '.join(removed)}" if removed else ""]
    return (
        f"The campaign's tools changed: {'; '.join(change for change in changes if change)}.\n\n"
        f"- Read the revised goals and plans in `{config_path}`.\n"
        "- For each added tool, create or update tasks so the role that owns it has work, starting with the "
        "first deliverable its plan names. Use Tool Search to confirm the tool is reachable before assigning work "
        "that needs it, and note a missing connection on the card instead of guessing.\n"
        "- For each removed tool, cancel or rewrite open tasks that depend on it.\n"
        "- Hand back a short summary of the tasks you created, changed or cancelled."
    )


def _queue_replan(home: Path, config_path: Path, config: dict, added: list[str], removed: list[str]) -> str | None:
    """Wake the orchestrator for a tool change on a running campaign; once per change."""
    if not (added or removed) or config.get("lifecycle_state") != "resumed":
        return None
    if config.get("mode", DEFAULT_CAMPAIGN_MODE) == "control":
        return None
    change = json.dumps({"added": added, "removed": removed, "integrations": sorted(config.get("integrations", []))})
    board = config["kanban_board"]
    with bind_profile_scope(home, hydrate_secrets=False), connect_closing(board=board) as conn:
        return kanban_db.create_task(
            conn, board=board, assignee=config["orchestrator"], created_by="oma-campaigns",
            title="Re-plan work for the campaign's changed tools",
            body=_replan_body(config_path, added, removed),
            idempotency_key=f"oma-tools:{config['id']}:{sha256(change.encode()).hexdigest()[:16]}",
        )


def revise(home: Path, campaign_id: str, definition: Path) -> dict:
    """Apply a revised definition to an installed campaign. Fields left out keep their saved values."""
    require_file_tooling("OMA campaign revision")
    proposed = read_mapping(_real_path(definition))
    if proposed.get("id") != campaign_id:
        raise ValueError(f"The definition's id must be {campaign_id!r}")
    if fields := MANAGED_FIELDS & proposed.keys():
        raise ValueError(f"Revision manages these fields: {', '.join(sorted(fields))}")
    path = _campaign_config_path(_campaigns_dir(home), campaign_id)
    with _install_lock(path):
        saved = read_mapping(path)
        if _status(home, campaign_id, saved)["state"] != "installed":
            raise ValueError(f"Campaign {campaign_id!r} is not installed; use create for a new campaign")
        _check_unchanged(saved, proposed)
        authored = {**saved, **proposed, "agents": saved["agents"]}
        validate_record("campaign", authored, definition)
        # Check the plans the user wrote: the plan lines added for needs name the tools they serve.
        added, removed = _tool_change(saved, authored)
        revised, needed = with_needed_tools(home, authored)
        validate_record("campaign", revised, definition)
        added += [key for key in needed if key not in saved.get("integrations", [])]
        atomic_config_write(path, revised)
    synced = sync_campaign(home, campaign_id)
    return {
        "id": campaign_id, "added": added, "removed": removed, "added_for_needs": needed,
        "updated_agents": synced["updated_agents"],
        "replan_task": _queue_replan(home, path, revised, added, removed),
        "warnings": campaign_warnings(revised),
    }
