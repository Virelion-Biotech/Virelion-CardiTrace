"""High-performance read-only query helpers over a trace."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TraceQuery:
    recorder: object

    def events(self, event_type: str | None = None, run_id: str | None = None, component: str | None = None):
        result = self.recorder.events
        if event_type is not None:
            result = tuple(e for e in result if e.event_type == event_type)
        if run_id is not None:
            result = tuple(e for e in result if e.run_id == run_id)
        if component is not None:
            result = tuple(e for e in result if e.component == component)
        return result

    def runs(self, component: str | None = None, status: str | None = None, operation: str | None = None):
        result = self.recorder.runs
        if component is not None:
            result = tuple(r for r in result if r.component == component)
        if status is not None:
            result = tuple(r for r in result if str(r.status) == status)
        if operation is not None:
            result = tuple(r for r in result if r.operation == operation)
        return result

    def artifact(self, artifact_id: str):
        return next((a for a in self.recorder.artifacts if a.artifact_id == artifact_id), None)

    def outputs_of(self, run_id: str):
        run = next(r for r in self.recorder.runs if r.run_id == run_id)
        return tuple(filter(None, (self.artifact(a) for a in run.output_artifacts)))

    def inputs_of(self, run_id: str):
        run = next(r for r in self.recorder.runs if r.run_id == run_id)
        return tuple(filter(None, (self.artifact(a) for a in run.input_artifacts)))

    def descendants(self, artifact_id: str) -> set[str]:
        from .lineage import LineageGraph
        graph = LineageGraph()
        for edge in self.recorder.lineage:
            graph.add_edge(edge.source_id, edge.target_id, edge.relation, edge.run_id, edge.metadata)
        return graph.descendants(artifact_id)

    def ancestors(self, artifact_id: str) -> set[str]:
        from .lineage import LineageGraph
        graph = LineageGraph()
        for edge in self.recorder.lineage:
            graph.add_edge(edge.source_id, edge.target_id, edge.relation, edge.run_id, edge.metadata)
        return graph.ancestors(artifact_id)

    def latest_run(self, *, component: str | None = None, operation: str | None = None):
        runs = self.runs(component=component, operation=operation)
        return max(runs, key=lambda r: r.started_at, default=None)

    def execution_fingerprints(self) -> dict[str, str]:
        return {r.run_id: r.metadata["execution_fingerprint"] for r in self.recorder.runs if r.metadata.get("execution_fingerprint")}
