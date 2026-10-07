"""Append-only, content-addressed provenance recorder."""

from __future__ import annotations
import json, platform, sys, socket, time, math, os
from copy import deepcopy
from functools import wraps
from .storage import ledger_lock, atomic_json
from .journal import refresh_fingerprint
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable
from .fingerprint import execution_fingerprint
from .hashing import digest_event, sha256_file, sha256_payload
from .lineage import LineageGraph
from .models import (
    ArtifactKind,
    ArtifactRef,
    LineageEdge,
    RunRecord,
    TraceEvent,
    TraceStatus,
)
from .redaction import DEFAULT_SENSITIVE_KEYS, redact


def mutation(fn):
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        with ledger_lock(self.root):
            self._reload()
            from .audit import verify_recorder

            report = verify_recorder(self, verify_local_files=False)
            if not report.valid:
                raise ValueError(
                    "Ledger integrity check failed; inspect and explicitly recover snapshots"
                )
            try:
                result = fn(self, *args, **kwargs)
                self._persist()
                return deepcopy(result)
            finally:
                self._reload()

    return wrapped


class TraceRecorder:
    """Durable provenance ledger with execution identity, metrics, tags, and lineage support."""

    def __init__(
        self,
        root,
        actor="unknown",
        component="CardiTrace",
        *,
        redact_metadata=True,
        sensitive_keys=DEFAULT_SENSITIVE_KEYS,
    ):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.actor = actor
        self.component = component
        self.redact_metadata = redact_metadata
        self.sensitive_keys = frozenset(sensitive_keys)
        self.events_path = self.root / "events.jsonl"
        self.runs_path = self.root / "runs.json"
        self.artifacts_path = self.root / "artifacts.json"
        self.edges_path = self.root / "lineage.json"
        with ledger_lock(self.root):
            self._reload()

    def _reload(self):
        self._events = self._load_events()
        self._runs = self._load_runs()
        self._artifacts = self._load_artifacts()
        self._edges = self._load_edges()

    def _load_events(self):
        return (
            []
            if not self.events_path.exists()
            else [
                TraceEvent(**json.loads(x))
                for x in self.events_path.read_text(encoding="utf-8").splitlines()
                if x.strip()
            ]
        )

    def _load_runs(self):
        data = (
            {}
            if not self.runs_path.exists()
            else json.loads(self.runs_path.read_text(encoding="utf-8"))
        )
        if any(k != v.get("run_id") for k, v in data.items()):
            raise ValueError("Run snapshot key mismatch")
        return {k: RunRecord(**v) for k, v in data.items()}

    def _load_artifacts(self):
        data = (
            {}
            if not self.artifacts_path.exists()
            else json.loads(self.artifacts_path.read_text(encoding="utf-8"))
        )
        if any(k != v.get("artifact_id") for k, v in data.items()):
            raise ValueError("Artifact snapshot key mismatch")
        return {k: ArtifactRef(**v) for k, v in data.items()}

    def _load_edges(self):
        return (
            []
            if not self.edges_path.exists()
            else [
                LineageEdge(**v)
                for v in json.loads(self.edges_path.read_text(encoding="utf-8"))
            ]
        )

    def _clean(self, value):
        return deepcopy(
            redact(value, sensitive_keys=self.sensitive_keys)
            if self.redact_metadata
            else value
        )

    def _persist(self):
        atomic_json(self.runs_path, {k: v.to_dict() for k, v in self._runs.items()})
        atomic_json(
            self.artifacts_path, {k: v.to_dict() for k, v in self._artifacts.items()}
        )
        atomic_json(self.edges_path, [e.to_dict() for e in self._edges])

    def _append(self, event):
        body = event.to_dict()
        body["event_hash"] = ""
        event = replace(event, event_hash=digest_event(body))
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    event.to_dict(),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        self._events.append(event)
        return event

    @mutation
    def record(self, event_type, payload, *, run_id=None, component=None):
        if event_type in {
            "run.started",
            "run.finished",
            "run.input.attached",
            "run.output.attached",
            "run.metric",
            "run.tag",
            "artifact.registered",
            "lineage.edge",
        }:
            raise ValueError(
                "Reserved event type; use the corresponding recorder method"
            )
        if not isinstance(payload, dict):
            raise TypeError("Event payload must be a mapping")
        return self._record(event_type, payload, run_id=run_id, component=component)

    def _record(self, event_type, payload, *, run_id=None, component=None):
        previous = self._events[-1].event_hash if self._events else None
        return self._append(
            TraceEvent.new(
                event_type=event_type,
                actor=self.actor,
                component=component or self.component,
                payload=self._clean(payload),
                run_id=run_id,
                previous_hash=previous,
            )
        )

    @mutation
    def start_run(
        self,
        component,
        operation,
        *,
        parameters=None,
        environment=None,
        code_identity=None,
        parent_run_id=None,
        metadata=None,
        seeds=None,
        packages=(),
        tags=None,
    ):
        parameters = self._clean(parameters or {})
        environment = self._clean(
            environment
            if environment is not None
            else default_environment(packages=packages)
        )
        metadata = dict(metadata or {})
        if parent_run_id is not None and parent_run_id not in self._runs:
            raise KeyError(f"Unknown parent run: {parent_run_id}")
        environment["fingerprint"] = sha256_payload(
            {k: v for k, v in environment.items() if k != "fingerprint"}
        )
        fp = execution_fingerprint(
            code_identity=code_identity,
            environment_identity=environment.get("fingerprint"),
            input_artifacts=(),
            parameters=parameters,
            seeds=self._clean(seeds or {}),
        )
        metadata["execution_fingerprint"] = fp.digest
        metadata["execution_fingerprint_detail"] = fp.to_dict()
        metadata["seeds"] = self._clean(seeds or {})
        run = RunRecord.new(
            component,
            operation,
            parameters=self._clean(parameters),
            environment=self._clean(environment),
            code_identity=code_identity or fp.code_identity,
            parent_run_id=parent_run_id,
            metadata=self._clean(metadata),
            tags=self._clean(tags or {}),
        )
        self._runs[run.run_id] = run
        self._record(
            "run.started",
            {"run": run.to_dict()},
            run_id=run.run_id,
            component=component,
        )
        return run

    def _refresh_fingerprint(self, run):
        return refresh_fingerprint(run)

    @mutation
    def log_metric(self, run_id, name, value):
        if run_id not in self._runs:
            raise KeyError(f"Unknown run: {run_id}")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("metric value must be numeric") from exc
        if not math.isfinite(numeric):
            raise ValueError("metric value must be finite")
        run = replace(
            self._runs[run_id],
            metrics={**self._runs[run_id].metrics, str(name): numeric},
        )
        self._runs[run_id] = run
        self._record(
            "run.metric",
            {"name": str(name), "value": numeric},
            run_id=run_id,
            component=run.component,
        )
        return numeric

    @mutation
    def set_tag(self, run_id, name, value):
        if run_id not in self._runs:
            raise KeyError(f"Unknown run: {run_id}")
        value = self._clean({str(name): str(value)})[str(name)]
        run = replace(
            self._runs[run_id], tags={**self._runs[run_id].tags, str(name): str(value)}
        )
        self._runs[run_id] = run
        self._record(
            "run.tag",
            {"name": str(name), "value": str(value)},
            run_id=run_id,
            component=run.component,
        )
        return str(value)

    def log_metrics(self, run_id, metrics):
        for name, value in metrics.items():
            self.log_metric(run_id, name, value)

    def set_tags(self, run_id, tags):
        for name, value in tags.items():
            self.set_tag(run_id, name, value)

    @mutation
    def finish_run(self, run_id, *, status=TraceStatus.SUCCEEDED, metadata=None):
        if run_id not in self._runs:
            raise KeyError(f"Unknown run: {run_id}")
        status = TraceStatus(status)
        if status == TraceStatus.RUNNING:
            raise ValueError("finish status must be terminal")
        if self._runs[run_id].finished_at is not None:
            raise ValueError("Run already finished")
        if (
            metadata
            and {"execution_fingerprint", "execution_fingerprint_detail", "seeds"}
            & metadata.keys()
        ):
            raise ValueError("Execution identity metadata is reserved")
        old = self._refresh_fingerprint(self._runs[run_id])
        run = replace(
            old,
            finished_at=time.time(),
            status=status,
            metadata={**old.metadata, **self._clean(metadata or {})},
        )
        self._runs[run_id] = run
        self._record(
            "run.finished",
            {"run": run.to_dict()},
            run_id=run_id,
            component=run.component,
        )
        return run

    @mutation
    def register_payload(
        self,
        payload,
        *,
        role="artifact",
        kind=ArtifactKind.PAYLOAD,
        name=None,
        media_type="application/json",
        metadata=None,
    ):
        from .hashing import canonical_json

        digest = sha256_payload(payload)
        ref = ArtifactRef.create(
            digest,
            kind=kind,
            media_type=media_type,
            name=name,
            size_bytes=len(canonical_json(payload)),
            metadata={"role": role, **self._clean(metadata or {})},
        )
        self._artifacts[ref.artifact_id] = ref
        self._record(
            "artifact.registered", {"artifact": ref.to_dict()}, component=self.component
        )
        return ref

    @mutation
    def register_file(
        self,
        path,
        *,
        role="artifact",
        kind=ArtifactKind.FILE,
        media_type=None,
        metadata=None,
    ):
        p = Path(path)
        digest = sha256_file(p)
        ref = ArtifactRef.create(
            digest,
            kind=kind,
            media_type=media_type,
            name=p.name,
            size_bytes=p.stat().st_size,
            uri=str(p.resolve()),
            metadata={"role": role, **self._clean(metadata or {})},
        )
        self._artifacts[ref.artifact_id] = ref
        self._record(
            "artifact.registered", {"artifact": ref.to_dict()}, component=self.component
        )
        return ref

    def attach_input(self, run_id, artifact):
        self._attach(run_id, artifact, "input")

    def attach_output(self, run_id, artifact):
        self._attach(run_id, artifact, "output")

    @mutation
    def _attach(self, run_id, artifact, role):
        if run_id not in self._runs:
            raise KeyError(f"Unknown run: {run_id}")
        aid = artifact.artifact_id if isinstance(artifact, ArtifactRef) else artifact
        run = self._runs[run_id]
        if aid not in self._artifacts:
            raise KeyError(f"Unknown artifact: {aid}")
        run = (
            replace(
                run, input_artifacts=tuple(dict.fromkeys((*run.input_artifacts, aid)))
            )
            if role == "input"
            else replace(
                run, output_artifacts=tuple(dict.fromkeys((*run.output_artifacts, aid)))
            )
        )
        self._runs[run_id] = self._refresh_fingerprint(run)
        self._record(
            f"run.{role}.attached",
            {"artifact_id": aid},
            run_id=run_id,
            component=run.component,
        )

    @mutation
    def add_lineage(
        self,
        source_id,
        target_id,
        *,
        relation="derived_from",
        run_id=None,
        metadata=None,
    ):
        if run_id is not None and run_id not in self._runs:
            raise KeyError(f"Unknown run: {run_id}")
        if source_id == target_id:
            raise ValueError("A lineage node cannot derive itself")
        if source_id not in self._artifacts or target_id not in self._artifacts:
            raise KeyError("Lineage endpoints must be registered artifacts")
        graph = LineageGraph()
        [
            graph.add_edge(e.source_id, e.target_id, e.relation, e.run_id, e.metadata)
            for e in self._edges
        ]
        graph.add_edge(
            source_id, target_id, relation, run_id, self._clean(metadata or {})
        )
        edge = LineageEdge(
            source_id, target_id, relation, run_id, self._clean(metadata or {})
        )
        if not any(
            e.source_id == source_id
            and e.target_id == target_id
            and e.relation == relation
            for e in self._edges
        ):
            self._edges.append(edge)
            self._record("lineage.edge", {"edge": edge.to_dict()}, run_id=run_id)
        return edge

    @property
    def events(self):
        return deepcopy(tuple(self._events))

    @property
    def runs(self):
        return deepcopy(
            tuple(sorted(self._runs.values(), key=lambda r: (r.started_at, r.run_id)))
        )

    @property
    def artifacts(self):
        return deepcopy(tuple(self._artifacts.values()))

    @property
    def lineage(self):
        return deepcopy(tuple(self._edges))

    def export_bundle(self, path):
        from .export import export_bundle

        return export_bundle(self, path)


def default_environment(*, packages=()):
    versions = {}
    from importlib.metadata import version, PackageNotFoundError

    for name in sorted(set(packages)):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "packages": versions,
    }
