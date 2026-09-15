"""OpenLineage-shaped events with START/COMPLETE/FAIL lifecycle export."""
from __future__ import annotations
import datetime, json
from pathlib import Path
from typing import Any

OPENLINEAGE_SCHEMA = "https://openlineage.io/spec/2-0-2/OpenLineage.json"

def _dataset(ref, namespace: str, *, output: bool = False):
    facet = {"_producer": "carditrace", "_schemaURL": "https://virelion.org/carditrace/facets/artifact/v1", "artifactId": ref.artifact_id, "digest": ref.digest, "kind": str(ref.kind), "mediaType": ref.media_type}
    item = {"namespace": namespace, "name": ref.uri or ref.artifact_id, "facets": {"carditrace": facet}}
    item["outputFacets" if output else "inputFacets"] = {"carditrace_identity": facet}
    return item

def _event(run, artifacts, event_type: str, *, namespace: str):
    when = run.started_at if event_type == "START" else (run.finished_at or run.started_at)
    run_facets = {"carditrace_execution": {"_producer": "carditrace", "_schemaURL": "https://virelion.org/carditrace/facets/execution/v1", "executionFingerprint": run.metadata.get("execution_fingerprint")}}
    if run.parent_run_id:
        run_facets["parent"] = {"_producer": "carditrace", "_schemaURL": "https://openlineage.io/spec/facets/ParentRunFacet.json", "run": {"runId": run.parent_run_id, "facets": {}}}
    if event_type == "FAIL":
        run_facets["errorMessage"] = {"_producer": "carditrace", "_schemaURL": "https://openlineage.io/spec/facets/ErrorMessageRunFacet.json", "message": run.metadata.get("exception_message", "run failed"), "programmingLanguage": "python"}
    return {"eventType": event_type, "eventTime": datetime.datetime.fromtimestamp(when, datetime.timezone.utc).isoformat().replace("+00:00", "Z"), "producer": "carditrace", "schemaURL": OPENLINEAGE_SCHEMA, "run": {"runId": run.run_id, "facets": run_facets}, "job": {"namespace": namespace, "name": f"{run.component}:{run.operation}", "facets": {"carditrace_parameters": {"_producer": "carditrace", "_schemaURL": "https://virelion.org/carditrace/facets/parameters/v1", "parameters": run.parameters}}}, "inputs": [_dataset(artifacts[x], namespace) for x in run.input_artifacts if x in artifacts], "outputs": [_dataset(artifacts[x], namespace, output=True) for x in run.output_artifacts if x in artifacts]}

def run_event(run, artifacts: dict[str, Any], *, event_type: str = "COMPLETE", namespace: str = "carditrace://local") -> dict[str, Any]:
    if event_type not in {"START", "COMPLETE", "FAIL", "ABORT"}: raise ValueError("unsupported OpenLineage event type")
    return _event(run, artifacts, event_type, namespace=namespace)

def events_from_recorder(recorder, *, namespace="carditrace://local", lifecycle: str = "all"):
    if lifecycle not in {"all", "terminal", "start"}: raise ValueError("lifecycle must be 'all', 'terminal', or 'start'")
    artifacts = {a.artifact_id: a for a in recorder.artifacts}; events=[]
    for run in recorder.runs:
        if lifecycle in {"all", "start"}: events.append(run_event(run, artifacts, event_type="START", namespace=namespace))
        if lifecycle in {"all", "terminal"} and run.finished_at is not None:
            terminal = "COMPLETE" if str(run.status) == "succeeded" else ("ABORT" if str(run.status) == "cancelled" else "FAIL")
            events.append(run_event(run, artifacts, event_type=terminal, namespace=namespace))
    return events

def export_openlineage(recorder, path, *, namespace="carditrace://local", lifecycle="all"):
    target=Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(e, sort_keys=True, separators=(",", ":"))+"\n" for e in events_from_recorder(recorder, namespace=namespace, lifecycle=lifecycle)), encoding="utf-8")
    return target
