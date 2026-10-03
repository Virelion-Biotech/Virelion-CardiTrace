"""Reproducibility manifests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from .hashing import sha256_payload
from .models import ArtifactRef


@dataclass(frozen=True)
class TraceManifest:
    schema_version: str
    created_at: str
    trace_digest: str
    artifacts: tuple[dict[str, Any], ...] = ()
    runs: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(cls, artifacts: list[ArtifactRef], runs: list[Any], *, trace_digest: str, metadata: dict[str, Any] | None = None) -> "TraceManifest":
        return cls("1.0", datetime.now(timezone.utc).isoformat(), trace_digest, tuple(a.to_dict() for a in artifacts), tuple(r.to_dict() for r in runs), metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "created_at": self.created_at, "trace_digest": self.trace_digest, "artifacts": list(self.artifacts), "runs": list(self.runs), "metadata": self.metadata}

    @property
    def digest(self) -> str:
        return sha256_payload(self.to_dict())
