"""Read-only query helpers over traces, runs, metrics, and lineage."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TraceQuery:
    recorder: Any
    def events(self,event_type=None,run_id=None,component=None):
        result=self.recorder.events
        if event_type is not None: result=tuple(e for e in result if e.event_type==event_type)
        if run_id is not None: result=tuple(e for e in result if e.run_id==run_id)
        if component is not None: result=tuple(e for e in result if e.component==component)
        return result
    def runs(self,component=None,status=None,operation=None,tag=None,tag_value=None,metric=None,metric_min=None,metric_max=None):
        result=self.recorder.runs
        if component is not None: result=tuple(r for r in result if r.component==component)
        if status is not None: result=tuple(r for r in result if str(r.status)==status)
        if operation is not None: result=tuple(r for r in result if r.operation==operation)
        if tag is not None: result=tuple(r for r in result if tag in r.tags and (tag_value is None or r.tags[tag]==str(tag_value)))
        if metric is not None: result=tuple(r for r in result if metric in r.metrics and (metric_min is None or r.metrics[metric]>=metric_min) and (metric_max is None or r.metrics[metric]<=metric_max))
        return result
    def artifact(self,artifact_id): return next((a for a in self.recorder.artifacts if a.artifact_id==artifact_id),None)
    def outputs_of(self,run_id):
        run=next(r for r in self.recorder.runs if r.run_id==run_id); return tuple(filter(None,(self.artifact(a) for a in run.output_artifacts)))
    def inputs_of(self,run_id):
        run=next(r for r in self.recorder.runs if r.run_id==run_id); return tuple(filter(None,(self.artifact(a) for a in run.input_artifacts)))
    def descendants(self,artifact_id):
        from .lineage import LineageGraph
        graph=LineageGraph(); [graph.add_edge(e.source_id,e.target_id,e.relation,e.run_id,e.metadata) for e in self.recorder.lineage]; return graph.descendants(artifact_id)
    def ancestors(self,artifact_id):
        from .lineage import LineageGraph
        graph=LineageGraph(); [graph.add_edge(e.source_id,e.target_id,e.relation,e.run_id,e.metadata) for e in self.recorder.lineage]; return graph.ancestors(artifact_id)
    def latest_run(self,*,component=None,operation=None): return max(self.runs(component=component,operation=operation),key=lambda r:r.started_at,default=None)
    def metric_history(self,name,*,component=None,operation=None): return tuple((r.started_at,r.run_id,r.metrics[name]) for r in self.runs(component=component,operation=operation) if name in r.metrics)
    def best_run(self,metric,*,maximize=True,component=None,operation=None):
        runs=self.runs(component=component,operation=operation,metric=metric); return (max if maximize else min)(runs,key=lambda r:r.metrics[metric],default=None)
    def execution_fingerprints(self): return {r.run_id:r.metadata["execution_fingerprint"] for r in self.recorder.runs if r.metadata.get("execution_fingerprint")}
