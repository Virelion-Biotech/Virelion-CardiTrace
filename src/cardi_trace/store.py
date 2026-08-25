"""Filesystem content-addressed artifact store."""
from __future__ import annotations
from pathlib import Path
from typing import BinaryIO
from .hashing import sha256_bytes


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> Path:
        return self.root / "sha256" / digest[:2] / digest[2:]

    def put_bytes(self, data: bytes) -> str:
        digest = sha256_bytes(data)
        path = self._path(digest); path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists(): path.write_bytes(data)
        return digest

    def put_file(self, source: str | Path) -> str:
        with Path(source).open("rb") as handle: return self.put_stream(handle)

    def put_stream(self, stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
        import hashlib
        digest = hashlib.sha256(); chunks=[]
        while chunk := stream.read(chunk_size): digest.update(chunk); chunks.append(chunk)
        value=digest.hexdigest(); path=self._path(value); path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists(): path.write_bytes(b"".join(chunks))
        return value

    def get_bytes(self, digest: str) -> bytes:
        return self._path(digest).read_bytes()

    def exists(self, digest: str) -> bool: return self._path(digest).is_file()

    def verify(self, digest: str) -> bool:
        return self.exists(digest) and sha256_bytes(self.get_bytes(digest)) == digest
