"""Human- and machine-readable provenance cards."""
from __future__ import annotations
from typing import Any
from .hashing import sha256_payload
from .provenance import ProvenanceGraph, capture_environment


def provenance_card(graph: ProvenanceGraph, *, title: str, run_id: str | None = None, summary: str | None = None, status: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a compact provenance card suitable for reports and model registries."""
    card = {
        "schema_version": "1.0",
        "title": title,
        "run_id": run_id,
        "summary": summary,
        "status": status,
        "environment": capture_environment(),
        "counts": {"entities": len(graph.entities), "activities": len(graph.activities), "agents": len(graph.agents), "relations": len(graph.relations)},
        "graph_digest": graph.digest,
        "metadata": metadata or {},
    }
    card["card_digest"] = sha256_payload(card)
    return card


def impact_report(graph: ProvenanceGraph, entity_id: str) -> dict[str, Any]:
    """Return reproducible upstream/downstream impact sets for change analysis."""
    return {"entity_id": entity_id, "upstream": sorted(graph.upstream(entity_id)), "downstream": sorted(graph.downstream(entity_id)), "graph_digest": graph.digest}
