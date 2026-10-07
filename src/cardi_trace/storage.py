"""Atomic snapshots and cooperative local-process locking."""

from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import threading

_locks = {}
_guard = threading.Lock()
_active = threading.local()


@contextmanager
def ledger_lock(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with _guard:
        lock = _locks.setdefault(str(root), threading.RLock())
    with lock:
        active = getattr(_active, "roots", set())
        if str(root) in active:
            yield
            return
        _active.roots = active | {str(root)}
        try:
            with (root / ".write.lock").open("a+b") as handle:
                with _platform_lock(handle):
                    yield
        finally:
            _active.roots = active


@contextmanager
def _platform_lock(handle):
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        if os.name == "nt":
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, sort_keys=True, indent=2, allow_nan=False)
    fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            fd_dir = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd_dir)
            finally:
                os.close(fd_dir)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
