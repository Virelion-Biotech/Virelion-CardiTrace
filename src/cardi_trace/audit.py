"""Multi-layer verification for CardiTrace traces."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .hashing import digest_event, sha256_file
from .merkle import recorder_merkle_root
from .models import AuditIssue


@dataclass(frozen=True)
class AuditReport:
    valid: bool
    events_checked: int
    artifacts_checked: int
    runs_checked: int
    lineage_edges_checked: int = 0
    commitment: str | None = None
    issues: tuple[AuditIssue, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "events_checked": self.events_checked,
            "artifacts_checked": self.artifacts_checked,
            "runs_checked": self.runs_checked,
            "lineage_edges_checked": self.lineage_edges_checked,
            "commitment": self.commitment,
            "issues": [i.to_dict() for i in self.issues],
        }


def verify_recorder(
    recorder, *, verify_local_files: bool = True, require_local_files: bool = False
) -> AuditReport:
    """Verify event chaining, artifact references, execution identity, lineage, and local file content hashes."""
    issues: list[AuditIssue] = []
    previous = None
    import math

    for event in recorder.events:
        if event.previous_hash != previous:
            issues.append(
                AuditIssue(
                    "error",
                    "event.chain",
                    "Previous hash does not match chain",
                    event.event_id,
                )
            )
        body = event.to_dict()
        body["event_hash"] = ""
        if event.event_hash != digest_event(body):
            issues.append(
                AuditIssue("error", "event.hash", "Event hash mismatch", event.event_id)
            )
        previous = event.event_hash
    from .journal import replay_events, state_payload, refresh_fingerprint
    from .hashing import sha256_payload

    try:
        recovered = state_payload(*replay_events(recorder.events))
        actual = state_payload(
            {r.run_id: r for r in recorder.runs},
            {a.artifact_id: a for a in recorder.artifacts},
            list(recorder.lineage),
        )
        if sha256_payload(recovered) != sha256_payload(actual):
            issues.append(
                AuditIssue(
                    "error",
                    "snapshot.journal",
                    "Derived snapshots differ from event journal",
                )
            )
    except (ValueError, TypeError, KeyError) as exc:
        issues.append(AuditIssue("error", "journal.replay", str(exc)))
    artifact_ids = {a.artifact_id for a in recorder.artifacts}
    if len(artifact_ids) != len(recorder.artifacts) or len(
        {r.run_id for r in recorder.runs}
    ) != len(recorder.runs):
        issues.append(
            AuditIssue(
                "error", "snapshot.duplicate", "Duplicate run or artifact identity"
            )
        )
    for artifact in recorder.artifacts:
        if (
            artifact.artifact_id != f"sha256:{artifact.digest}"
            or len(artifact.digest) != 64
            or any(c not in "0123456789abcdef" for c in artifact.digest)
        ):
            issues.append(
                AuditIssue(
                    "error",
                    "artifact.identity",
                    "Invalid artifact digest/identity",
                    artifact.artifact_id,
                )
            )
        if verify_local_files and artifact.uri and Path(artifact.uri).is_absolute():
            path = Path(artifact.uri)
            if path.exists() and path.is_file():
                actual = sha256_file(path)
                if actual != artifact.digest:
                    issues.append(
                        AuditIssue(
                            "error",
                            "artifact.hash",
                            "Local file content hash mismatch",
                            artifact.artifact_id,
                        )
                    )
            else:
                issues.append(
                    AuditIssue(
                        "error" if require_local_files else "warning",
                        "artifact.missing",
                        "Referenced local file is unavailable to verifier",
                        artifact.artifact_id,
                    )
                )
    run_ids = {r.run_id for r in recorder.runs}
    for run in recorder.runs:
        if (
            not math.isfinite(run.started_at)
            or (run.finished_at is not None and not math.isfinite(run.finished_at))
            or any(not math.isfinite(v) for v in run.metrics.values())
        ):
            issues.append(
                AuditIssue("error", "run.numeric", "Non-finite run values", run.run_id)
            )
        if run.environment.get("fingerprint"):
            env_digest = sha256_payload(
                {k: v for k, v in run.environment.items() if k != "fingerprint"}
            )
            if (
                run.environment["fingerprint"] != env_digest
                or run.metadata.get("execution_fingerprint_detail", {}).get(
                    "environment_identity"
                )
                != env_digest
            ):
                issues.append(
                    AuditIssue(
                        "error",
                        "run.environment",
                        "Environment fingerprint mismatch",
                        run.run_id,
                    )
                )
        if run.parent_run_id and run.parent_run_id not in run_ids:
            issues.append(
                AuditIssue("error", "run.parent", "Unknown parent run", run.run_id)
            )
        if str(run.status) not in {"running", "succeeded", "failed", "cancelled"}:
            issues.append(
                AuditIssue("error", "run.status", "Unknown status", run.run_id)
            )
        if run.finished_at is not None and (
            run.finished_at < run.started_at or str(run.status) == "running"
        ):
            issues.append(
                AuditIssue(
                    "error", "run.time", "Invalid run timestamps/status", run.run_id
                )
            )
        if (
            run.metadata.get("execution_fingerprint")
            and refresh_fingerprint(run).metadata["execution_fingerprint"]
            != run.metadata["execution_fingerprint"]
        ):
            issues.append(
                AuditIssue(
                    "error",
                    "run.fingerprint",
                    "Execution fingerprint mismatch",
                    run.run_id,
                )
            )
        for aid in (*run.input_artifacts, *run.output_artifacts):
            if aid not in artifact_ids:
                issues.append(
                    AuditIssue(
                        "error",
                        "run.artifact",
                        f"Run references unknown artifact {aid}",
                        run.run_id,
                    )
                )
        if str(run.status) != "running" and run.finished_at is None:
            issues.append(
                AuditIssue(
                    "error",
                    "run.finish",
                    "Terminal run has no finish timestamp",
                    run.run_id,
                )
            )
        if not run.metadata.get("execution_fingerprint"):
            issues.append(
                AuditIssue(
                    "warning",
                    "run.fingerprint",
                    "Run has no execution fingerprint",
                    run.run_id,
                )
            )
    edge_count = 0
    if hasattr(recorder, "lineage"):
        edge_count = len(recorder.lineage)
        from .lineage import LineageGraph

        graph = LineageGraph()
        for edge in recorder.lineage:
            if edge.run_id is not None and edge.run_id not in run_ids:
                issues.append(
                    AuditIssue(
                        "error", "lineage.run", "Unknown lineage run", edge.run_id
                    )
                )
            if edge.source_id not in artifact_ids or edge.target_id not in artifact_ids:
                issues.append(
                    AuditIssue(
                        "error",
                        "lineage.artifact",
                        "Lineage references unknown artifact",
                        edge.source_id,
                    )
                )
                continue
            try:
                graph.add_edge(
                    edge.source_id,
                    edge.target_id,
                    edge.relation,
                    edge.run_id,
                    edge.metadata,
                )
            except ValueError as exc:
                issues.append(
                    AuditIssue("error", "lineage.cycle", str(exc), edge.target_id)
                )
    return AuditReport(
        not any(i.severity == "error" for i in issues),
        len(recorder.events),
        len(recorder.artifacts),
        len(recorder.runs),
        edge_count,
        recorder_merkle_root(recorder),
        tuple(issues),
    )


def verify_trace_dir(
    root: str | Path, *, require_local_files: bool = False
) -> AuditReport:
    from .recorder import TraceRecorder

    root = Path(root)
    if not root.is_dir() or not (root / "events.jsonl").is_file():
        return AuditReport(
            False,
            0,
            0,
            0,
            issues=(
                AuditIssue("error", "trace.missing", "Trace journal is unavailable"),
            ),
        )
    try:
        return verify_recorder(
            TraceRecorder(root), require_local_files=require_local_files
        )
    except (ValueError, TypeError, KeyError, OSError) as exc:
        return AuditReport(
            False, 0, 0, 0, issues=(AuditIssue("error", "trace.parse", str(exc)),)
        )
