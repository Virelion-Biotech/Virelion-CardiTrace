"""Deterministic content identity helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): canonicalize(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (list, tuple)):
        return [canonicalize(v) for v in value]
    if isinstance(value, set):
        return sorted((canonicalize(v) for v in value), key=lambda x: json.dumps(x, sort_keys=True, default=str))
    if hasattr(value, "value") and not isinstance(value, (str, bytes, bytearray)):
        return canonicalize(value.value)
    if hasattr(value, "to_dict"):
        return canonicalize(value.to_dict())
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_payload(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def digest_event(event_without_hash: dict[str, Any]) -> str:
    return sha256_payload(event_without_hash)
