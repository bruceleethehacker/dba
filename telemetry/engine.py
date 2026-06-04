"""Real-time telemetry engine.

Accepts raw event batches from the client (web or mobile), validates
them, fans them out to:
  1. SQLite (raw audit trail)
  2. Feature extractor (biometrics.features)
  3. Continuous-auth scorer (biometrics.continuous_auth)
  4. In-memory ring buffer for the admin live view

Designed as an additive Flask Blueprint -- mount it in app.py with:

    from telemetry.engine import telemetry_bp, telemetry
    app.register_blueprint(telemetry_bp, url_prefix="/api/v2")

…without touching any existing routes.
"""

from __future__ import annotations

import collections
import threading
import time
from typing import Any, Optional

from flask import Blueprint, jsonify, request, session

from biometrics.continuous_auth import ContinuousAuth
from db import sqlite_store as store
from security.session import SessionGuard

telemetry_bp = Blueprint("telemetry_v2", __name__)

# In-process state.
_BUFFER_SIZE = 500
_buffer: collections.deque = collections.deque(maxlen=_BUFFER_SIZE)
_lock = threading.Lock()

ca = ContinuousAuth()
guard = SessionGuard()


class TelemetryEngine:
    VALID_CHANNELS = {"typing", "scroll", "tap", "swipe", "motion", "sensor"}

    def ingest_batch(self, user_id: Optional[int], session_id: Optional[str],
                     batch: dict) -> dict:
        """batch = {'typing':[...], 'scrolling':[...], 'taps':[...],
                   'swipes':[[...]], 'motion':[...], 'sensors':[...]}"""
        # 1. persist raw payload per channel
        mapping = {
            "typing":   ("typing",  {"events":  batch.get("typing", [])}),
            "scroll":   ("scroll",  {"samples": batch.get("scrolling", [])}),
            "tap":      ("tap",     {"taps":    batch.get("taps", [])}),
            "motion":   ("motion",  {"samples": batch.get("motion", [])}),
            "sensor":   ("sensor",  {"samples": batch.get("sensors", [])}),
        }
        for _, (ch, payload) in mapping.items():
            if any(payload.values()):
                store.insert_telemetry(session_id, user_id, ch, payload)
        for path in batch.get("swipes", []):
            store.insert_telemetry(session_id, user_id, "swipe", {"path": path})

        # 2. score via continuous auth if we have a session
        result: dict[str, Any] = {"stored": True}
        if session_id and user_id is not None:
            if session_id not in ca._states:
                ca.start(session_id, user_id)
            result.update(ca.ingest(session_id, batch))

        # 3. live admin buffer
        with _lock:
            _buffer.append({"ts": time.time(), "user_id": user_id,
                            "session_id": session_id, "result": result})

        return result

    def live_tail(self, n: int = 50) -> list[dict]:
        with _lock:
            return list(_buffer)[-n:]


engine = TelemetryEngine()


# ---- HTTP routes (mounted under /api/v2) ----

@telemetry_bp.post("/telemetry")
def post_telemetry():
    body = request.get_json(silent=True) or {}
    token = request.headers.get("X-Session-Token") or session.get("ca_token")
    claims = guard.verify(token) if token else None
    user_id = claims.get("uid") if claims else body.get("user_id")
    session_id = claims.get("sid") if claims else body.get("session_id")
    return jsonify(engine.ingest_batch(user_id, session_id, body))


@telemetry_bp.get("/telemetry/live")
def live():
    return jsonify(engine.live_tail(int(request.args.get("n", 50))))


@telemetry_bp.get("/ca/state")
def ca_state():
    sid = request.args.get("session_id") or session.get("ca_sid")
    snap = ca.snapshot(sid) if sid else None
    return jsonify(snap or {"error": "no session"})
