"""Dependency-free process/resource telemetry for provenance activities."""
from __future__ import annotations
import os, time
from pathlib import Path

def snapshot() -> dict:
    result = {"timestamp": time.time(), "pid": os.getpid()}
    try:
        result["cpu_time_seconds"] = sum(os.times()[:4])
    except Exception:
        pass
    try:
        stat = Path(f"/proc/{os.getpid()}/status").read_text(encoding="utf-8", errors="ignore")
        for line in stat.splitlines():
            if line.startswith("VmRSS:"):
                result["rss_bytes"] = int(line.split()[1]) * 1024
                break
    except Exception:
        pass
    try:
        usage = os.getloadavg()
        result["load_average"] = list(usage)
    except (AttributeError, OSError):
        pass
    return result

def delta(before: dict, after: dict) -> dict:
    out = {"elapsed_seconds": max(0.0, after.get("timestamp", 0) - before.get("timestamp", 0))}
    for key in ("cpu_time_seconds", "rss_bytes"):
        if key in before and key in after:
            out[key] = after[key] - before[key]
    return out

def capture_environment() -> dict:
    """Return host/runtime telemetry safe to attach to a trace metadata field."""
    return {"resource_capture": "carditrace.resources.v1", "initial": snapshot()}
