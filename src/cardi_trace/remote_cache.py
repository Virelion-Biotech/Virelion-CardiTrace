"""Portable cache-key and local cache primitives for reproducible trace reuse."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Callable
from .hashing import sha256_payload
from .storage import atomic_json


class Cache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def key(self, *, code: str, inputs=(), parameters=None, environment=None) -> str:
        return sha256_payload(
            {
                "code": code,
                "inputs": sorted(inputs),
                "parameters": parameters or {},
                "environment": environment or {},
            }
        )

    def path_for(self, key: str) -> Path:
        if (
            not isinstance(key, str)
            or len(key) != 64
            or any(c not in "0123456789abcdef" for c in key)
        ):
            raise ValueError("Cache key must be a lowercase SHA-256 digest")
        return self.root / key[:2] / key[2:] / "result.json"

    def get(self, key: str):
        p = self.path_for(key)
        if not p.exists():
            return None
        entry = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or entry.get("schema") != "carditrace.cache.v1":
            raise ValueError("Unverified legacy cache entry; remove it and recompute")
        if entry.get("cache_key") != key or entry.get("value_digest") != sha256_payload(
            entry.get("value")
        ):
            raise ValueError("Cache identity or content hash mismatch")
        return entry["value"]

    def put(self, key: str, value: Any):
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(
            p,
            {
                "schema": "carditrace.cache.v1",
                "cache_key": key,
                "value": value,
                "value_digest": sha256_payload(value),
            },
        )
        return p

    def get_or_compute(self, key: str, compute: Callable[[], Any]):
        if self.path_for(key).exists():
            return self.get(key), True
        value = compute()
        self.put(key, value)
        return value, False
