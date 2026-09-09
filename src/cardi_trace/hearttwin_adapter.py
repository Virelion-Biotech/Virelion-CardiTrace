"""HeartTwin local-command adapter for CardiTrace provenance recording."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .models import TraceStatus
from .recorder import TraceRecorder


def main() -> int:
    raw = os.environ.get("HEARTTWIN_PAYLOAD")
    if not raw:
        print("HEARTTWIN_PAYLOAD environment variable not set", file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw)
        root = Path(os.environ.get("CARDITRACE_ROOT", ".carditrace"))
        recorder = TraceRecorder(root, actor="hearttwin", component="HeartTwin")
        entity_id = str(payload.get("entity_id", "unknown"))
        run = recorder.start_run(
            component="HeartTwin",
            operation="twin_run",
            parameters={"entity_id": entity_id, "context": payload.get("context", {})},
            metadata={"hearttwin_payload_sha256": __import__("hashlib").sha256(raw.encode()).hexdigest()},
        )
        input_artifact = recorder.register_payload(payload, role="input", name=f"hearttwin:{entity_id}")
        recorder.attach_input(run.run_id, input_artifact)
        recorder.finish_run(
            run.run_id,
            status=TraceStatus.SUCCEEDED,
            metadata={"entity_id": entity_id},
        )
        finished = next(item for item in recorder.runs if item.run_id == run.run_id)
        print(json.dumps({
            "run_id": finished.run_id,
            "status": finished.status,
            "execution_fingerprint": finished.metadata.get("execution_fingerprint"),
            "input_artifact_id": input_artifact.artifact_id,
            "trace_root": str(root.resolve()),
        }, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - translate to adapter contract
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
