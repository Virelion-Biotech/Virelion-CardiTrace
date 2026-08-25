"""Loose adapters for tracing Virelion pipeline envelopes."""
from __future__ import annotations
from typing import Any


def trace_component_event(recorder, component: str, operation: str, *, payload: dict[str, Any], run_id: str | None = None):
    """Record an upstream/downstream event without coupling CardiTrace to its schema."""
    return recorder.record(f"component.{operation}", payload, run_id=run_id, component=component)


def trace_handoff(recorder, *, source: str, target: str, payload: dict[str, Any], run_id: str | None = None):
    """Register a cross-repository handoff as a content-addressed payload."""
    ref = recorder.register_payload(payload, role="handoff", metadata={"source": source, "target": target})
    recorder.record("handoff.created", {"source": source, "target": target, "artifact_id": ref.artifact_id}, run_id=run_id, component="CardiTrace")
    return ref


def trace_model_use(recorder, *, model_id: str, model_digest: str, inputs: list[str], outputs: list[str], run_id: str | None = None):
    return recorder.record("model.used", {"model_id": model_id, "model_digest": model_digest, "inputs": inputs, "outputs": outputs}, run_id=run_id, component="CardiTrace")
