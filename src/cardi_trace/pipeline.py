"""Small DVC-like reproducibility primitives: deterministic stage specs and lock state."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from .hashing import sha256_payload

@dataclass(frozen=True)
class Stage:
    name: str
    command: str
    deps: tuple[str, ...] = ()
    outs: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)

    def digest(self, resolved_deps: dict[str, str] | None = None) -> str:
        return sha256_payload({"name": self.name, "command": self.command, "deps": dict(sorted((resolved_deps or {}).items())), "outs": sorted(self.outs), "params": self.params})

@dataclass
class Pipeline:
    stages: dict[str, Stage] = field(default_factory=dict)

    def add(self, stage: Stage):
        if stage.name in self.stages:
            raise ValueError(f"Duplicate stage: {stage.name}")
        self.stages[stage.name] = stage
        return stage

    def topological_order(self) -> list[str]:
        produced = {out: name for name, stage in self.stages.items() for out in stage.outs}
        deps = {name: {produced[d] for d in stage.deps if d in produced} for name, stage in self.stages.items()}
        result = []
        while deps:
            ready = sorted(name for name, need in deps.items() if not need)
            if not ready:
                raise ValueError("Pipeline dependency cycle detected")
            result.extend(ready)
            for name in ready: deps.pop(name)
            for need in deps.values(): need.difference_update(ready)
        return result

def lock_pipeline(pipeline: Pipeline, *, resolved_deps: dict[str, dict[str, str]] | None = None, path=None):
    """Create deterministic lock state describing the exact stage definitions."""
    resolved_deps = resolved_deps or {}
    lock = {"schema": "carditrace.pipeline.lock.v1", "stages": {name: {"digest": stage.digest(resolved_deps.get(name)), "command": stage.command, "deps": list(stage.deps), "outs": list(stage.outs), "params": stage.params} for name, stage in sorted(pipeline.stages.items())}, "order": pipeline.topological_order()}
    lock["digest"] = sha256_payload(lock)
    if path:
        Path(path).write_text(json.dumps(lock, indent=2, sort_keys=True), encoding="utf-8")
    return lock

def changed_stages(previous_lock: dict[str, Any], current_lock: dict[str, Any]) -> list[str]:
    old = previous_lock.get("stages", {}); new = current_lock.get("stages", {})
    changed = {name for name in new if name not in old or new[name].get("digest") != old[name].get("digest")}
    # Downstream invalidation follows the same dependency graph semantics as pipeline repro.
    for name, stage in current_lock.get("stages", {}).items():
        if any(dep in changed for dep in stage.get("deps", ())):
            changed.add(name)
    return sorted(changed)
