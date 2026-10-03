"""Trace comparison and regression detection."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .hashing import sha256_payload

@dataclass(frozen=True)
class TraceDiff:
    identical: bool; left_digest: str; right_digest: str
    added_runs: tuple[str,...]=(); removed_runs: tuple[str,...]=(); changed_runs: tuple[str,...]=()
    added_artifacts: tuple[str,...]=(); removed_artifacts: tuple[str,...]=(); changed_events: int=0
    def to_dict(self):
        return {"identical":self.identical,"left_digest":self.left_digest,"right_digest":self.right_digest,"added_runs":list(self.added_runs),"removed_runs":list(self.removed_runs),"changed_runs":list(self.changed_runs),"added_artifacts":list(self.added_artifacts),"removed_artifacts":list(self.removed_artifacts),"changed_events":self.changed_events}

def trace_digest(recorder):
    return sha256_payload({"events":[e.to_dict() for e in recorder.events],"runs":[r.to_dict() for r in sorted(recorder.runs,key=lambda x:x.run_id)],"artifacts":[a.to_dict() for a in sorted(recorder.artifacts,key=lambda x:x.artifact_id)],"lineage":[e.to_dict() for e in getattr(recorder,"lineage",())]})

def compare_traces(left,right):
    l_runs={r.run_id:r.to_dict() for r in left.runs}; r_runs={r.run_id:r.to_dict() for r in right.runs}; l_art={a.artifact_id:a.to_dict() for a in left.artifacts}; r_art={a.artifact_id:a.to_dict() for a in right.artifacts}
    added=tuple(sorted(set(r_runs)-set(l_runs))); removed=tuple(sorted(set(l_runs)-set(r_runs))); changed=tuple(sorted(k for k in set(l_runs)&set(r_runs) if l_runs[k]!=r_runs[k])); added_a=tuple(sorted(set(r_art)-set(l_art))); removed_a=tuple(sorted(set(l_art)-set(r_art)))
    le=[e.to_dict() for e in left.events]; re=[e.to_dict() for e in right.events]; changed_events=sum((le[i] if i<len(le) else None)!=(re[i] if i<len(re) else None) for i in range(max(len(le),len(re))))
    ld,rd=trace_digest(left),trace_digest(right)
    return TraceDiff(not any((added,removed,changed,added_a,removed_a,changed_events)),ld,rd,added,removed,changed,added_a,removed_a,changed_events)
