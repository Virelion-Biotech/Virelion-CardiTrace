"""Cross-repository trace federation with optional shared-secret authentication."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import uuid
from .hashing import sha256_payload
from .merkle import recorder_merkle_root
from .signing import sign_payload, verify_signature

@dataclass(frozen=True)
class TraceEnvelope:
    envelope_id: str; source: str; target: str; trace_id: str; created_at: str; merkle_root: str; artifact_ids: tuple[str,...]; metadata: dict[str,Any]; signature: str|None=None; signature_algorithm: str|None=None
    def to_dict(self, *, include_signature: bool = True):
        body={"envelope_id":self.envelope_id,"source":self.source,"target":self.target,"trace_id":self.trace_id,"created_at":self.created_at,"merkle_root":self.merkle_root,"artifact_ids":list(self.artifact_ids),"metadata":self.metadata}
        if include_signature:
            if self.signature_algorithm: body["signature_algorithm"]=self.signature_algorithm
            if self.signature: body["signature"]=self.signature
        return body
    @property
    def digest(self): return sha256_payload(self.to_dict())

def create_envelope(recorder, *, source, target, trace_id=None, metadata=None, secret: bytes|None=None):
    body={"envelope_id":str(uuid.uuid4()),"source":source,"target":target,"trace_id":trace_id or str(uuid.uuid4()),"created_at":datetime.now(timezone.utc).isoformat(),"merkle_root":recorder_merkle_root(recorder),"artifact_ids":sorted(a.artifact_id for a in recorder.artifacts),"metadata":metadata or {}}
    signature=sign_payload(body,secret) if secret else None
    return TraceEnvelope(**body,signature=signature,signature_algorithm="hmac-sha256" if secret else None)

def verify_envelope(envelope: TraceEnvelope, recorder, *, secret: bytes|None=None, require_signature: bool=False) -> tuple[str,...]:
    issues=[]
    if envelope.merkle_root != recorder_merkle_root(recorder): issues.append("merkle_root_mismatch")
    missing=sorted(set(envelope.artifact_ids)-{a.artifact_id for a in recorder.artifacts})
    if missing: issues.append("missing_artifacts:"+",".join(missing))
    if require_signature and not envelope.signature: issues.append("missing_signature")
    if envelope.signature:
        if envelope.signature_algorithm != "hmac-sha256": issues.append("unsupported_signature_algorithm")
        elif not secret or not verify_signature(envelope.to_dict(),envelope.signature,secret): issues.append("invalid_signature")
    return tuple(issues)
