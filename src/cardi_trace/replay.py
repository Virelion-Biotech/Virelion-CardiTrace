"""Reproducibility planning and replay validation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ReplayPlan:
    run_id: str; component: str; operation: str; code_identity: str | None; environment: dict[str,Any]; parameters: dict[str,Any]; input_artifacts: tuple[str,...]; output_artifacts: tuple[str,...]; fingerprint: str | None
    def to_dict(self): return {"run_id":self.run_id,"component":self.component,"operation":self.operation,"code_identity":self.code_identity,"environment":self.environment,"parameters":self.parameters,"input_artifacts":list(self.input_artifacts),"output_artifacts":list(self.output_artifacts),"fingerprint":self.fingerprint}

def plan_replay(recorder, run_id: str):
    run=next((r for r in recorder.runs if r.run_id==run_id),None)
    if run is None: raise KeyError(f"Unknown run: {run_id}")
    return ReplayPlan(run.run_id,run.component,run.operation,run.code_identity,run.environment,run.parameters,run.input_artifacts,run.output_artifacts,run.metadata.get("execution_fingerprint"))

def validate_replay(original,candidate):
    mismatches=[]
    if original.component!=candidate.component: mismatches.append("component")
    if original.operation!=candidate.operation: mismatches.append("operation")
    if tuple(original.input_artifacts)!=tuple(candidate.input_artifacts): mismatches.append("inputs")
    if original.parameters!=candidate.parameters: mismatches.append("parameters")
    if original.code_identity!=candidate.code_identity: mismatches.append("code_identity")
    expected=original.metadata.get("execution_fingerprint"); actual=candidate.metadata.get("execution_fingerprint")
    if expected and actual and expected!=actual: mismatches.append("execution_fingerprint")
    elif not expected or not actual: mismatches.append("missing_execution_fingerprint")
    return tuple(mismatches)
