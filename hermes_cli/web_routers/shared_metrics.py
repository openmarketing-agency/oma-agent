"""Read-only compatibility responses for dashboards that still ask about telemetry."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ConsentAnswer(BaseModel):
    enabled: bool
    send: bool = False


def _read_consent() -> dict:
    """Keep older dashboards from offering the retired feature."""
    from hermes_cli.observability.shared_metrics_consent import consent_state

    return {**consent_state(), "managed": True}


@router.get("/api/shared-metrics/consent")
async def get_shared_metrics_consent(profile: Optional[str] = None):
    return _read_consent()


@router.put("/api/shared-metrics/consent")
async def put_shared_metrics_consent(body: ConsentAnswer, profile: Optional[str] = None):
    return _read_consent()
