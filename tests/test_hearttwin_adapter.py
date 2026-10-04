from __future__ import annotations

import hashlib
import json

import pytest

from cardi_trace.hearttwin_adapter import _verify_canonical_state


def _fingerprint(state: dict) -> str:
    payload = dict(state)
    payload.pop("state_fingerprint", None)
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _payload() -> dict:
    state = {
        "contract_version": "1.3.0",
        "entity_id": "TRACE-001",
        "biological_context": {"source": "test"},
        "state_phase": "evaluated",
        "observations": [],
        "atlas_context": None,
        "anatomy_bundles": [],
        "benchmarks": [],
        "modality_analyses": [],
        "derived_values": [],
        "simulation_artifacts": [],
        "prediction_artifacts": [],
        "ep_artifacts": [],
        "mechanics_artifacts": [],
        "flow_artifacts": [],
        "therapy_artifacts": [],
        "posterior_artifacts": [],
        "evaluation_artifacts": [],
        "validation_gates": [],
        "challenges": [],
        "vex_observations": [],
        "bridge_publications": [],
        "transitions": [],
        "trace_records": [],
        "provenance": [],
        "inferred_state": {},
        "simulations": [],
        "predictions": [],
        "validation": {},
    }
    fingerprint = _fingerprint(state)
    state["state_fingerprint"] = fingerprint
    return {
        "entity_id": "TRACE-001",
        "workflow_state": {"entity_id": "TRACE-001", "cardiac_state": state},
        "canonical_state_fingerprint": fingerprint,
    }


def test_verifies_canonical_state_fingerprint_independently() -> None:
    payload = _payload()
    assert _verify_canonical_state(payload) == payload["canonical_state_fingerprint"]


def test_rejects_tampered_canonical_state() -> None:
    payload = _payload()
    payload["workflow_state"]["cardiac_state"]["biological_context"]["tampered"] = True
    with pytest.raises(ValueError, match="canonical fingerprint mismatch"):
        _verify_canonical_state(payload)


def test_legacy_trace_without_canonical_state_remains_supported() -> None:
    assert _verify_canonical_state({"entity_id": "legacy"}) is None
