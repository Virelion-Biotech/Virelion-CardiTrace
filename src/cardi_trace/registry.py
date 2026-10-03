"""Small local run/artifact registry inspired by MLflow-style tracking APIs."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .query import TraceQuery

@dataclass(frozen=True)
class Registry:
    recorder: Any
    def runs(self, **filters):
        return TraceQuery(self.recorder).runs(**filters)
    def latest(self, *, component=None, operation=None):
        return TraceQuery(self.recorder).latest_run(component=component, operation=operation)
    def artifacts(self, kind=None, role=None):
        result = self.recorder.artifacts
        if kind is not None: result = tuple(a for a in result if str(a.kind) == str(kind))
        if role is not None: result = tuple(a for a in result if a.metadata.get("role") == role)
        return result
    def models(self):
        return self.artifacts(kind="model")
    def datasets(self):
        return self.artifacts(kind="dataset")
    def reports(self):
        return self.artifacts(kind="report")
