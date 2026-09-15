"""Optional shared-secret authentication for federated CardiTrace envelopes."""
from __future__ import annotations
import hashlib, hmac
from typing import Any
from .hashing import canonical_json

def sign_payload(payload: dict[str, Any], secret: bytes) -> str:
    """Return an HMAC-SHA256 MAC. This authenticates integrity to secret holders; it is not a public-key signature."""
    if not secret: raise ValueError("secret must not be empty")
    return hmac.new(secret, canonical_json(payload), hashlib.sha256).hexdigest()

def verify_signature(payload: dict[str, Any], signature: str, secret: bytes) -> bool:
    if not secret or not signature: return False
    return hmac.compare_digest(sign_payload(payload, secret), signature)

def signed_copy(payload: dict[str, Any], secret: bytes) -> dict[str, Any]:
    body = dict(payload); body["signature_algorithm"] = "hmac-sha256"; body["signature"] = sign_payload(body, secret); return body
