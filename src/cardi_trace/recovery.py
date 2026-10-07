"""Explicit, hash-checked recovery of derived snapshots from the journal."""

from pathlib import Path
from .journal import replay_events
from .recorder import TraceRecorder
from .storage import ledger_lock


def recover_from_events(root: str | Path, *, overwrite: bool = False) -> TraceRecorder:
    root = Path(root)
    if not (root / "events.jsonl").is_file():
        raise FileNotFoundError(root / "events.jsonl")
    with ledger_lock(root):
        # Avoid loading potentially corrupt snapshots until the journal is checked.
        probe = object.__new__(TraceRecorder)
        probe.events_path = root / "events.jsonl"
        events = probe._load_events()
        runs, artifacts, edges = replay_events(events)
        probe.root = root
        probe._events, probe._runs, probe._artifacts, probe._edges = (
            events,
            runs,
            artifacts,
            edges,
        )
        from .audit import verify_recorder

        report = verify_recorder(probe, verify_local_files=False)
        if not report.valid:
            raise ValueError(
                "Journal recovery failed: " + ", ".join(i.code for i in report.issues)
            )
        paths = [
            root / name for name in ("runs.json", "artifacts.json", "lineage.json")
        ]
        # overwrite permits replacing malformed snapshots, never an invalid journal.
        if not overwrite:
            import json

            for path in paths:
                if path.exists():
                    json.loads(path.read_text(encoding="utf-8"))
        probe.runs_path, probe.artifacts_path, probe.edges_path = paths
        probe._persist()
    return TraceRecorder(root)
