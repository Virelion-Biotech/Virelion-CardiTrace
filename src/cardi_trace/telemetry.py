"""OpenTelemetry-shaped export without an OpenTelemetry dependency."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TraceSpan:
    trace_id: str; span_id: str; parent_span_id: str | None; name: str; start_time_ns: int; end_time_ns: int | None; status: str; attributes: dict[str,Any]
    def to_dict(self): return {"trace_id":self.trace_id,"span_id":self.span_id,"parent_span_id":self.parent_span_id,"name":self.name,"start_time_unix_nano":self.start_time_ns,"end_time_unix_nano":self.end_time_ns,"status":self.status,"attributes":self.attributes}

def spans_from_recorder(recorder):
    spans=[]
    for run in recorder.runs:
        trace_id=run.metadata.get("trace_id",run.run_id.replace("-","")[:32].ljust(32,"0")); span_id=run.run_id.replace("-","")[:16].ljust(16,"0"); parent=run.metadata.get("span_parent_id")
        spans.append(TraceSpan(trace_id,span_id,parent,f"{run.component}.{run.operation}",int(run.started_at*1e9),None if run.finished_at is None else int(run.finished_at*1e9),str(run.status),{"service.name":run.component,"carditrace.run_id":run.run_id,"carditrace.execution_fingerprint":run.metadata.get("execution_fingerprint")}))
    return tuple(spans)

def export_otlp_json(recorder,path):
    import json
    from pathlib import Path
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps({"resourceSpans":[{"scopeSpans":[{"spans":[s.to_dict() for s in spans_from_recorder(recorder)]}]}]},sort_keys=True,indent=2),encoding="utf-8")
