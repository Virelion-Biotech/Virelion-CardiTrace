"""Dependency-free adapters for importing external lineage/run events."""

from __future__ import annotations
from typing import Any, Mapping
from .models import ArtifactKind


class AdapterError(ValueError):
    pass


def ingest_mapping(
    recorder, payload: Mapping[str, Any], *, source: str, component: str | None = None
):
    """Import a generic run mapping while preserving external IDs in tags/metadata."""
    run_payload = payload.get("run", payload)
    external_id = str(run_payload.get("runId") or run_payload.get("run_id") or "")
    if not external_id:
        raise AdapterError("external run identifier is required")
    params = run_payload.get("parameters", run_payload.get("params", {})) or {}
    tags = {str(k): str(v) for k, v in (run_payload.get("tags", {}) or {}).items()}
    tags.update({"external_source": source, "external_run_id": external_id})
    run = recorder.start_run(
        component
        or str(
            payload.get("component") or payload.get("job", {}).get("name") or source
        ),
        str(
            payload.get("operation") or payload.get("job", {}).get("name") or "imported"
        ),
        parameters=params,
        metadata={"adapter_source": source, "external_run_id": external_id},
        tags=tags,
    )
    for metric_name, value in (run_payload.get("metrics", {}) or {}).items():
        recorder.log_metric(run.run_id, metric_name, value)
    return run


def ingest_openlineage_event(
    recorder, event: Mapping[str, Any], *, source: str = "openlineage"
):
    """Import lifecycle, metrics and dataset descriptors; source bytes remain external.

    Dataset descriptors receive their own payload identity, never a fabricated
    assertion that CardiTrace has measured the upstream dataset bytes.
    """
    import math
    from .hashing import sha256_payload

    event_type = str(event.get("eventType", ""))
    if event_type not in {"START", "RUNNING", "COMPLETE", "FAIL", "ABORT", "OTHER"}:
        raise AdapterError("Unsupported OpenLineage event type")
    run = event.get("run", {}) or {}
    job = event.get("job", {}) or {}
    run_id = str(run.get("runId") or "")
    if not run_id:
        raise AdapterError("OpenLineage event missing run.runId")
    component = str(job.get("namespace") or source)
    operation = str(job.get("name") or "openlineage")
    execution = run.get("facets", {}).get("carditrace_execution", {}) or {}
    metrics = execution.get("metrics", {}) or {}
    tags = execution.get("tags", {}) or {}
    if not isinstance(metrics, dict) or not isinstance(tags, dict):
        raise AdapterError("Invalid run facets")
    try:
        metrics = {str(k): float(v) for k, v in metrics.items()}
        if any(not math.isfinite(v) for v in metrics.values()):
            raise ValueError("non-finite metric")
    except (ValueError, TypeError) as exc:
        raise AdapterError("Invalid metric values") from exc
    datasets = []
    for role in ("inputs", "outputs"):
        records = event.get(role, []) or []
        if not isinstance(records, list) or any(
            not isinstance(item, dict) for item in records
        ):
            raise AdapterError("Invalid dataset descriptors")
        datasets.extend((role, item) for item in records)
    existing = next(
        (
            candidate
            for candidate in recorder.runs
            if candidate.tags.get("external_run_id") == run_id
            and candidate.tags.get("external_source") == source
        ),
        None,
    )
    if existing and (
        existing.component != component or existing.operation != operation
    ):
        raise AdapterError("External run identity conflicts with a different job")
    terminal = {"COMPLETE": "succeeded", "FAIL": "failed", "ABORT": "cancelled"}.get(
        event_type
    )
    if existing and existing.finished_at is not None:
        if terminal == str(existing.status) or event_type == "START":
            return existing
        raise AdapterError("Conflicting event after terminal run")
    if existing is None:
        parameters = (job.get("facets", {}).get("carditrace_parameters", {}) or {}).get(
            "parameters", {}
        )
        existing = ingest_mapping(
            recorder,
            {
                "run": {"runId": run_id, "parameters": parameters},
                "component": component,
                "operation": operation,
            },
            source=source,
            component=component,
        )
    for name, value in metrics.items():
        if existing.metrics.get(name) != value:
            recorder.log_metric(existing.run_id, name, value)
    for name, value in tags.items():
        if name not in {"external_source", "external_run_id"} and existing.tags.get(
            name
        ) != str(value):
            recorder.set_tag(existing.run_id, name, value)
    for role, descriptor in datasets:
        digest = sha256_payload(descriptor)
        ref = next((a for a in recorder.artifacts if a.digest == digest), None)
        if ref is None:
            ref = recorder.register_payload(
                descriptor,
                kind=ArtifactKind.DATASET,
                role="external_dataset_descriptor",
                name=str(descriptor.get("name") or "dataset"),
                metadata={"adapter_source": source, "content_verified": False},
            )
        current = next(r for r in recorder.runs if r.run_id == existing.run_id)
        attached = (
            current.input_artifacts if role == "inputs" else current.output_artifacts
        )
        if ref.artifact_id not in attached:
            (recorder.attach_input if role == "inputs" else recorder.attach_output)(
                existing.run_id, ref
            )
    if terminal:
        return recorder.finish_run(
            existing.run_id,
            status=terminal,
            metadata={
                "external_event_type": event_type,
                "external_source": source,
                "external_event_time": event.get("eventTime"),
            },
        )
    return next(r for r in recorder.runs if r.run_id == existing.run_id)


def ingest_artifact_manifest(recorder, manifest: Mapping[str, Any], *, source: str):
    """Import a dataset-manifest-like mapping as an auditable payload artifact."""
    ref = recorder.register_payload(
        dict(manifest),
        role="dataset_manifest",
        kind=ArtifactKind.DATASET,
        name=str(manifest.get("dataset_id") or source),
        metadata={
            "source": source,
            "external_manifest_digest": manifest.get("manifest_digest"),
        },
    )
    return ref


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, Any] = {}

    def register(self, name: str, adapter: Any):
        if not name or not callable(adapter):
            raise TypeError("adapter name and callable are required")
        if name in self._adapters:
            raise AdapterError(f"adapter already registered: {name}")
        self._adapters[name] = adapter

    def get(self, name: str):
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise AdapterError(f"unknown adapter: {name}") from exc

    def names(self):
        return tuple(sorted(self._adapters))
