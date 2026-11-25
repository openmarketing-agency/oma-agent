"""Default SOUL.md template seeded into HERMES_HOME on first run."""

from hashlib import sha256
from pathlib import Path

from hermes_cli._startup_fast import project_root_str
from hermes_constants import get_default_hermes_root

DEFAULT_SOUL_MD = "You are OMA Agent built by Open Marketing Agency powered by Hermes Agent."


def _is_default_home(home: Path) -> bool:
    return home.resolve() == get_default_hermes_root(home=home).resolve()


def starter_soul(home: Path) -> str:
    if not _is_default_home(home):
        return DEFAULT_SOUL_MD
    return (Path(project_root_str()) / "SOUL.md").read_text(encoding="utf-8-sig")


_LEGACY_ROOT_SOUL_WITH_OMA_SKILLS = DEFAULT_SOUL_MD + "\n\n" + (
    "Choose the OMA skill that matches the user's request:\n\n"
    "- `oma-onboarding`: Get started, or add campaigns or agents to existing OMA work.\n"
    "- `oma-brands`: Create or update brands, logos, and brand knowledge.\n"
    "- `oma-playbooks`: Create or refine a brand's strategy.\n"
    "- `oma-campaigns`: Install or inspect campaigns and manage their goals, plans, and playbook links.\n"
    "- `oma-agents`: Manage agent records, personas, settings, and saved files."
)
_LEGACY_ROOT_SOUL_WITH_CLARIFY = _LEGACY_ROOT_SOUL_WITH_OMA_SKILLS + "\n\n" + (
    "Use `clarify` when you need the user's feedback, preferences, or a decision, especially during OMA onboarding. "
    "Ask focused questions and offer choices when helpful. If `clarify` is not listed, look for it with Tool Search. "
    "If it is unavailable, ask in chat. Do not treat a skipped or unanswered question as agreement."
)

_SCAFFOLD_HEAD = (
    "# Hermes Agent Persona\n\n<!--\nThis file defines the agent's personality and tone.\n"
    "The agent will embody whatever you write here.\nEdit this to customize how Hermes communicates with you.\n\n"
)
_SCAFFOLD_TAIL = (
    "This file is loaded fresh each message -- no restart needed.\n"
    "Delete the contents (or this file) to use the default personality.\n-->"
)

# Fingerprint of the normalized root starter before it gained paused campaign creation.
# Match exactly so a user-edited persona is never replaced.
_PRE_PAUSED_CREATE_OMA_SOUL_SHA256 = "3c1ad6dfa54bd14191da512a3741103be4b0c92699d17a1a8b2a850a6b7ea14d"

# Auto-seeded SOUL.md content that carries zero user intent, so a matching file is safe to upgrade
# to the current starter: comment-only scaffolds older installers wrote, plus earlier generations
# of the auto-seeded default text. Compared on
# normalized content (stripped, line endings unified). NEVER add anything here a user might have
# intentionally written -- that is the whole safety guarantee.
_LEGACY_TEMPLATE_SOULS = (
    DEFAULT_SOUL_MD + "\n\nUse the `oma-playbooks` skill to manage playbooks.",
    DEFAULT_SOUL_MD + "\n\nUse the `oma-campaigns` skill to manage playbooks.",
    _LEGACY_ROOT_SOUL_WITH_OMA_SKILLS,
    _LEGACY_ROOT_SOUL_WITH_CLARIFY,
    _SCAFFOLD_HEAD + (
        "Examples:\n"
        '  - "You are a warm, playful assistant who uses kaomoji occasionally."\n'
        '  - "You are a concise technical expert. No fluff, just facts."\n'
        '  - "You speak like a friendly coworker who happens to know everything."\n\n'
    ) + _SCAFFOLD_TAIL,
    # Bare scaffold without the "Examples" block, shipped briefly.
    _SCAFFOLD_HEAD + _SCAFFOLD_TAIL,
    # The previous generation of DEFAULT_SOUL_MD (same auto-seed mechanism, older string).
    (
        "You are Hermes Agent, an intelligent AI assistant created by Nous Research. You are helpful, "
        "knowledgeable, and direct. You assist users with a wide range of tasks including answering questions, "
        "writing and editing code, analyzing information, creative work, and executing actions via your tools. "
        "You communicate clearly, admit uncertainty when appropriate, and prioritize being genuinely useful over "
        "being verbose unless otherwise directed below. Be targeted and efficient in your exploration and "
        "investigations."
    ),
    # Historical ASCII-dashed Windows installer template.
    (
        "You are Hermes Agent, built by Nous Research. Be direct: match the length of your reply to the weight of "
        "the ask -- a one-line question gets a one-line answer, and finished work gets a short report of what "
        "changed, what's verified, and what's left, never a replay of the process. No filler (\"Great question,\" "
        "\"I'd be happy to\"), no restating the request back, no re-summarizing what you already said, no narrating "
        "tool calls the user can see. Plain claims over adjectives; when unsure, say so plainly. Agree because it's "
        "right, not because the user said it. Depth is earned -- give it when the user asks for detail, teaches, or "
        "the stakes demand it, not by default."
    ),
)


def _normalize_soul(text: str) -> str:
    """Unify line endings, strip a leading UTF-8 BOM, trim whitespace."""
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()


def is_legacy_template_soul(text: str, *, home: Path | None = None) -> bool:
    """True if ``text`` is a non-customized, auto-seeded SOUL.md.

    Only known historical installer templates count; any edit outside those exact
    strings is treated as user intent and preserved.
    """
    normalized = _normalize_soul(text)
    if (
        home is not None
        and sha256(normalized.encode("utf-8")).hexdigest() == _PRE_PAUSED_CREATE_OMA_SOUL_SHA256
        and _is_default_home(home)
    ):
        return True
    return any(normalized == _normalize_soul(t) for t in _LEGACY_TEMPLATE_SOULS)
