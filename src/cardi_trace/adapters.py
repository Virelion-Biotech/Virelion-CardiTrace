"""Dependency-free adapters for importing external lineage/run events."""
from __future__ import annotations
from typing import Any, Mapping
from .models import ArtifactKind

class AdapterError(ValueError): pass

def ingest_mapping(recorder, payload: Mapping[str, Any], *, source: str, component: str | None = None):
    """Import a generic run mapping while preserving external IDs in tags/metadata."""
    run_payload = payload.get("run", payload)
    external_id = str(run_payload.get("runId") or run_payload.get("run_id") or "")
    if not external_id: raise AdapterError("external run identifier is required")
    params = run_payload.get("parameters", run_payload.get("params", {})) or {}
    tags = {"external_source": source, "external_run_id": external_id}
    tags.update({str(k): str(v) for k, v in (run_payload.get("tags", {}) or {}).items()})
    run = recorder.start_run(component or str(payload.get("component") or payload.get("job", {}).get("name") or source), str(payload.get("operation") or payload.get("job", {}).get("name") or "imported"), parameters=params, metadata={"adapter_source": source, "external_run_id": external_id}, tags=tags)
    for metric_name, value in (run_payload.get("metrics", {}) or {}).items(): recorder.log_metric(run.run_id, metric_name, value)
    return run

def ingest_openlineage_event(recorder, event: Mapping[str, Any], *, source: str = "openlineage"):
    """Import an OpenLineage-shaped event into the CardiTrace ledger."""
    event_type = str(event.get("eventType", ""))
    run = event.get("run", {}) or {}; job = event.get("job", {}) or {}
    run_id = str(run.get("runId") or "")
    if not run_id: raise AdapterError("OpenLineage event missing run.runId")
    component = str(job.get("namespace") or source); operation = str(job.get("name") or "openlineage")
    if event_type == "START":
        return ingest_mapping(recorder, {"run": {"runId": run_id, "parameters": (job.get("facets", {}).get("carditrace_parameters", {}) or {}).get("parameters", {})}, "component": component, "operation": operation}, source=source, component=component)
    existing = next((candidate for candidate in recorder.runs if candidate.tags.get("external_run_id") == run_id and candidate.tags.get("external_source") == source), None)
    if existing is None: existing = ingest_mapping(recorder, {"run": {"runId": run_id}, "component": component, "operation": operation}, source=source, component=component)
    terminal = {"COMPLETE": "succeeded", "FAIL": "failed", "ABORT": "cancelled"}.get(event_type)
    if terminal:
        return recorder.finish_run(existing.run_id, status=terminal, metadata={"external_event_type": event_type, "external_source": source})
    return existing

def ingest_artifact_manifest(recorder, manifest: Mapping[str, Any], *, source: str):
    """Import a dataset-manifest-like mapping as an auditable payload artifact."""
    ref = recorder.register_payload(dict(manifest), role="dataset_manifest", kind=ArtifactKind.DATASET, name=str(manifest.get("dataset_id") or source), metadata={"source": source, "external_manifest_digest": manifest.get("manifest_digest")})
    return ref

class AdapterRegistry:
    def __init__(self): self._adapters: dict[str, Any] = {}
    def register(self, name: str, adapter: Any):
        if not name or not callable(adapter): raise TypeError("adapter name and callable are required")
        if name in self._adapters: raise AdapterError(f"adapter already registered: {name}")
        self._adapters[name] = adapter
    def get(self, name: str):
        try: return self._adapters[name]
        except KeyError as exc: raise AdapterError(f"unknown adapter: {name}") from exc
    def names(self): return tuple(sorted(self._adapters))
