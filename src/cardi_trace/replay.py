"""Reproducibility planning and replay validation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .fingerprint import execution_fingerprint

@dataclass(frozen=True)
class ReplayPlan:
    run_id: str; component: str; operation: str; code_identity: str | None; environment: dict[str,Any]; parameters: dict[str,Any]; input_artifacts: tuple[str,...]; output_artifacts: tuple[str,...]; fingerprint: str | None
    def to_dict(self): return {"run_id":self.run_id,"component":self.component,"operation":self.operation,"code_identity":self.code_identity,"environment":self.environment,"parameters":self.parameters,"input_artifacts":list(self.input_artifacts),"output_artifacts":list(self.output_artifacts),"fingerprint":self.fingerprint}

def plan_replay(recorder, run_id: str):
    run=next((r for r in recorder.runs if r.run_id==run_id),None)
    if run is None: raise KeyError(f"Unknown run: {run_id}")
    return ReplayPlan(run.run_id,run.component,run.operation,run.code_identity,run.environment,run.parameters,run.input_artifacts,run.output_artifacts,run.metadata.get("execution_fingerprint"))

def validate_replay(original,candidate):
    """Compare a replay candidate against a run, tolerating a stale pre-attachment snapshot of the same run."""
    mismatches=[]
    same_run = getattr(original, "run_id", None) == getattr(candidate, "run_id", None)
    if original.component!=candidate.component: mismatches.append("component")
    if original.operation!=candidate.operation: mismatches.append("operation")
    comparison_inputs = candidate.input_artifacts if same_run else original.input_artifacts
    if not same_run and tuple(original.input_artifacts)!=tuple(candidate.input_artifacts): mismatches.append("inputs")
    if original.parameters!=candidate.parameters: mismatches.append("parameters")
    if original.code_identity!=candidate.code_identity: mismatches.append("code_identity")
    baseline = candidate if same_run else original
    detail=baseline.metadata.get("execution_fingerprint_detail",{})
    expected=execution_fingerprint(code_identity=baseline.code_identity, environment_identity=detail.get("environment_identity"), input_artifacts=comparison_inputs, parameters=baseline.parameters, seeds=baseline.metadata.get("seeds",{})).digest
    actual=candidate.metadata.get("execution_fingerprint")
    if not actual: mismatches.append("missing_execution_fingerprint")
    elif expected!=actual: mismatches.append("execution_fingerprint")
    return tuple(dict.fromkeys(mismatches))
