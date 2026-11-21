"""Validate authored records against the shared OMA JSON Schemas."""

from functools import lru_cache
from importlib.resources import files
import json
from pathlib import Path

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

KINDS = ("brand", "playbook", "campaign", "agent")


@lru_cache(maxsize=len(KINDS))
def _validator(kind: str) -> Draft202012Validator:
    if kind not in KINDS:
        raise ValueError(f"Expected one of: {', '.join(KINDS)}")
    path = files("hermes_cli.oma_campaigns").joinpath("schemas", f"{kind}.schema.json")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8-sig")))


def validate_record(kind: str, record: dict, context: str | Path) -> None:
    error = next(_validator(kind).iter_errors(record), None)
    if error is not None:
        # Validator messages can include entire sections, including credential values.
        field = ".".join(map(str, error.absolute_path)) or "record"
        if error.validator == "required":
            missing = ", ".join(key for key in error.validator_value if key not in error.instance)
            raise ValueError(f"{context}: invalid OMA {kind} {field} (missing: {missing})")
        raise ValueError(f"{context}: invalid OMA {kind} {field} ({error.validator})")
