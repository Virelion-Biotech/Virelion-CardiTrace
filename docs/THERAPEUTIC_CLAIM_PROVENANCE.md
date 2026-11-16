# Therapeutic claim provenance

CardiTrace now has a typed claim-level provenance contract for therapeutic intelligence. Each claim preserves canonical source URL/identifier, publication date, retrieval timestamp, source type/version/hash, exact claim text and source location, extraction actor, verification status, and clinical interpretation context (analysis population, endpoint, denominator, follow-up, subgroup/prespecification and multiplicity). Supersession and contradiction links are explicit.

Supported source classes remain distinct: peer-reviewed paper, clinical registry, regulator, company release, conference abstract, preprint, guideline and other. Verification states describe provenance review, not scientific truth. A source-checked company release remains company-reported evidence; it does not become independently verified efficacy.

## Capture

```python
from cardi_trace import TraceRecorder
from cardi_trace.therapeutic_provenance import TherapeuticClaimProvenance
from cardi_trace.therapeutic_integration import trace_therapeutic_claim

trace = TraceRecorder("./trace", component="CardiAtlas")
claim = TherapeuticClaimProvenance(
    canonical_source_url="https://example.org/source",
    source_identifier="DOI:10.xxxx/example",
    publication_date="2026-01-01",
    retrieval_timestamp="2026-11-16T10:00:00Z",
    source_type="peer_reviewed",
    source_version="version of record",
    source_sha256="<sha256 of archived source artifact>",
    claim_text="Exact claim extracted from source",
    claim_location="Results, page 5, paragraph 2",
    extraction_actor="curator:identifier",
    verification_status="source_checked",
    analysis_population="intention_to_treat",
    endpoint="prespecified primary endpoint",
    denominator={"randomized": 100, "analyzed": 96},
    follow_up="12 months",
    subgroup="none",
    subgroup_prespecified="not_applicable",
    multiplicity_status="hierarchical gatekeeping",
)
trace_therapeutic_claim(trace, claim)
```

For company reports or conference abstracts, set `source_type` accordingly. Do not infer missing denominators or follow-up; encode the value as `not_reported` in the relevant field and explain in metadata. The source hash must identify the archived artifact whose version is recorded, not merely the URL.

## Derived artifacts

`DerivedArtifactProvenance` requires source record IDs, component/schema versions, transformation-code SHA-256, parameters and optional seed/output hash. Recorder adapters store the complete provenance payload as a content-addressed artifact and emit append-only events linking the claim/artifact IDs. Use this for CardiAtlas → CardiBench → CardiEval → HeartTwin derived outputs.

## Integrity boundary

A SHA-256 digest detects byte changes relative to a trusted digest. It does not authenticate the publisher, prove the source is true, establish correct extraction, or establish scientific validity. Independent verification, signed source archives, key custody and retention remain separate governance controls.
