"""Core immutable data structures for CardiTrace."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
import time
import uuid


class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class TraceStatus(_StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(_StrEnum):
    FILE = "file"
    PAYLOAD = "payload"
    DIRECTORY = "directory"
    MODEL = "model"
    DATASET = "dataset"
    REPORT = "report"
    CODE = "code"
    CONFIG = "config"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ArtifactRef:
    """Content-addressed identity of an artifact or in-memory payload."""
    artifact_id: str
    digest: str
    kind: str = ArtifactKind.UNKNOWN
    media_type: str | None = None
    name: str | None = None
    size_bytes: int | None = None
    uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, digest: str, **kwargs: Any) -> "ArtifactRef":
        return cls(artifact_id=f"sha256:{digest}", digest=digest, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceEvent:
    """One append-only provenance event."""
    event_id: str
    timestamp: float
    event_type: str
    run_id: str | None
    actor: str
    component: str
    payload: dict[str, Any]
    previous_hash: str | None
    event_hash: str

    @classmethod
    def new(cls, *, event_type: str, actor: str, component: str, payload: dict[str, Any], run_id: str | None = None, timestamp: float | None = None, event_id: str | None = None, previous_hash: str | None = None) -> "TraceEvent":
        return cls(event_id=event_id or str(uuid.uuid4()), timestamp=timestamp if timestamp is not None else time.time(), event_type=event_type, run_id=run_id, actor=actor, component=component, payload=payload, previous_hash=previous_hash, event_hash="")

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    component: str
    operation: str
    started_at: float
    finished_at: float | None
    status: str
    parameters: dict[str, Any]
    environment: dict[str, Any]
    code_identity: str | None = None
    parent_run_id: str | None = None
    input_artifacts: tuple[str, ...] = ()
    output_artifacts: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, component: str, operation: str, **kwargs: Any) -> "RunRecord":
        return cls(run_id=str(uuid.uuid4()), component=component, operation=operation, started_at=time.time(), finished_at=None, status=TraceStatus.RUNNING, parameters=kwargs.pop("parameters", {}), environment=kwargs.pop("environment", {}), **kwargs)

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class LineageEdge:
    source_id: str
    target_id: str
    relation: str
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    message: str
    subject: str | None = None

    def to_dict(self) -> dict[str, Any]: return asdict(self)
