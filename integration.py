"""Integration glue: wires the enhanced modules into the original app.py
without altering the existing JSON-backed flow.

Call `init_enhancements(app)` once after constructing the Flask app.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from typing import Optional

from db import sqlite_store as store
from telemetry.engine import telemetry_bp
from security.session import SessionGuard


def _ensure_user(email: str, pin_hash: str) -> int:
    salt = hashlib.sha256(email.encode()).hexdigest()[:16]
    return store.upsert_user(email, pin_hash, salt)


def init_enhancements(app):
    # 1. SQLite
    store.init_db()

    # 2. Telemetry blueprint
    if "telemetry_v2" not in app.blueprints:
        app.register_blueprint(telemetry_bp, url_prefix="/api/v2")

    # 3. Session guard
    app.config["SESSION_GUARD"] = SessionGuard(
        secret=os.environ.get("BAS_SESSION_SECRET", app.secret_key)
    )

    # 4. ML runtime (lazy load)
    from ml import runtime as ml_runtime
    ml_runtime.warm_start()
    app.config["ML_RUNTIME"] = ml_runtime

    # 5. dual_write: mirror enrollment + auth results into SQLite
    def dual_write(email: str, pin_hash: str, features: dict, result: dict,
                   session_id: Optional[str] = None) -> int:
        try:
            uid = _ensure_user(email, pin_hash)
            store.mark_enrolled(uid)
            # flatten features into telemetry rows per channel
            for channel, payload in (features or {}).items():
                if isinstance(payload, dict) and payload.get("samples", 0):
                    store.insert_telemetry(session_id, uid, channel, payload)
            # save profile snapshot (Welford-compatible structure: just store raw)
            flat = {}
            for ch, p in (features or {}).items():
                if isinstance(p, dict):
                    for k, v in p.items():
                        if isinstance(v, (int, float)):
                            flat[f"{ch}_{k}"] = float(v)
            from ml.anomaly import AnomalyDetector
            det = AnomalyDetector.load_for_user(uid)
            det.update_profile(flat)
            # record score
            store.record_score(
                session_id, uid,
                float(result.get("confidence", 0.0)),
                result.get("status", "unknown"),
                result.get("scores", {}),
            )
            return uid
        except Exception as e:
            app.logger.warning("dual_write failed: %s", e)
            return -1

    app.config["DUAL_WRITE"] = dual_write
