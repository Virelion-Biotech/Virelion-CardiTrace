"""Interoperable biomedical provenance graph and deterministic dataset manifests."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json, platform, sys
from .hashing import sha256_file, sha256_payload
from .models import ArtifactKind, ArtifactRef

def _now() -> str: return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class ProvEntity:
    id: str
    attributes: dict[str, Any] = field(default_factory=dict)
@dataclass(frozen=True)
class ProvActivity:
    id: str
    started_at: str
    ended_at: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
@dataclass(frozen=True)
class ProvAgent:
    id: str
    attributes: dict[str, Any] = field(default_factory=dict)
@dataclass(frozen=True)
class ProvRelation:
    relation: str
    source: str
    target: str
    attributes: dict[str, Any] = field(default_factory=dict)

class ProvenanceGraph:
    """Dependency-free semantic provenance graph following core W3C PROV relationships."""
    def __init__(self) -> None:
        self.entities={}; self.activities={}; self.agents={}; self.relations=[]
    def entity(self, entity_id: str, **attributes: Any) -> ProvEntity:
        item=ProvEntity(entity_id,attributes); self.entities[entity_id]=item; return item
    def activity(self, activity_id: str, *, started_at: str|None=None, ended_at: str|None=None, **attributes: Any) -> ProvActivity:
        item=ProvActivity(activity_id,started_at or _now(),ended_at,attributes); self.activities[activity_id]=item; return item
    def agent(self, agent_id: str, **attributes: Any) -> ProvAgent:
        item=ProvAgent(agent_id,attributes); self.agents[agent_id]=item; return item
    def relation(self, relation: str, source: str, target: str, **attributes: Any) -> ProvRelation:
        item=ProvRelation(relation,source,target,attributes)
        if item not in self.relations: self.relations.append(item)
        return item
    def used(self, activity_id, entity_id, **attributes): return self.relation("used",activity_id,entity_id,**attributes)
    def generated(self, entity_id, activity_id, **attributes): return self.relation("wasGeneratedBy",entity_id,activity_id,**attributes)
    def derived(self, entity_id, source_id, **attributes): return self.relation("wasDerivedFrom",entity_id,source_id,**attributes)
    def associated(self, activity_id, agent_id, **attributes): return self.relation("wasAssociatedWith",activity_id,agent_id,**attributes)
    def attributed(self, entity_id, agent_id, **attributes): return self.relation("wasAttributedTo",entity_id,agent_id,**attributes)
    def informed(self, informed_id, informant_id, **attributes): return self.relation("wasInformedBy",informed_id,informant_id,**attributes)
    def specialized(self, specific_id, general_id, **attributes): return self.relation("specializationOf",specific_id,general_id,**attributes)
    def to_dict(self):
        return {"prefix":{"prov":"http://www.w3.org/ns/prov#","ct":"https://virelion.org/cardi-trace#"},"entity":{k:{"id":v.id,**v.attributes} for k,v in sorted(self.entities.items())},"activity":{k:{"id":v.id,"startedAtTime":v.started_at,**({"endedAtTime":v.ended_at} if v.ended_at else {}),**v.attributes} for k,v in sorted(self.activities.items())},"agent":{k:{"id":v.id,**v.attributes} for k,v in sorted(self.agents.items())},"relations":[asdict(r) for r in self.relations]}
    def to_prov_json(self):
        out={"prefix":{"prov":"http://www.w3.org/ns/prov#","ct":"https://virelion.org/cardi-trace#"},"entity":{},"activity":{},"agent":{},"wasGeneratedBy":{},"used":{},"wasDerivedFrom":{},"wasAssociatedWith":{},"wasAttributedTo":{},"wasInformedBy":{}}
        for k,v in sorted(self.entities.items()): out["entity"][k]=v.attributes
        for k,v in sorted(self.activities.items()): out["activity"][k]={"prov:startTime":v.started_at,**({"prov:endTime":v.ended_at} if v.ended_at else {}),**v.attributes}
        for k,v in sorted(self.agents.items()): out["agent"][k]=v.attributes
        counters={r:0 for r in out}
        for r in self.relations:
            if r.relation not in out: continue
            counters[r.relation]+=1; key=f"{r.relation}:{counters[r.relation]}"
            if r.relation=="used": out[r.relation][key]={"prov:activity":r.source,"prov:entity":r.target,**r.attributes}
            elif r.relation=="wasGeneratedBy": out[r.relation][key]={"prov:entity":r.source,"prov:activity":r.target,**r.attributes}
            elif r.relation=="wasDerivedFrom": out[r.relation][key]={"prov:generatedEntity":r.source,"prov:usedEntity":r.target,**r.attributes}
            elif r.relation=="wasAssociatedWith": out[r.relation][key]={"prov:activity":r.source,"prov:agent":r.target,**r.attributes}
            elif r.relation=="wasAttributedTo": out[r.relation][key]={"prov:entity":r.source,"prov:agent":r.target,**r.attributes}
            elif r.relation=="wasInformedBy": out[r.relation][key]={"prov:informed":r.source,"prov:informing":r.target,**r.attributes}
        return out
    @property
    def digest(self): return sha256_payload(self.to_dict())
    def to_json(self, *, indent=2, prov_json=False): return json.dumps(self.to_prov_json() if prov_json else self.to_dict(),indent=indent,sort_keys=True,default=str)
    def _walk(self,node_id,*,forward):
        seen={node_id}; changed=True
        while changed:
            changed=False
            for rel in self.relations:
                left,right=(rel.source,rel.target) if forward else (rel.target,rel.source)
                if left in seen and right not in seen: seen.add(right); changed=True
        return seen
    def upstream(self,entity_id): return self._walk(entity_id,forward=False)
    def downstream(self,entity_id): return self._walk(entity_id,forward=True)

def dataset_manifest(source, artifacts, *, dataset_id=None, version=None, organism=None, modality=None, condition=None, metadata=None):
    items=sorted((a.to_dict() for a in artifacts),key=lambda x:x["artifact_id"])
    manifest={"schema_version":"2.0","dataset_id":dataset_id or "","source":source,"version":version,"organism":organism,"modality":modality,"condition":condition,"artifacts":items,"metadata":metadata or {}}
    if not manifest["dataset_id"]: manifest["dataset_id"]=f"dataset:{sha256_payload({'source':source,'version':version,'artifacts':items})[:32]}"
    manifest["manifest_digest"]=sha256_payload(manifest); return manifest

def register_source(graph, source, *, source_type="dataset", version=None, uri=None, **metadata):
    source_id=f"source:{sha256_payload({'source':source,'version':version})[:24]}"; graph.entity(source_id,source=source,source_type=source_type,version=version,uri=uri,**metadata); return source_id

def register_file_entity(graph, path, *, role="artifact", **metadata):
    p=Path(path); digest=sha256_file(p); entity_id=f"artifact:sha256:{digest}"; graph.entity(entity_id,kind=str(ArtifactKind.FILE),name=p.name,digest=digest,size_bytes=p.stat().st_size,uri=str(p.resolve()),role=role,**metadata); return entity_id

def capture_environment(): return {"python":sys.version.split()[0],"platform":platform.platform(),"implementation":platform.python_implementation()}

def graph_from_recorder(recorder):
    graph=ProvenanceGraph(); actor=getattr(recorder,"actor","unknown"); component=getattr(recorder,"component","CardiTrace"); agent_id=f"agent:{actor}"; graph.agent(agent_id,type="software",name=component)
    for artifact in recorder.artifacts:
        entity_id=f"artifact:{artifact.artifact_id}"; graph.entity(entity_id,**artifact.to_dict()); graph.attributed(entity_id,agent_id)
    for run in recorder.runs:
        aid=f"activity:{run.run_id}"; end=datetime.fromtimestamp(run.finished_at,timezone.utc).isoformat() if run.finished_at else None
        graph.activity(aid,started_at=datetime.fromtimestamp(run.started_at,timezone.utc).isoformat(),ended_at=end,component=run.component,operation=run.operation,status=run.status,parameters=run.parameters,environment=run.environment,code_identity=run.code_identity,metadata=run.metadata); graph.associated(aid,agent_id)
        if run.parent_run_id: graph.informed(aid,f"activity:{run.parent_run_id}")
        for artifact_id in run.input_artifacts: graph.used(aid,f"artifact:{artifact_id}")
        for artifact_id in run.output_artifacts: graph.generated(f"artifact:{artifact_id}",aid)
    for edge in recorder.lineage: graph.derived(f"artifact:{edge.target_id}",f"artifact:{edge.source_id}",relation=edge.relation,run_id=edge.run_id,**edge.metadata)
    return graph
