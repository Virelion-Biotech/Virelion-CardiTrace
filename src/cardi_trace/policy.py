"""Policy gates for trustworthy trace capture."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable

@dataclass(frozen=True)
class PolicyViolation:
    code: str; message: str; severity: str = "error"; subject: str | None = None
    def to_dict(self): return {"code":self.code,"message":self.message,"severity":self.severity,"subject":self.subject}

@dataclass(frozen=True)
class TracePolicy:
    require_code_identity: bool = True
    require_environment: bool = True
    require_inputs_for_non_source_runs: bool = False
    require_outputs_for_success: bool = False
    allowed_components: frozenset[str] | None = None
    required_run_metadata: tuple[str, ...] = ()
    blocked_metadata_keys: frozenset[str] = frozenset()
    def evaluate(self, recorder):
        out=[]
        for run in recorder.runs:
            if self.require_code_identity and not run.code_identity: out.append(PolicyViolation("run.code_identity","Run has no code identity",subject=run.run_id))
            if self.require_environment and not run.environment: out.append(PolicyViolation("run.environment","Run has no environment fingerprint",subject=run.run_id))
            if self.require_inputs_for_non_source_runs and not run.input_artifacts and run.operation not in {"ingest","source","generate"}: out.append(PolicyViolation("run.inputs","Non-source run has no input artifacts",subject=run.run_id))
            if self.require_outputs_for_success and str(run.status)=="succeeded" and not run.output_artifacts: out.append(PolicyViolation("run.outputs","Successful run has no output artifacts",subject=run.run_id))
            if self.allowed_components is not None and run.component not in self.allowed_components: out.append(PolicyViolation("run.component",f"Component {run.component!r} is not allowed",subject=run.run_id))
            for key in self.required_run_metadata:
                if key not in run.metadata: out.append(PolicyViolation("run.metadata",f"Required metadata key {key!r} is missing",subject=run.run_id))
            for key in self.blocked_metadata_keys:
                if key in run.metadata: out.append(PolicyViolation("run.metadata.blocked",f"Blocked metadata key {key!r} is present",subject=run.run_id))
        return tuple(out)
    def assert_compliant(self, recorder):
        errors=tuple(v for v in self.evaluate(recorder) if v.severity=="error")
        if errors: raise TracePolicyError(errors)

class TracePolicyError(RuntimeError):
    def __init__(self, violations: Iterable[PolicyViolation]):
        self.violations=tuple(violations); super().__init__("Trace policy failed: "+"; ".join(v.code for v in self.violations))
