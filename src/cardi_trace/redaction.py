"""Safe metadata redaction for trace boundaries."""
from __future__ import annotations
from typing import Any, Iterable

DEFAULT_SENSITIVE_KEYS=frozenset({"password","passwd","token","secret","api_key","apikey","authorization","private_key","access_token","refresh_token","client_secret","cookie"})

def redact(value: Any, *, sensitive_keys: Iterable[str] = DEFAULT_SENSITIVE_KEYS, replacement: str = "[REDACTED]") -> Any:
    keys={k.lower() for k in sensitive_keys}
    if isinstance(value,dict): return {str(k): replacement if str(k).lower() in keys else redact(v,sensitive_keys=keys,replacement=replacement) for k,v in value.items()}
    if isinstance(value,list): return [redact(v,sensitive_keys=keys,replacement=replacement) for v in value]
    if isinstance(value,tuple): return tuple(redact(v,sensitive_keys=keys,replacement=replacement) for v in value)
    return value
