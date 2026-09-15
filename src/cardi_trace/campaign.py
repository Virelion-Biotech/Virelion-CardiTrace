"""Reproducible multi-run campaign summaries for experiments and pipelines."""
from __future__ import annotations
from typing import Any

def summarize_campaign(recorder, *, run_ids=None, metric=None):
    runs = [r for r in recorder.runs if run_ids is None or r.run_id in set(run_ids)]
    status_counts = {}
    for run in runs: status_counts[str(run.status)] = status_counts.get(str(run.status), 0) + 1
    durations = [r.finished_at-r.started_at for r in runs if r.finished_at is not None]
    report = {"schema_version":"1.0","run_ids":[r.run_id for r in runs],"run_count":len(runs),"status_counts":status_counts,"duration_seconds":{"count":len(durations),"total":sum(durations),"mean":sum(durations)/len(durations) if durations else None,"max":max(durations) if durations else None}}
    if metric:
        values=[(r.run_id,r.metrics[metric]) for r in runs if metric in r.metrics]
        report["metric"]={"name":metric,"count":len(values),"best":(max(values,key=lambda x:x[1]) if values else None),"worst":(min(values,key=lambda x:x[1]) if values else None)}
    report["execution_fingerprints"]={r.run_id:r.metadata.get("execution_fingerprint") for r in runs if r.metadata.get("execution_fingerprint")}
    return report

def compare_runs(recorder, run_a: str, run_b: str) -> dict[str, Any]:
    lookup={r.run_id:r for r in recorder.runs}
    a,b=lookup.get(run_a),lookup.get(run_b)
    if not a or not b: raise KeyError("Both run IDs must exist")
    metrics=sorted(set(a.metrics)|set(b.metrics))
    return {"run_a":run_a,"run_b":run_b,"same_code":a.code_identity==b.code_identity,"same_parameters":a.parameters==b.parameters,"same_inputs":a.input_artifacts==b.input_artifacts,"metric_delta":{name:(b.metrics[name]-a.metrics[name]) if name in a.metrics and name in b.metrics else None for name in metrics},"status_delta":[str(a.status),str(b.status)]}
