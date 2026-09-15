"""Recover derived trace state from the append-only event journal."""
from __future__ import annotations
import json
from dataclasses import replace
from pathlib import Path
from .models import ArtifactRef, LineageEdge, RunRecord, TraceEvent
from .recorder import TraceRecorder

def recover_from_events(root: str | Path, *, overwrite: bool = False) -> TraceRecorder:
    root = Path(root); events_path = root / "events.jsonl"
    if not events_path.exists(): raise FileNotFoundError(events_path)
    events=[]
    for lineno,line in enumerate(events_path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        try: events.append(TraceEvent(**json.loads(line)))
        except Exception as exc: raise ValueError(f"Invalid event at line {lineno}: {exc}") from exc
    runs={}; artifacts={}; edges={}
    for event in events:
        payload=event.payload or {}
        if event.event_type in {"run.started","run.finished"} and payload.get("run"):
            run=RunRecord(**payload["run"]); runs[run.run_id]=run
        elif event.event_type=="artifact.registered" and payload.get("artifact"):
            artifact=ArtifactRef(**payload["artifact"]); artifacts[artifact.artifact_id]=artifact
        elif event.event_type=="run.input.attached" and event.run_id and event.run_id in runs:
            run=runs[event.run_id]; aid=payload.get("artifact_id")
            if aid: runs[event.run_id]=replace(run,input_artifacts=tuple(dict.fromkeys((*run.input_artifacts,aid))))
        elif event.event_type=="run.output.attached" and event.run_id and event.run_id in runs:
            run=runs[event.run_id]; aid=payload.get("artifact_id")
            if aid: runs[event.run_id]=replace(run,output_artifacts=tuple(dict.fromkeys((*run.output_artifacts,aid))))
        elif event.event_type=="run.metric" and event.run_id and event.run_id in runs:
            run=runs[event.run_id]; name=payload.get("name"); value=payload.get("value")
            if name is not None and value is not None: runs[event.run_id]=replace(run,metrics={**run.metrics,str(name):float(value)})
        elif event.event_type=="run.tag" and event.run_id and event.run_id in runs:
            run=runs[event.run_id]; name=payload.get("name"); value=payload.get("value")
            if name is not None: runs[event.run_id]=replace(run,tags={**run.tags,str(name):str(value)})
        elif event.event_type=="lineage.edge" and payload.get("edge"):
            edge=LineageEdge(**payload["edge"]); edges[(edge.source_id,edge.target_id,edge.relation)]=edge
    if overwrite:
        for path in (root/"runs.json",root/"artifacts.json",root/"lineage.json"):
            if path.exists(): path.unlink()
    recorder=TraceRecorder(root)
    if set(recorder.runs) != set(runs.values()) or set(recorder.artifacts) != set(artifacts.values()) or set(recorder.lineage) != set(edges.values()):
        recorder._runs=runs; recorder._artifacts=artifacts; recorder._edges=list(edges.values()); recorder._events=events; recorder._persist()
    return recorder
