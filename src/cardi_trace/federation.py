"""Cross-repository trace federation utilities.

Federation exchanges references and signed-like integrity commitments rather than
requiring a shared database. Each repository can keep its own ledger and later
join traces through correlation IDs and artifact identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import uuid

from .hashing import sha256_payload
from .merkle import recorder_merkle_root


@dataclass(frozen=True)
class TraceEnvelope:
    envelope_id: str
    source: str
    target: str
    trace_id: str
    created_at: str
    merkle_root: str
    artifact_ids: tuple[str, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "source": self.source,
            "target": self.target,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "merkle_root": self.merkle_root,
            "artifact_ids": list(self.artifact_ids),
            "metadata": self.metadata,
        }

    @property
    def digest(self) -> str:
        return sha256_payload(self.to_dict())


def create_envelope(recorder, *, source: str, target: str, trace_id: str | None = None, metadata: dict[str, Any] | None = None) -> TraceEnvelope:
    return TraceEnvelope(
        envelope_id=str(uuid.uuid4()),
        source=source,
        target=target,
        trace_id=trace_id or str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        merkle_root=recorder_merkle_root(recorder),
        artifact_ids=tuple(sorted(a.artifact_id for a in recorder.artifacts)),
        metadata=metadata or {},
    )


def verify_envelope(envelope: TraceEnvelope, recorder) -> tuple[str, ...]:
    issues: list[str] = []
    if envelope.merkle_root != recorder_merkle_root(recorder):
        issues.append("merkle_root_mismatch")
    actual = {a.artifact_id for a in recorder.artifacts}
    missing = sorted(set(envelope.artifact_ids) - actual)
    if missing:
        issues.append("missing_artifacts:" + ",".join(missing))
    return tuple(issues)
