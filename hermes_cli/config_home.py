"""Directory initialization and storage diagnostics for the active Hermes home."""

import os
import shutil
from pathlib import Path

from hermes_constants import get_default_hermes_root
from hermes_dir_acl import make_user_dir

OMA_CAMPAIGN_SKILL = "oma-campaigns"
MAINTENANCE_TEMPLATE = Path(__file__).parent / "data" / "profiles" / "maintenance"


class HomeInitializationError(RuntimeError):
    """The home skeleton is unavailable, not an invalid YAML document."""


def _directory_links(path: Path) -> list[Path]:
    return [part for part in (*reversed(path.parents), path) if part.is_symlink()]


def _operator_owned_links(links: list[Path], home: Path) -> list[Path]:
    """Keep only the links that make the operator the owner of the home's permissions.

    That boundary is the home itself and anything under it. A link *above* the home
    (macOS ``/tmp`` -> ``/private/tmp``, ``/var`` -> ``/private/var``, or any aliased parent
    the user happens to live in) says nothing about who owns :data:`home`, and treating it as
    an operator-owned link left a fresh home and its ``cron``/``sessions``/``logs``/``memories``
    subdirectories at the default ``0o755`` instead of ``0o700``.
    """
    return [link for link in links if link == home or home in link.parents]


def _ensure_directory(path: Path, *, create: bool, secure: bool, home: Path) -> None:
    from hermes_cli.config import _secure_dir

    detail = ""
    try:
        links = _directory_links(path)
        detail = "; ".join(f"{link} -> {link.readlink()}" for link in links)
        # Never materialize a missing mount's target on the underlying disk.
        for link in links:
            if not link.is_dir():
                raise FileNotFoundError(f"Directory link is unavailable: {link}")
        if create:
            make_user_dir(path, parents=True, exist_ok=True)
        elif not path.is_dir():
            raise FileNotFoundError(f"Required directory does not exist: {path}")
        # The operator owns permissions beyond a link, including logs/curator.
        if secure and not _operator_owned_links(links, home):
            _secure_dir(path)
    except OSError as exc:
        raise HomeInitializationError(
            f"Cannot initialize Hermes directory {path}: {exc}. "
            + (f"Directory links: {detail}. " if detail else "")
            + "Check the directory/link target, mount availability and access permissions; "
            "restore the mount or repair the link before retrying. "
            "Hermes has not replaced the link or created its missing target."
        ) from exc


def initialize_home(home: Path, subdirs: tuple[str, ...], ensured: set[str]) -> None:
    from hermes_cli.config import _ensure_default_soul_md, is_managed

    managed = is_managed()
    old_umask = os.umask(0o007) if managed else None
    try:
        _ensure_directory(home, create=not managed, secure=not managed, home=home)
        required = ("cron", "sessions", "logs", "memories") if managed else subdirs
        for subdir in required:
            _ensure_directory(home / subdir, create=not managed, secure=not managed, home=home)
        if managed:
            _ensure_directory(home / "logs" / "curator", create=True, secure=False, home=home)
        try:
            _ensure_default_soul_md(home)
        except OSError as exc:
            raise HomeInitializationError(
                f"Cannot initialize Hermes home {home}: {exc}. "
                "Check storage availability and access permissions."
            ) from exc
    finally:
        if old_umask is not None:
            os.umask(old_umask)
    # Plugin discovery rebinds the resolved home. Do not repeat chmod through
    # that spelling after the operator-owned symlink boundary has been lost.
    ensured.update((str(home), str(home.resolve())))


def seed_empty_env_file(path: Path) -> bool:
    """Create a private, empty dotenv file without replacing an existing path."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def seed_config_file(config_path: Path, *, model_seed: dict | None = None) -> bool:
    """Write the OMA starter policy only if the target has no config."""
    from hermes_cli.config import _secure_file, atomic_config_write
    from hermes_cli.config_backend import config_exists
    from hermes_cli.config_defaults import DEFAULT_CONFIG
    from hermes_cli.config_version_stamp import note_first_stamp

    if config_exists(config_path) or config_path.is_symlink():
        return False

    enabled_toolsets = ["file", "terminal", "browser", "camofox", "web", "skills", "memory", "session_search"]
    eager_toolsets = ["file", "terminal", "skills", "memory"]
    home = config_path.parent
    is_default = home.resolve() == get_default_hermes_root(home=home).resolve()
    if is_default:
        enabled_toolsets.extend(["clarify", "kanban"])
        eager_toolsets.append("clarify")
    config = {
        "agent": {"enabled_toolsets": enabled_toolsets},
        "tools": {"tool_search": {
            "enabled": "on", "eager_toolsets": eager_toolsets, "listing": "off",
        }},
        "skills": {"disabled": []},
        "approvals": {
            "mode": "off",
            "timeout": 300,
            "cron_mode": "approve",
            "single_query_mode": "approve",
            "unattended_mode": "approve",
            "approvers": ["*"],
            "mcp_reload_confirm": False,
            "destructive_slash_confirm": False,
        },
        "_config_version": DEFAULT_CONFIG["_config_version"],
        **(model_seed or {}),
    }
    if is_default:
        config["kanban"] = {"orchestrator_profile": "default"}
    note_first_stamp(config_path.parent, {}, config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_config_write(config_path, config)
    _secure_file(config_path)
    return True


def _initialize_maintenance_profile(staging: Path) -> None:
    from agent.runtime_scope import bind_profile_scope
    from hermes_cli.config import _deep_merge, atomic_config_write, read_user_config_raw
    from hermes_cli.config_backend import FileBackend
    from tools.skills_sync import sync_skills

    path = staging / "config.yaml"
    overrides = FileBackend.read_path(MAINTENANCE_TEMPLATE / "config.yaml")
    atomic_config_write(path, _deep_merge(read_user_config_raw(path), overrides))
    with bind_profile_scope(staging, hydrate_secrets=False):
        sync_skills(quiet=True)
    shutil.copytree(MAINTENANCE_TEMPLATE / "skills", staging / "skills", dirs_exist_ok=True)


def _seed_maintenance_profile(home: Path) -> None:
    from hermes_cli.profile_provision import ProfileCreateRequest, provision_profile
    from hermes_cli.profiles import get_profile_dir
    from hermes_constants import named_profile_is_deleted

    target = get_profile_dir("maintenance")
    if target.parent.parent.resolve() != home.resolve():
        raise ValueError("Maintenance profile does not resolve under the install home")
    if target.exists() or target.is_symlink() or named_profile_is_deleted(target):
        return
    request = ProfileCreateRequest(
        name="maintenance", description="Maintain and troubleshoot OMA Agent.",
        soul=(MAINTENANCE_TEMPLATE / "SOUL.md").read_text(encoding="utf-8-sig"),
        alias=False, mirror_credentials=False,
    )
    try:
        provision_profile(request, initialize=_initialize_maintenance_profile)
    except FileExistsError:
        if not (target.exists() or target.is_symlink()):
            raise


def seed_install_config() -> None:
    """Seed a fresh file-backed install and its starter maintenance profile."""
    from hermes_cli.config import get_config_path
    from hermes_cli.config_backend import supports_file_tooling
    from hermes_cli.env_loader import selected_config_backend_name

    path = get_config_path()
    if selected_config_backend_name(path.parent) != "remote" and supports_file_tooling():
        if seed_config_file(path) and path.parent.resolve() == get_default_hermes_root(home=path.parent).resolve():
            _seed_maintenance_profile(path.parent)


def config_load_issue(exc: Exception):
    from hermes_cli.config_issues import ConfigIssue

    if isinstance(exc, (HomeInitializationError, OSError)):
        return ConfigIssue(
            "error", f"Hermes storage is unavailable: {exc}",
            "Check the reported path, link target, mount and permissions; keep config.yaml unchanged.",
        )
    return ConfigIssue("error", "Could not load config.yaml", "Run 'hermes setup' to create a valid config")
