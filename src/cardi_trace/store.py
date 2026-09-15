"""Filesystem content-addressed artifact store with atomic streaming writes."""
from __future__ import annotations
import hashlib, os, tempfile
from pathlib import Path
from typing import BinaryIO
from .hashing import sha256_bytes

class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()): raise ValueError("digest must be a 64-character SHA-256 hex string")
        return self.root / "sha256" / digest[:2] / digest[2:]
    def put_bytes(self, data: bytes) -> str:
        return self.put_stream(__import__("io").BytesIO(data))
    def put_file(self, source: str | Path) -> str:
        with Path(source).open("rb") as handle: return self.put_stream(handle)
    def put_stream(self, stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
        if chunk_size <= 0: raise ValueError("chunk_size must be positive")
        digest = hashlib.sha256()
        staging_dir = self.root / ".staging"; staging_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="artifact-", dir=staging_dir)
        try:
            with os.fdopen(fd, "wb") as target:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk: break
                    digest.update(chunk); target.write(chunk)
                target.flush(); os.fsync(target.fileno())
            value = digest.hexdigest(); path = self._path(value); path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists(): os.unlink(temp_name)
            else: os.replace(temp_name, path)
            return value
        except Exception:
            try: os.unlink(temp_name)
            except FileNotFoundError: pass
            raise
    def get_bytes(self, digest: str) -> bytes: return self._path(digest).read_bytes()
    def open(self, digest: str, mode: str = "rb"):
        return self._path(digest).open(mode)
    def exists(self, digest: str) -> bool: return self._path(digest).is_file()
    def verify(self, digest: str) -> bool: return self.exists(digest) and sha256_bytes(self.get_bytes(digest)) == digest
