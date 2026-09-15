"""OpenLineage-compatible event export without requiring the OpenLineage SDK."""
from __future__ import annotations
from typing import Any

OPENLINEAGE_SCHEMA = "https://openlineage.io/spec/1-0-5/OpenLineage.json#/$defs/RunEvent"

def _dataset(ref, namespace: str):
    name = ref.uri or ref.artifact_id
    return {"namespace": namespace, "name": name, "facets": {"carditrace": {"_producer": "Virelion-CardiTrace", "_schemaURL": "carditrace://facets/artifact/v1", "artifactId": ref.artifact_id, "digest": ref.digest, "kind": str(ref.kind), "mediaType": ref.media_type}}}

def run_event(run, artifacts: dict[str, Any], *, event_type: str = "COMPLETE", namespace: str = "carditrace://local") -> dict[str, Any]:
    """Map a CardiTrace RunRecord to a portable OpenLineage-shaped RunEvent."""
    import datetime
    when = run.finished_at or run.started_at
    inputs = [_dataset(artifacts[x], namespace) for x in run.input_artifacts if x in artifacts]
    outputs = [_dataset(artifacts[x], namespace) for x in run.output_artifacts if x in artifacts]
    return {"eventType": event_type, "eventTime": datetime.datetime.fromtimestamp(when, datetime.timezone.utc).isoformat().replace("+00:00", "Z"), "producer": "carditrace", "schemaURL": OPENLINEAGE_SCHEMA, "run": {"runId": run.run_id, "facets": {"carditrace_execution": {"_producer": "carditrace", "_schemaURL": "carditrace://facets/execution/v1", "executionFingerprint": run.metadata.get("execution_fingerprint")}}}, "job": {"namespace": namespace, "name": f"{run.component}:{run.operation}", "facets": {"carditrace_parameters": {"_producer": "carditrace", "_schemaURL": "carditrace://facets/parameters/v1", "parameters": run.parameters}}}, "inputs": inputs, "outputs": outputs}

def events_from_recorder(recorder, *, namespace="carditrace://local"):
    artifacts = {a.artifact_id: a for a in recorder.artifacts}
    return [run_event(run, artifacts, event_type="COMPLETE" if str(run.status) == "succeeded" else "FAIL", namespace=namespace) for run in recorder.runs]

def export_openlineage(recorder, path, *, namespace="carditrace://local"):
    """Write newline-delimited OpenLineage-shaped events."""
    import json
    from pathlib import Path
    p = Path(path)
    p.write_text("".join(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n" for e in events_from_recorder(recorder, namespace=namespace)), encoding="utf-8")
    return p
