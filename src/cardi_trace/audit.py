"""Audit verification for CardiTrace traces."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
from .hashing import digest_event, sha256_file
from .models import AuditIssue


@dataclass(frozen=True)
class AuditReport:
    valid: bool
    events_checked: int
    artifacts_checked: int
    runs_checked: int
    issues: tuple[AuditIssue, ...]

    def to_dict(self) -> dict:
        return {"valid": self.valid, "events_checked": self.events_checked, "artifacts_checked": self.artifacts_checked, "runs_checked": self.runs_checked, "issues": [i.to_dict() for i in self.issues]}


def verify_recorder(recorder) -> AuditReport:
    issues: list[AuditIssue] = []
    previous = None
    for event in recorder.events:
        if event.previous_hash != previous:
            issues.append(AuditIssue("error", "event.chain", "Previous hash does not match chain", event.event_id))
        body = event.to_dict(); body["event_hash"] = ""
        expected = digest_event(body)
        if event.event_hash != expected:
            issues.append(AuditIssue("error", "event.hash", "Event hash mismatch", event.event_id))
        previous = event.event_hash
    for run in recorder.runs:
        for aid in (*run.input_artifacts, *run.output_artifacts):
            if aid not in {a.artifact_id for a in recorder.artifacts}:
                issues.append(AuditIssue("error", "run.artifact", f"Run references unknown artifact {aid}", run.run_id))
        if run.status != "running" and run.finished_at is None:
            issues.append(AuditIssue("error", "run.finish", "Terminal run has no finish timestamp", run.run_id))
    return AuditReport(not any(i.severity == "error" for i in issues), len(recorder.events), len(recorder.artifacts), len(recorder.runs), tuple(issues))


def verify_trace_dir(root: str | Path) -> AuditReport:
    from .recorder import TraceRecorder
    return verify_recorder(TraceRecorder(root))
