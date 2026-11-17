"""Recorder adapters for claim-level therapeutic evidence and derived artifacts."""
from __future__ import annotations
from typing import Any
from .therapeutic_provenance import TherapeuticClaimProvenance, DerivedArtifactProvenance

def trace_therapeutic_claim(recorder, claim: TherapeuticClaimProvenance, *, run_id: str | None=None):
    """Store the full immutable claim record and emit a trace event linking its content hash."""
    payload=claim.to_dict()
    ref=recorder.register_payload(payload,role="therapeutic_claim",metadata={"claim_id":claim.claim_id,"source_type":claim.source_type})
    recorder.record("therapeutic.claim.recorded",{"claim_id":claim.claim_id,"claim_record_sha256":payload["record_sha256"],"artifact_id":ref.artifact_id,"source_type":claim.source_type,"verification_status":claim.verification_status},run_id=run_id,component="CardiTrace")
    return ref

def trace_derived_therapeutic_artifact(recorder, artifact: DerivedArtifactProvenance, *, run_id: str | None=None):
    """Record source IDs and transformation identity for a derived benchmark/simulation artifact."""
    payload=artifact.to_dict()
    ref=recorder.register_payload(payload,role="therapeutic_derived_artifact",metadata={"artifact_id":artifact.artifact_id})
    recorder.record("therapeutic.artifact.derived",{"artifact_id":artifact.artifact_id,"artifact_sha256":artifact.artifact_sha256,"source_record_ids":list(artifact.source_record_ids),"component_versions":artifact.component_versions,"schema_versions":artifact.schema_versions,"transformation_code_sha256":artifact.transformation_code_sha256,"parameters":artifact.parameters,"seed":artifact.seed,"output_sha256":artifact.output_sha256,"provenance_artifact_id":ref.artifact_id},run_id=run_id,component="CardiTrace")
    return ref
