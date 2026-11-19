"""Compatibility response for older clients that ask about shared metrics."""

from typing import Any


def consent_state(raw_cfg: Any = None) -> dict[str, bool]:
    """OMA Agent never collects or sends shared metrics, regardless of saved consent."""
    return {"enabled": False, "send": False, "decided": True, "reask": False}
