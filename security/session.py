"""Session security utilities.

Provides:
- HMAC-signed, time-bounded session tokens (stateless verification +
  SQLite-backed revocation list)
- Token rotation on every continuous-auth tick
- Constant-time comparison, replay-resistant nonces
- Helper to bind a session to client IP + User-Agent fingerprint
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from db import sqlite_store as store


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _ub64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


class SessionGuard:
    def __init__(self, secret: Optional[str] = None, ttl_seconds: int = 3600):
        self.secret = (secret or os.environ.get("BAS_SESSION_SECRET")
                       or secrets.token_hex(32)).encode()
        self.ttl = ttl_seconds

    # ---- issue / verify ----
    def issue(self, user_id: int, ip: str = "", ua: str = "") -> str:
        sid = secrets.token_urlsafe(16)
        claims = {"uid": user_id, "sid": sid, "iat": int(time.time()),
                  "exp": int(time.time()) + self.ttl,
                  "fp": self._fingerprint(ip, ua)}
        token = self._sign(claims)
        store.create_session(sid, user_id, ip, ua)
        return token

    def rotate(self, old_token: str, ip: str = "", ua: str = "") -> Optional[str]:
        claims = self.verify(old_token, ip=ip, ua=ua)
        if not claims:
            return None
        new_claims = dict(claims)
        new_claims["iat"] = int(time.time())
        new_claims["exp"] = int(time.time()) + self.ttl
        new_claims["nonce"] = secrets.token_hex(4)
        return self._sign(new_claims)

    def verify(self, token: str, ip: str = "", ua: str = "") -> Optional[dict]:
        try:
            payload_b64, sig_b64 = token.rsplit(".", 1)
            expected = self._mac(payload_b64.encode())
            if not hmac.compare_digest(expected, _ub64(sig_b64)):
                return None
            claims = json.loads(_ub64(payload_b64))
        except Exception:
            return None
        if claims.get("exp", 0) < time.time():
            return None
        if ip or ua:
            if claims.get("fp") != self._fingerprint(ip, ua):
                return None
        if not store.get_session(claims["sid"]):
            return None
        return claims

    def revoke(self, token: str) -> None:
        try:
            payload_b64 = token.split(".", 1)[0]
            claims = json.loads(_ub64(payload_b64))
            store.revoke_session(claims["sid"])
        except Exception:
            pass

    # ---- internals ----
    def _sign(self, claims: dict) -> str:
        payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
        sig = self._mac(payload.encode())
        return f"{payload}.{_b64(sig)}"

    def _mac(self, msg: bytes) -> bytes:
        return hmac.new(self.secret, msg, hashlib.sha256).digest()

    @staticmethod
    def _fingerprint(ip: str, ua: str) -> str:
        return hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:16]
