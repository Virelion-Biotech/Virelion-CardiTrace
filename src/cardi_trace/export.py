"""Portable trace bundle export/import with schema and commitment metadata."""
from __future__ import annotations

import json
from pathlib import Path
from .audit import verify_recorder
from .hashing import sha256_payload
from .schema import SCHEMA_VERSION, validate_envelope
from .merkle import recorder_merkle_root


def build_bundle(recorder) -> dict:
    audit = verify_recorder(recorder)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "events": [e.to_dict() for e in recorder.events],
        "runs": [r.to_dict() for r in recorder.runs],
        "artifacts": [a.to_dict() for a in recorder.artifacts],
        "lineage": [e.to_dict() for e in getattr(recorder, "lineage", ())],
        "audit": audit.to_dict(),
        "commitment": {"algorithm": "merkle-sha256-v1", "root": recorder_merkle_root(recorder)},
    }
    payload["bundle_digest"] = sha256_payload(payload)
    return payload


def export_bundle(recorder, path: str | Path) -> Path:
    payload = build_bundle(recorder)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    return target


def load_bundle(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    issues = validate_envelope(payload)
    if issues:
        raise ValueError("Invalid trace bundle: " + ", ".join(issues))
    claimed = payload.get("bundle_digest")
    body = dict(payload)
    body.pop("bundle_digest", None)
    if claimed != sha256_payload(body):
        raise ValueError("Bundle digest mismatch")
    return payload


def export_jsonl(recorder, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for event in recorder.events:
            handle.write(json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
    return target
