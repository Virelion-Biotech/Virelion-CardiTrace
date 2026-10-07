"""Filesystem content-addressed artifact store with atomic streaming writes and GC."""

from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from typing import BinaryIO
from .hashing import sha256_bytes, sha256_payload, canonical_json

from functools import wraps
from .storage import ledger_lock


def store_mutation(fn):
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        with ledger_lock(self.root):
            return fn(self, *args, **kwargs)

    return wrapped


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("digest must be a 64-character SHA-256 hex string")
        return self.root / "sha256" / digest[:2] / digest[2:]

    def put_bytes(self, data: bytes) -> str:
        return self.put_stream(__import__("io").BytesIO(data))

    def put_json(self, value) -> str:
        return self.put_bytes(canonical_json(value))

    def put_file(self, source: str | Path) -> str:
        with Path(source).open("rb") as handle:
            return self.put_stream(handle)

    @store_mutation
    def put_stream(self, stream: BinaryIO, chunk_size=1024 * 1024) -> str:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        digest = hashlib.sha256()
        staging = self.root / ".staging"
        staging.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="artifact-", dir=staging)
        try:
            with os.fdopen(fd, "wb") as target:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            value = digest.hexdigest()
            path = self._path(value)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if not self.verify(value):
                    raise ValueError(f"Corrupt existing artifact: {value}")
                os.unlink(temp_name)
            else:
                os.replace(temp_name, path)
            return value
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    @store_mutation
    def put_directory(self, source: str | Path) -> str:
        """Store all files and return a content hash of the directory manifest."""
        base = Path(source)
        if not base.is_dir():
            raise NotADirectoryError(base)
        entries = []
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            digest = self.put_file(path)
            entries.append(
                {
                    "path": path.relative_to(base).as_posix(),
                    "digest": digest,
                    "size_bytes": self._path(digest).stat().st_size,
                }
            )
        return self.put_json({"schema": "carditrace.directory.v1", "entries": entries})

    def get_bytes(self, digest: str) -> bytes:
        data = self._path(digest).read_bytes()
        if sha256_bytes(data) != digest:
            raise ValueError(f"Artifact content hash mismatch: {digest}")
        return data

    def get_json(self, digest: str):
        return json.loads(self.get_bytes(digest).decode("utf-8"))

    def open(self, digest: str, mode="rb"):
        if mode not in {"r", "rb"}:
            raise ValueError("Content-addressed artifacts are read-only")
        if not self.verify(digest):
            raise ValueError(f"Artifact content hash mismatch: {digest}")
        return self._path(digest).open(mode)

    def exists(self, digest: str) -> bool:
        return self._path(digest).is_file()

    def verify(self, digest: str) -> bool:
        from .hashing import sha256_file

        return self.exists(digest) and sha256_file(self._path(digest)) == digest

    def list_digests(self):
        root = self.root / "sha256"
        if not root.exists():
            return ()
        return tuple(
            sorted(
                p.parent.name + p.name
                for p in root.glob("*/" + "*")
                if p.is_file()
                and len(p.parent.name + p.name) == 64
                and all(c in "0123456789abcdef" for c in p.parent.name + p.name)
            )
        )

    @store_mutation
    def gc(
        self, keep: set[str] | list[str] | tuple[str, ...], *, dry_run=False
    ) -> list[str]:
        """Delete unreferenced CAS blobs; only exact SHA-256 digests are eligible."""
        keep = set(keep)
        removed = []
        # Mark directory-manifest children before deleting any blobs.
        pending = list(keep)
        while pending:
            digest = pending.pop()
            self._path(digest)
            if not self.exists(digest):
                continue
            data = self.get_bytes(digest)
            try:
                manifest = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                continue
            if (
                isinstance(manifest, dict)
                and manifest.get("schema") == "carditrace.directory.v1"
            ):
                for entry in manifest["entries"]:
                    child = entry["digest"]
                    self._path(child)
                    if child not in keep:
                        keep.add(child)
                        pending.append(child)
        for digest in self.list_digests():
            if digest in keep:
                continue
            path = self._path(digest)
            if not dry_run:
                path.unlink(missing_ok=True)
            removed.append(digest)
        return removed
