"""Read-only trace queries."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TraceQuery:
    """Convenience queries over an existing recorder."""
    recorder: object

    def events(self, event_type: str | None = None, run_id: str | None = None):
        result = self.recorder.events
        if event_type is not None: result = tuple(e for e in result if e.event_type == event_type)
        if run_id is not None: result = tuple(e for e in result if e.run_id == run_id)
        return result

    def runs(self, component: str | None = None, status: str | None = None):
        result = self.recorder.runs
        if component is not None: result = tuple(r for r in result if r.component == component)
        if status is not None: result = tuple(r for r in result if str(r.status) == status)
        return result

    def artifact(self, artifact_id: str):
        return next((a for a in self.recorder.artifacts if a.artifact_id == artifact_id), None)

    def outputs_of(self, run_id: str):
        run = next(r for r in self.recorder.runs if r.run_id == run_id)
        return tuple(filter(None, (self.artifact(a) for a in run.output_artifacts)))

    def inputs_of(self, run_id: str):
        run = next(r for r in self.recorder.runs if r.run_id == run_id)
        return tuple(filter(None, (self.artifact(a) for a in run.input_artifacts)))
