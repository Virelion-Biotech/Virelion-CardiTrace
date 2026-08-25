"""Portable trace bundle export/import."""
from __future__ import annotations
import json
from pathlib import Path
from .audit import verify_recorder
from .hashing import sha256_payload


def export_bundle(recorder, path: str | Path) -> Path:
    audit = verify_recorder(recorder)
    events = [e.to_dict() for e in recorder.events]
    runs = [r.to_dict() for r in recorder.runs]
    artifacts = [a.to_dict() for a in recorder.artifacts]
    payload = {"schema_version": "1.0", "events": events, "runs": runs, "artifacts": artifacts, "audit": audit.to_dict()}
    payload["bundle_digest"] = sha256_payload(payload)
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    return target


def export_jsonl(recorder, path: str | Path) -> Path:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for event in recorder.events:
            handle.write(json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
    return target
