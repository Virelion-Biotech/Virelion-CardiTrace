"""Deterministic execution identity and environment fingerprints."""
from __future__ import annotations
import hashlib
import importlib.metadata
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from .hashing import canonical_json, sha256_file, sha256_payload

@dataclass(frozen=True)
class ExecutionFingerprint:
    digest: str
    code_identity: str
    environment_identity: str
    input_identity: str
    parameter_identity: str
    seed_identity: str
    algorithm: str = "carditrace-fingerprint-v1"
    def to_dict(self):
        return {"digest": self.digest, "code_identity": self.code_identity, "environment_identity": self.environment_identity, "input_identity": self.input_identity, "parameter_identity": self.parameter_identity, "seed_identity": self.seed_identity, "algorithm": self.algorithm}

def git_identity(path=None):
    cwd = str(Path(path).resolve()) if path else os.getcwd()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = subprocess.call(["git", "diff", "--quiet"], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0
        return f"git:{commit}{'+dirty' if dirty else ''}"
    except (OSError, subprocess.SubprocessError):
        return "git:unavailable"

def code_fingerprint(paths: Iterable[str | Path]) -> str:
    entries=[]
    for raw in paths:
        p=Path(raw)
        if p.is_file(): entries.append((p.as_posix(), sha256_file(p)))
        elif p.is_dir():
            for child in sorted(x for x in p.rglob("*") if x.is_file()): entries.append((child.as_posix(), sha256_file(child)))
    return sha256_payload(entries)

def _distribution_version(name):
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return None

def environment_fingerprint(*, packages=(), extra=None):
    selected={"python":sys.version,"implementation":platform.python_implementation(),"platform":platform.platform(),"machine":platform.machine(),"packages":{n:_distribution_version(n) for n in sorted(set(packages))},"extra":extra or {}}
    return sha256_payload(selected)

def execution_fingerprint(*, code_identity=None, environment_identity=None, input_artifacts=(), parameters=None, seeds=None):
    code=code_identity or git_identity(); env=environment_identity or environment_fingerprint(); inputs=sha256_payload(sorted(input_artifacts)); params=sha256_payload(parameters if parameters is not None else {}); seed_id=sha256_payload(seeds if seeds is not None else {})
    digest=hashlib.sha256(canonical_json({"code":code,"env":env,"inputs":inputs,"parameters":params,"seeds":seed_id})).hexdigest()
    return ExecutionFingerprint(digest,code,env,inputs,params,seed_id)
