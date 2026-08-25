"""Append-only trace recorder."""
from __future__ import annotations

import json
import platform
import sys
import socket
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from .hashing import digest_event, sha256_file, sha256_payload
from .models import ArtifactKind, ArtifactRef, RunRecord, TraceEvent, TraceStatus


class TraceRecorder:
    """Small, deterministic provenance ledger backed by JSONL plus a registry."""

    def __init__(self, root: str | Path, actor: str = "unknown", component: str = "CardiTrace") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.actor = actor
        self.component = component
        self.events_path = self.root / "events.jsonl"
        self.runs_path = self.root / "runs.json"
        self.artifacts_path = self.root / "artifacts.json"
        self._events: list[TraceEvent] = self._load_events()
        self._runs: dict[str, RunRecord] = self._load_runs()
        self._artifacts: dict[str, ArtifactRef] = self._load_artifacts()

    def _load_events(self) -> list[TraceEvent]:
        if not self.events_path.exists(): return []
        return [TraceEvent(**json.loads(line)) for line in self.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _load_runs(self) -> dict[str, RunRecord]:
        if not self.runs_path.exists(): return {}
        return {k: RunRecord(**v) for k, v in json.loads(self.runs_path.read_text(encoding="utf-8")).items()}

    def _load_artifacts(self) -> dict[str, ArtifactRef]:
        if not self.artifacts_path.exists(): return {}
        return {k: ArtifactRef(**v) for k, v in json.loads(self.artifacts_path.read_text(encoding="utf-8")).items()}

    def _persist(self) -> None:
        self.runs_path.write_text(json.dumps({k: v.to_dict() for k, v in self._runs.items()}, sort_keys=True, indent=2), encoding="utf-8")
        self.artifacts_path.write_text(json.dumps({k: v.to_dict() for k, v in self._artifacts.items()}, sort_keys=True, indent=2), encoding="utf-8")

    def _append(self, event: TraceEvent) -> TraceEvent:
        body = event.to_dict(); body["event_hash"] = ""
        event = replace(event, event_hash=digest_event(body))
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
        self._events.append(event)
        return event

    def record(self, event_type: str, payload: dict[str, Any], *, run_id: str | None = None, component: str | None = None) -> TraceEvent:
        previous = self._events[-1].event_hash if self._events else None
        return self._append(TraceEvent.new(event_type=event_type, actor=self.actor, component=component or self.component, payload=payload, run_id=run_id, previous_hash=previous))

    def start_run(self, component: str, operation: str, *, parameters: dict[str, Any] | None = None, environment: dict[str, Any] | None = None, code_identity: str | None = None, parent_run_id: str | None = None, metadata: dict[str, Any] | None = None) -> RunRecord:
        env = environment or default_environment()
        run = RunRecord.new(component, operation, parameters=parameters or {}, environment=env, code_identity=code_identity, parent_run_id=parent_run_id, metadata=metadata or {})
        self._runs[run.run_id] = run; self._persist()
        self.record("run.started", {"run": run.to_dict()}, run_id=run.run_id, component=component)
        return run

    def finish_run(self, run_id: str, *, status: TraceStatus = TraceStatus.SUCCEEDED, metadata: dict[str, Any] | None = None) -> RunRecord:
        if run_id not in self._runs: raise KeyError(f"Unknown run: {run_id}")
        old = self._runs[run_id]
        run = replace(old, finished_at=time.time(), status=status, metadata={**old.metadata, **(metadata or {})})
        self._runs[run_id] = run; self._persist()
        self.record("run.finished", {"run": run.to_dict()}, run_id=run_id, component=run.component)
        return run

    def register_payload(self, payload: Any, *, role: str = "artifact", kind: str = ArtifactKind.PAYLOAD, name: str | None = None, media_type: str = "application/json", metadata: dict[str, Any] | None = None) -> ArtifactRef:
        digest = sha256_payload(payload)
        ref = ArtifactRef.create(digest, kind=kind, media_type=media_type, name=name, size_bytes=len(json.dumps(payload, default=str).encode("utf-8")), metadata={"role": role, **(metadata or {})})
        self._artifacts[ref.artifact_id] = ref; self._persist()
        self.record("artifact.registered", {"artifact": ref.to_dict()}, component=self.component)
        return ref

    def register_file(self, path: str | Path, *, role: str = "artifact", kind: str = ArtifactKind.FILE, media_type: str | None = None, metadata: dict[str, Any] | None = None) -> ArtifactRef:
        p = Path(path); digest = sha256_file(p)
        ref = ArtifactRef.create(digest, kind=kind, media_type=media_type, name=p.name, size_bytes=p.stat().st_size, uri=str(p.resolve()), metadata={"role": role, **(metadata or {})})
        self._artifacts[ref.artifact_id] = ref; self._persist()
        self.record("artifact.registered", {"artifact": ref.to_dict()}, component=self.component)
        return ref

    def attach_input(self, run_id: str, artifact: ArtifactRef | str) -> None:
        self._attach(run_id, artifact, "input")

    def attach_output(self, run_id: str, artifact: ArtifactRef | str) -> None:
        self._attach(run_id, artifact, "output")

    def _attach(self, run_id: str, artifact: ArtifactRef | str, role: str) -> None:
        if run_id not in self._runs: raise KeyError(f"Unknown run: {run_id}")
        aid = artifact.artifact_id if isinstance(artifact, ArtifactRef) else artifact
        run = self._runs[run_id]
        if aid not in self._artifacts: raise KeyError(f"Unknown artifact: {aid}")
        if role == "input": run = replace(run, input_artifacts=tuple(dict.fromkeys((*run.input_artifacts, aid))))
        else: run = replace(run, output_artifacts=tuple(dict.fromkeys((*run.output_artifacts, aid))))
        self._runs[run_id] = run; self._persist()
        self.record(f"run.{role}.attached", {"artifact_id": aid}, run_id=run_id, component=run.component)

    @property
    def events(self) -> tuple[TraceEvent, ...]: return tuple(self._events)
    @property
    def runs(self) -> tuple[RunRecord, ...]: return tuple(self._runs.values())
    @property
    def artifacts(self) -> tuple[ArtifactRef, ...]: return tuple(self._artifacts.values())

    def export_bundle(self, path: str | Path) -> Path:
        from .export import export_bundle
        return export_bundle(self, path)


def default_environment() -> dict[str, Any]:
    return {"python": sys.version.split()[0], "platform": platform.platform(), "hostname": socket.gethostname()}
