"""Portable cache-key and local cache primitives for reproducible trace reuse."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Callable
from .hashing import sha256_payload

class Cache:
    def __init__(self, root: str | Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def key(self, *, code: str, inputs=(), parameters=None, environment=None) -> str:
        return sha256_payload({"code": code, "inputs": sorted(inputs), "parameters": parameters or {}, "environment": environment or {}})
    def path_for(self, key: str) -> Path:
        return self.root / key[:2] / key[2:] / "result.json"
    def get(self, key: str):
        p = self.path_for(key)
        if not p.exists(): return None
        return json.loads(p.read_text(encoding="utf-8"))
    def put(self, key: str, value: Any):
        p = self.path_for(key); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, sort_keys=True), encoding="utf-8"); return p
    def get_or_compute(self, key: str, compute: Callable[[], Any]):
        cached = self.get(key)
        if cached is not None: return cached, True
        value = compute(); self.put(key, value); return value, False
