"""Human- and machine-readable provenance cards and reports."""
from __future__ import annotations
from typing import Any
from .hashing import sha256_payload
from .provenance import ProvenanceGraph, capture_environment

def provenance_card(graph: ProvenanceGraph, *, title: str, run_id: str | None = None, summary: str | None = None, status: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    card={"schema_version":"1.0","title":title,"run_id":run_id,"summary":summary,"status":status,"environment":capture_environment(),"counts":{"entities":len(graph.entities),"activities":len(graph.activities),"agents":len(graph.agents),"relations":len(graph.relations)},"graph_digest":graph.digest,"metadata":metadata or {}}
    card["card_digest"]=sha256_payload(card); return card

def impact_report(graph: ProvenanceGraph, entity_id: str) -> dict[str, Any]:
    if entity_id not in graph.entities: raise KeyError(f"Unknown entity: {entity_id}")
    return {"entity_id":entity_id,"upstream":sorted(graph.upstream(entity_id)),"downstream":sorted(graph.downstream(entity_id)),"graph_digest":graph.digest}

def workflow_card(graph: ProvenanceGraph, *, title="CardiTrace workflow", summary=None, metadata=None) -> str:
    """Render a deterministic Markdown provenance card for humans and code review."""
    card=provenance_card(graph,title=title,summary=summary,metadata=metadata)
    lines=[f"# {title}", "", summary or "", "", "## Summary", f"- Entities: {card['counts']['entities']}", f"- Activities: {card['counts']['activities']}", f"- Agents: {card['counts']['agents']}", f"- Relations: {card['counts']['relations']}", f"- Graph digest: `{card['graph_digest']}`", "", "## Activities"]
    for key, activity in sorted(graph.activities.items()):
        lines.append(f"- `{key}` — {activity.attributes.get('component','?')}.{activity.attributes.get('operation','?')} — {activity.attributes.get('status','unknown')}")
    lines += ["", "## Activity dataflow"]
    for rel in graph.relations:
        if rel.relation in {"used","wasGeneratedBy","wasDerivedFrom"}: lines.append(f"- `{rel.relation}`: `{rel.source}` → `{rel.target}`")
    lines += ["", f"Card digest: `{card['card_digest']}`"]
    return "\n".join(lines)+"\n"

def write_workflow_card(graph: ProvenanceGraph, path, *, title="CardiTrace workflow", summary=None, metadata=None):
    from pathlib import Path
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(workflow_card(graph,title=title,summary=summary,metadata=metadata),encoding="utf-8"); return target
