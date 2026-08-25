"""Multi-layer verification for CardiTrace traces."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from .hashing import digest_event
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


def verify_recorder(recorder) -> AuditReport:
    issues: list[AuditIssue] = []
    previous = None
    for event in recorder.events:
        if event.previous_hash != previous:
            issues.append(AuditIssue("error", "event.chain", "Previous hash does not match chain", event.event_id))
        body = event.to_dict()
        body["event_hash"] = ""
        expected = digest_event(body)
        if event.event_hash != expected:
            issues.append(AuditIssue("error", "event.hash", "Event hash mismatch", event.event_id))
        previous = event.event_hash

    artifact_ids = {a.artifact_id for a in recorder.artifacts}
    for run in recorder.runs:
        for aid in (*run.input_artifacts, *run.output_artifacts):
            if aid not in artifact_ids:
                issues.append(AuditIssue("error", "run.artifact", f"Run references unknown artifact {aid}", run.run_id))
        if str(run.status) != "running" and run.finished_at is None:
            issues.append(AuditIssue("error", "run.finish", "Terminal run has no finish timestamp", run.run_id))
        if not run.metadata.get("execution_fingerprint"):
            issues.append(AuditIssue("warning", "run.fingerprint", "Run has no execution fingerprint", run.run_id))

    edge_count = 0
    if hasattr(recorder, "lineage"):
        edge_count = len(recorder.lineage)
        from .lineage import LineageGraph
        graph = LineageGraph()
        for edge in recorder.lineage:
            if edge.source_id not in artifact_ids or edge.target_id not in artifact_ids:
                issues.append(AuditIssue("error", "lineage.artifact", "Lineage references unknown artifact", edge.source_id))
                continue
            try:
                graph.add_edge(edge.source_id, edge.target_id, edge.relation, edge.run_id, edge.metadata)
            except ValueError as exc:
                issues.append(AuditIssue("error", "lineage.cycle", str(exc), edge.target_id))

    return AuditReport(
        not any(i.severity == "error" for i in issues),
        len(recorder.events),
        len(recorder.artifacts),
        len(recorder.runs),
        edge_count,
        recorder_merkle_root(recorder),
        tuple(issues),
    )


def verify_trace_dir(root: str | Path) -> AuditReport:
    from .recorder import TraceRecorder
    return verify_recorder(TraceRecorder(root))
