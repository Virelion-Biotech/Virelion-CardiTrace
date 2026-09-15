"""Fine-grained column/feature lineage for tabular and omics workflows."""
from __future__ import annotations
from typing import Any, Mapping

def validate_mapping(mapping: Mapping[str, Any]) -> dict[str, list[str]]:
    normalized={}
    for target,sources in mapping.items():
        if isinstance(sources,str): sources=[sources]
        if not isinstance(sources,(list,tuple,set)) or not all(isinstance(x,str) and x for x in sources): raise ValueError(f"Invalid lineage sources for {target}")
        normalized[str(target)]=sorted(set(sources))
    return normalized

def add_column_lineage(recorder, source_artifact_id: str, target_artifact_id: str, mapping: Mapping[str, Any], *, run_id: str|None=None, metadata: dict[str,Any]|None=None):
    """Attach validated source→target column mappings to a normal artifact lineage edge."""
    normalized=validate_mapping(mapping)
    details={**(metadata or {}),"column_lineage":normalized,"column_lineage_schema":"carditrace.column-lineage.v1"}
    return recorder.add_lineage(source_artifact_id,target_artifact_id,relation="derived_from",run_id=run_id,metadata=details)

def reverse_column_lineage(mapping: Mapping[str, Any]) -> dict[str,list[str]]:
    out={}
    for target,sources in validate_mapping(mapping).items():
        for source in sources: out.setdefault(source,[]).append(target)
    return {k:sorted(set(v)) for k,v in out.items()}
