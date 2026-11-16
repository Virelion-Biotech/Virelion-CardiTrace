from dataclasses import replace
import pytest
from cardi_trace.therapeutic_provenance import TherapeuticClaimProvenance, DerivedArtifactProvenance, verify_claim_record
from cardi_trace.therapeutic_integration import trace_therapeutic_claim, trace_derived_therapeutic_artifact
from cardi_trace import TraceRecorder

def claim(**kw):
    base=dict(canonical_source_url="https://example.org/paper",source_identifier="DOI:10.1000/example",publication_date="2026-01-01",retrieval_timestamp="2026-11-16T10:00:00Z",source_type="peer_reviewed",source_version="version of record",source_sha256="a"*64,claim_text="The prespecified primary endpoint was not met.",claim_location="Results, paragraph 2, page 5",extraction_actor="curator:test",verification_status="source_checked",analysis_population="intention_to_treat",endpoint="primary endpoint",denominator={"n_randomized":100,"n_analyzed":96},follow_up="12 months",subgroup="none",subgroup_prespecified="not_applicable",multiplicity_status="hierarchical gatekeeping")
    base.update(kw); return TherapeuticClaimProvenance(**base)

def test_claim_roundtrip_and_stable_identity():
    a=claim(); b=TherapeuticClaimProvenance.from_dict(a.to_dict())
    assert a==b
    assert a.claim_id==b.claim_id
    assert verify_claim_record(a.to_dict())

def test_source_types_remain_distinct():
    company=claim(source_type="company_release")
    paper=claim(source_type="peer_reviewed")
    assert company.claim_id!=paper.claim_id
    assert company.to_dict()["source_type"]=="company_release"
    assert paper.to_dict()["source_type"]=="peer_reviewed"

def test_invalid_hash_or_missing_claim_locator_rejected():
    with pytest.raises(ValueError,match="source_sha256"):
        claim(source_sha256="not-a-hash")
    with pytest.raises(ValueError,match="claim_location"):
        claim(claim_location="")

def test_derived_artifact_requires_source_and_code_lineage():
    with pytest.raises(ValueError,match="source_record_ids"):
        DerivedArtifactProvenance("bench:v1","b"*64,(),{"CardiBench":"0.1"},{"schema":"1"},"c"*64,{})
    a=DerivedArtifactProvenance("bench:v1","b"*64,("claim:123",),{"CardiBench":"0.1"},{"schema":"1"},"c"*64,{"threshold":0.5},seed=7)
    assert DerivedArtifactProvenance.from_dict(a.to_dict())==a

def test_claim_and_derived_artifact_are_recorded_in_trace(tmp_path):
    recorder=TraceRecorder(tmp_path,actor="test")
    c=claim()
    ref=trace_therapeutic_claim(recorder,c)
    assert ref.metadata["role"]=="therapeutic_claim"
    derived=DerivedArtifactProvenance("benchmark:v1","b"*64,(c.claim_id,),{"CardiBench":"1.0"},{"schema":"1.0"},"c"*64,{"seed":7},seed=7)
    out=trace_derived_therapeutic_artifact(recorder,derived)
    assert out.metadata["role"]=="therapeutic_derived_artifact"
    assert any(e.event_type=="therapeutic.claim.recorded" for e in recorder.events)
    assert any(e.event_type=="therapeutic.artifact.derived" for e in recorder.events)
