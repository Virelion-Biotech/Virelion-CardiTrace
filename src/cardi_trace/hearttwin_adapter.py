"""HeartTwin local-command adapter for CardiTrace provenance recording."""
from __future__ import annotations

import hashlib
import json
import os
import string
import sys
from pathlib import Path
from typing import Any

from .models import TraceStatus
from .recorder import TraceRecorder


def _canonical_json(value: Any) -> bytes:
    """Match HeartTwin's strict canonical JSON encoding for canonical state."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _verify_canonical_state(payload: dict[str, Any]) -> str | None:
    """Independently verify a claimed HeartTwin CardiacState fingerprint.

    Older/generic trace callers that do not send a canonical-state fingerprint
    remain supported. Once a fingerprint is supplied, however, CardiTrace
    fails closed unless the embedded state exists and hashes to that value.
    """
    expected = payload.get("canonical_state_fingerprint")
    if expected is None:
        return None
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(ch not in string.hexdigits for ch in expected)
    ):
        raise ValueError("canonical_state_fingerprint must be a 64-character SHA-256 hex string")
    expected = expected.lower()

    workflow_state = payload.get("workflow_state")
    if not isinstance(workflow_state, dict):
        raise ValueError(
            "canonical_state_fingerprint was supplied without workflow_state"
        )
    state = workflow_state.get("cardiac_state")
    if not isinstance(state, dict):
        raise ValueError(
            "canonical_state_fingerprint was supplied without workflow_state.cardiac_state"
        )

    state_payload = dict(state)
    embedded = state_payload.pop("state_fingerprint", None)
    if embedded is not None and str(embedded).lower() != expected:
        raise ValueError(
            "Embedded CardiacState state_fingerprint does not match the claimed canonical fingerprint"
        )

    observed = hashlib.sha256(_canonical_json(state_payload)).hexdigest()
    if observed != expected:
        raise ValueError(
            "CardiacState canonical fingerprint mismatch: traced state was modified or mis-serialized"
        )
    return observed


def main() -> int:
    raw = sys.stdin.read() if os.environ.get("HEARTTWIN_PAYLOAD_STDIN") == "1" else os.environ.get("HEARTTWIN_PAYLOAD")
    if not raw:
        print("HEARTTWIN_PAYLOAD environment variable not set", file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("HeartTwin trace payload must be a JSON object")
        verified_state_fingerprint = _verify_canonical_state(payload)

        root = Path(os.environ.get("CARDITRACE_ROOT", ".carditrace"))
        recorder = TraceRecorder(root, actor="hearttwin", component="HeartTwin")
        entity_id = str(payload.get("entity_id", "unknown"))
        run = recorder.start_run(
            component="HeartTwin",
            operation="twin_run",
            parameters={"entity_id": entity_id, "context": payload.get("context", {})},
            metadata={
                "hearttwin_payload_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "canonical_state_fingerprint": verified_state_fingerprint,
                "canonical_state_verified": verified_state_fingerprint is not None,
            },
        )
        input_artifact = recorder.register_payload(payload, role="input", name=f"hearttwin:{entity_id}")
        recorder.attach_input(run.run_id, input_artifact)
        recorder.finish_run(
            run.run_id,
            status=TraceStatus.SUCCEEDED,
            metadata={
                "entity_id": entity_id,
                "canonical_state_fingerprint": verified_state_fingerprint,
                "canonical_state_verified": verified_state_fingerprint is not None,
            },
        )
        finished = next(item for item in recorder.runs if item.run_id == run.run_id)
        print(json.dumps({
            "run_id": finished.run_id,
            "status": finished.status,
            "execution_fingerprint": finished.metadata.get("execution_fingerprint"),
            "input_artifact_id": input_artifact.artifact_id,
            "trace_root": str(root.resolve()),
            "canonical_state_fingerprint": verified_state_fingerprint,
            "canonical_state_verified": verified_state_fingerprint is not None,
        }, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - translate to adapter contract
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
