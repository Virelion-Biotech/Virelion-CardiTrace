"""Merkle commitments over trace events for efficient external anchoring."""
from __future__ import annotations

from .hashing import sha256_payload


def merkle_root(values: list[str] | tuple[str, ...]) -> str:
    if not values:
        return sha256_payload([])
    level = list(values)
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            nxt.append(sha256_payload({"left": left, "right": right}))
        level = nxt
    return level[0]


def recorder_merkle_root(recorder) -> str:
    return merkle_root([event.event_hash for event in recorder.events])
