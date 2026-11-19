"""Compatibility shape for the retired OMA shared-metrics sender."""

from dataclasses import dataclass

DEFAULT_ENDPOINT = ""


@dataclass(frozen=True)
class SendConfig:
    enabled: bool
    send: bool
    endpoint: str


def resolve_send_config(config: dict | None) -> SendConfig:
    """Legacy config cannot enable shared-metrics collection or upload."""
    return SendConfig(enabled=False, send=False, endpoint=DEFAULT_ENDPOINT)
