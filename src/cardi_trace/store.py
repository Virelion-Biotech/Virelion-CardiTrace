"""Filesystem content-addressed artifact store with atomic streaming writes and GC."""
from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from typing import BinaryIO
from .hashing import sha256_bytes, sha256_payload

class ArtifactStore:
    def __init__(self, root: str|Path) -> None:
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def _path(self,digest: str)->Path:
        if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest.lower()): raise ValueError("digest must be a 64-character SHA-256 hex string")
        return self.root/"sha256"/digest[:2]/digest[2:]
    def put_bytes(self,data: bytes)->str: return self.put_stream(__import__("io").BytesIO(data))
    def put_json(self,value)->str: return self.put_bytes(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode("utf-8"))
    def put_file(self,source: str|Path)->str:
        with Path(source).open("rb") as handle: return self.put_stream(handle)
    def put_stream(self,stream: BinaryIO,chunk_size=1024*1024)->str:
        if chunk_size<=0: raise ValueError("chunk_size must be positive")
        digest=hashlib.sha256(); staging=self.root/".staging"; staging.mkdir(parents=True,exist_ok=True); fd,temp_name=tempfile.mkstemp(prefix="artifact-",dir=staging)
        try:
            with os.fdopen(fd,"wb") as target:
                while True:
                    chunk=stream.read(chunk_size)
                    if not chunk: break
                    digest.update(chunk); target.write(chunk)
                target.flush(); os.fsync(target.fileno())
            value=digest.hexdigest(); path=self._path(value); path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists(): os.unlink(temp_name)
            else: os.replace(temp_name,path)
            return value
        except Exception:
            try: os.unlink(temp_name)
            except FileNotFoundError: pass
            raise
    def put_directory(self,source: str|Path)->str:
        """Store all files and return a content hash of the directory manifest."""
        base=Path(source)
        if not base.is_dir(): raise NotADirectoryError(base)
        entries=[]
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            digest=self.put_file(path); entries.append({"path":path.relative_to(base).as_posix(),"digest":digest,"size_bytes":path.stat().st_size})
        return self.put_json({"schema":"carditrace.directory.v1","entries":entries})
    def get_bytes(self,digest: str)->bytes: return self._path(digest).read_bytes()
    def get_json(self,digest: str): return json.loads(self.get_bytes(digest).decode("utf-8"))
    def open(self,digest: str,mode="rb"): return self._path(digest).open(mode)
    def exists(self,digest: str)->bool: return self._path(digest).is_file()
    def verify(self,digest: str)->bool: return self.exists(digest) and sha256_bytes(self.get_bytes(digest))==digest
    def list_digests(self):
        root=self.root/"sha256"
        if not root.exists(): return ()
        return tuple(sorted(p.parent.name+p.name for p in root.glob("*/"+"*" ) if p.is_file()))
    def gc(self,keep: set[str]|list[str]|tuple[str,...],*,dry_run=False)->list[str]:
        """Delete unreferenced CAS blobs; only exact SHA-256 digests are eligible."""
        keep=set(keep); removed=[]
        for digest in self.list_digests():
            if digest in keep: continue
            path=self._path(digest)
            if not dry_run: path.unlink(missing_ok=True)
            removed.append(digest)
        return removed
