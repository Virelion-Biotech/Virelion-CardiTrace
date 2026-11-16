"""Claim-level provenance contracts for therapeutic evidence and derived artifacts.

Hashes and lineage establish identity/integrity only; they do not verify scientific truth.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib, json, re
from typing import Any

SOURCE_TYPES={"peer_reviewed","clinical_registry","regulator","company_release","conference_abstract","preprint","guideline","other"}
VERIFICATION={"unverified","source_checked","independently_verified","superseded","contradicted"}
POPULATIONS={"intention_to_treat","modified_intention_to_treat","per_protocol","safety","exploratory","not_reported","not_applicable"}

def _canonical(value: Any) -> str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)

def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()

def _required_text(value: Any, name: str) -> None:
    if not isinstance(value,str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")

def _hash(value: Any, name: str, *, optional=False) -> None:
    if optional and value is None: return
    if not isinstance(value,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",value):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")

@dataclass(frozen=True)
class TherapeuticClaimProvenance:
    canonical_source_url: str
    source_identifier: str
    publication_date: str | None
    retrieval_timestamp: str
    source_type: str
    source_version: str
    source_sha256: str
    claim_text: str
    claim_location: str
    extraction_actor: str
    verification_status: str
    analysis_population: str = "not_reported"
    endpoint: str = "not_reported"
    denominator: dict[str, Any] = field(default_factory=dict)
    follow_up: str = "not_reported"
    subgroup: str = "not_reported"
    subgroup_prespecified: str = "not_reported"
    multiplicity_status: str = "not_reported"
    supersedes: tuple[str,...] = ()
    contradicts: tuple[str,...] = ()
    metadata: dict[str,Any] = field(default_factory=dict)
    claim_id: str = ""

    def __post_init__(self):
        for name in ("canonical_source_url","source_identifier","retrieval_timestamp","source_version","claim_text","claim_location","extraction_actor"):
            _required_text(getattr(self,name),name)
        if self.source_type not in SOURCE_TYPES: raise ValueError(f"unsupported source_type: {self.source_type}")
        if self.verification_status not in VERIFICATION: raise ValueError(f"unsupported verification_status: {self.verification_status}")
        if self.analysis_population not in POPULATIONS: raise ValueError(f"unsupported analysis_population: {self.analysis_population}")
        _hash(self.source_sha256,"source_sha256")
        identity={k:v for k,v in asdict(self).items() if k not in {"claim_id","metadata","supersedes","contradicts"}}
        if not self.claim_id: object.__setattr__(self,"claim_id",f"claim:{_digest(identity)[:32]}")
        if not self.claim_id.startswith("claim:"): raise ValueError("claim_id must use claim: prefix")

    def to_dict(self) -> dict[str,Any]:
        value=asdict(self)
        value["supersedes"]=list(self.supersedes); value["contradicts"]=list(self.contradicts)
        value["record_sha256"]=_digest(value)
        return value

    @classmethod
    def from_dict(cls,value:dict[str,Any])->"TherapeuticClaimProvenance":
        data=dict(value); data.pop("record_sha256",None)
        data["supersedes"]=tuple(data.get("supersedes",()))
        data["contradicts"]=tuple(data.get("contradicts",()))
        return cls(**data)

@dataclass(frozen=True)
class DerivedArtifactProvenance:
    artifact_id: str
    artifact_sha256: str
    source_record_ids: tuple[str,...]
    component_versions: dict[str,str]
    schema_versions: dict[str,str]
    transformation_code_sha256: str
    parameters: dict[str,Any]
    seed: int | None = None
    output_sha256: str | None = None
    metadata: dict[str,Any] = field(default_factory=dict)

    def __post_init__(self):
        _required_text(self.artifact_id,"artifact_id")
        if not self.source_record_ids: raise ValueError("source_record_ids must not be empty")
        _hash(self.artifact_sha256,"artifact_sha256")
        _hash(self.transformation_code_sha256,"transformation_code_sha256")
        _hash(self.output_sha256,"output_sha256",optional=True)
        if not self.component_versions or not self.schema_versions: raise ValueError("component_versions and schema_versions are required")

    def to_dict(self)->dict[str,Any]: return asdict(self)

    @classmethod
    def from_dict(cls,value:dict[str,Any])->"DerivedArtifactProvenance":
        data=dict(value); data["source_record_ids"]=tuple(data["source_record_ids"]); return cls(**data)

def verify_claim_record(value: dict[str,Any]) -> bool:
    expected=value.get("record_sha256")
    body={k:v for k,v in value.items() if k!="record_sha256"}
    return isinstance(expected,str) and expected==_digest(body)
