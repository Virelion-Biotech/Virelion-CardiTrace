"""Versioned schema utilities for trace interchange."""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "2.0"
SUPPORTED_MAJOR = 2


def envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **payload}


def validate_envelope(payload: dict[str, Any]) -> tuple[str, ...]:
    issues: list[str] = []
    version = str(payload.get("schema_version", ""))
    if not version:
        issues.append("missing_schema_version")
    else:
        try:
            major = int(version.split(".", 1)[0])
            if major != SUPPORTED_MAJOR:
                issues.append(f"unsupported_schema_major:{major}")
        except ValueError:
            issues.append("invalid_schema_version")
    for key in ("events", "runs", "artifacts"):
        if key not in payload:
            issues.append(f"missing:{key}")
    return tuple(issues)


def migrate_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Lossless structural migration from the original 1.x bundle format."""
    migrated = dict(payload)
    migrated["schema_version"] = SCHEMA_VERSION
    migrated.setdefault("lineage", [])
    migrated.setdefault("metadata", {})
    return migrated
