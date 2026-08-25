"""Append-only, content-addressed provenance recorder."""
from __future__ import annotations
import json, platform, sys, socket, time
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable
from .fingerprint import execution_fingerprint
from .hashing import digest_event, sha256_file, sha256_payload
from .lineage import LineageGraph
from .models import ArtifactKind, ArtifactRef, LineageEdge, RunRecord, TraceEvent, TraceStatus
from .redaction import DEFAULT_SENSITIVE_KEYS, redact

class TraceRecorder:
    """Durable provenance ledger with execution identity and lineage support."""
    def __init__(self, root: str | Path, actor: str = "unknown", component: str = "CardiTrace", *, redact_metadata: bool = True, sensitive_keys: Iterable[str] = DEFAULT_SENSITIVE_KEYS) -> None:
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.actor=actor; self.component=component; self.redact_metadata=redact_metadata; self.sensitive_keys=frozenset(sensitive_keys)
        self.events_path=self.root/"events.jsonl"; self.runs_path=self.root/"runs.json"; self.artifacts_path=self.root/"artifacts.json"; self.edges_path=self.root/"lineage.json"
        self._events=self._load_events(); self._runs=self._load_runs(); self._artifacts=self._load_artifacts(); self._edges=self._load_edges()
    def _load_events(self):
        return [] if not self.events_path.exists() else [TraceEvent(**json.loads(line)) for line in self.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    def _load_runs(self):
        return {} if not self.runs_path.exists() else {k:RunRecord(**v) for k,v in json.loads(self.runs_path.read_text(encoding="utf-8")).items()}
    def _load_artifacts(self):
        return {} if not self.artifacts_path.exists() else {k:ArtifactRef(**v) for k,v in json.loads(self.artifacts_path.read_text(encoding="utf-8")).items()}
    def _load_edges(self):
        return [] if not self.edges_path.exists() else [LineageEdge(**v) for v in json.loads(self.edges_path.read_text(encoding="utf-8"))]
    def _clean(self,value): return redact(value,sensitive_keys=self.sensitive_keys) if self.redact_metadata else value
    def _persist(self):
        self.runs_path.write_text(json.dumps({k:v.to_dict() for k,v in self._runs.items()},sort_keys=True,indent=2),encoding="utf-8")
        self.artifacts_path.write_text(json.dumps({k:v.to_dict() for k,v in self._artifacts.items()},sort_keys=True,indent=2),encoding="utf-8")
        self.edges_path.write_text(json.dumps([e.to_dict() for e in self._edges],sort_keys=True,indent=2),encoding="utf-8")
    def _append(self,event):
        body=event.to_dict(); body["event_hash"]=""; event=replace(event,event_hash=digest_event(body))
        with self.events_path.open("a",encoding="utf-8") as handle: handle.write(json.dumps(event.to_dict(),sort_keys=True,separators=(",",":"))+"\n")
        self._events.append(event); return event
    def record(self,event_type,payload,*,run_id=None,component=None):
        previous=self._events[-1].event_hash if self._events else None
        return self._append(TraceEvent.new(event_type=event_type,actor=self.actor,component=component or self.component,payload=self._clean(payload),run_id=run_id,previous_hash=previous))
    def start_run(self,component,operation,*,parameters=None,environment=None,code_identity=None,parent_run_id=None,metadata=None,seeds=None,packages=()):
        parameters=parameters or {}; environment=environment or default_environment(packages=packages); metadata=dict(metadata or {})
        fp=execution_fingerprint(code_identity=code_identity,environment_identity=environment.get("fingerprint"),input_artifacts=(),parameters=parameters,seeds=seeds)
        metadata["execution_fingerprint"]=fp.digest; metadata["execution_fingerprint_detail"]=fp.to_dict(); metadata["seeds"]=self._clean(seeds or {})
        run=RunRecord.new(component,operation,parameters=self._clean(parameters),environment=self._clean(environment),code_identity=code_identity or fp.code_identity,parent_run_id=parent_run_id,metadata=self._clean(metadata))
        self._runs[run.run_id]=run; self._persist(); self.record("run.started",{"run":run.to_dict()},run_id=run.run_id,component=component); return run
    def _refresh_fingerprint(self,run):
        detail=execution_fingerprint(code_identity=run.code_identity,environment_identity=run.metadata.get("execution_fingerprint_detail",{}).get("environment_identity"),input_artifacts=run.input_artifacts,parameters=run.parameters,seeds=run.metadata.get("seeds",{}))
        return replace(run,metadata={**run.metadata,"execution_fingerprint":detail.digest,"execution_fingerprint_detail":detail.to_dict()})
    def finish_run(self,run_id,*,status=TraceStatus.SUCCEEDED,metadata=None):
        if run_id not in self._runs: raise KeyError(f"Unknown run: {run_id}")
        old=self._refresh_fingerprint(self._runs[run_id]); run=replace(old,finished_at=time.time(),status=status,metadata={**old.metadata,**self._clean(metadata or {})}); self._runs[run_id]=run; self._persist(); self.record("run.finished",{"run":run.to_dict()},run_id=run_id,component=run.component); return run
    def register_payload(self,payload,*,role="artifact",kind=ArtifactKind.PAYLOAD,name=None,media_type="application/json",metadata=None):
        digest=sha256_payload(payload); ref=ArtifactRef.create(digest,kind=kind,media_type=media_type,name=name,size_bytes=len(json.dumps(payload,default=str).encode("utf-8")),metadata={"role":role,**self._clean(metadata or {})}); self._artifacts[ref.artifact_id]=ref; self._persist(); self.record("artifact.registered",{"artifact":ref.to_dict()},component=self.component); return ref
    def register_file(self,path,*,role="artifact",kind=ArtifactKind.FILE,media_type=None,metadata=None):
        p=Path(path); digest=sha256_file(p); ref=ArtifactRef.create(digest,kind=kind,media_type=media_type,name=p.name,size_bytes=p.stat().st_size,uri=str(p.resolve()),metadata={"role":role,**self._clean(metadata or {})}); self._artifacts[ref.artifact_id]=ref; self._persist(); self.record("artifact.registered",{"artifact":ref.to_dict()},component=self.component); return ref
    def attach_input(self,run_id,artifact): self._attach(run_id,artifact,"input")
    def attach_output(self,run_id,artifact): self._attach(run_id,artifact,"output")
    def _attach(self,run_id,artifact,role):
        if run_id not in self._runs: raise KeyError(f"Unknown run: {run_id}")
        aid=artifact.artifact_id if isinstance(artifact,ArtifactRef) else artifact; run=self._runs[run_id]
        if aid not in self._artifacts: raise KeyError(f"Unknown artifact: {aid}")
        run=replace(run,input_artifacts=tuple(dict.fromkeys((*run.input_artifacts,aid)))) if role=="input" else replace(run,output_artifacts=tuple(dict.fromkeys((*run.output_artifacts,aid))))
        self._runs[run_id]=self._refresh_fingerprint(run); self._persist(); self.record(f"run.{role}.attached",{"artifact_id":aid},run_id=run_id,component=run.component)
    def add_lineage(self,source_id,target_id,*,relation="derived_from",run_id=None,metadata=None):
        if source_id==target_id: raise ValueError("A lineage node cannot derive itself")
        if source_id not in self._artifacts or target_id not in self._artifacts: raise KeyError("Lineage endpoints must be registered artifacts")
        graph=LineageGraph()
        for edge in self._edges: graph.add_edge(edge.source_id,edge.target_id,edge.relation,edge.run_id,edge.metadata)
        graph.add_edge(source_id,target_id,relation,run_id,self._clean(metadata or {}))
        edge=LineageEdge(source_id,target_id,relation,run_id,self._clean(metadata or {}))
        if not any(e.source_id==source_id and e.target_id==target_id and e.relation==relation for e in self._edges): self._edges.append(edge); self._persist(); self.record("lineage.edge",{"edge":edge.to_dict()},run_id=run_id)
        return edge
    @property
    def events(self): return tuple(self._events)
    @property
    def runs(self): return tuple(self._runs.values())
    @property
    def artifacts(self): return tuple(self._artifacts.values())
    @property
    def lineage(self): return tuple(self._edges)
    def export_bundle(self,path):
        from .export import export_bundle
        return export_bundle(self,path)

def default_environment(*,packages=()):
    versions={}
    try:
        from importlib.metadata import version
        versions={name:version(name) for name in sorted(set(packages))}
    except Exception: pass
    return {"python":sys.version.split()[0],"platform":platform.platform(),"hostname":socket.gethostname(),"packages":versions}
