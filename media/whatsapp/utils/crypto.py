"""HMAC signing utilities for webhook payloads."""
from __future__ import annotations

import hashlib
import hmac as _hmac


def hmac_sign(secret: str, payload: bytes | str) -> str:
    """Return `sha256=<hex>` signature for the given payload."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    sig = _hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def verify_hmac(secret: str, payload: bytes | str, signature: str) -> bool:
    """Constant-time HMAC verification. Returns True if signature matches."""
    if not signature or not secret:
        return False
    expected = hmac_sign(secret, payload)
    return _hmac.compare_digest(expected, signature)
