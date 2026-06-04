"""
SQLite storage layer (FINAL FIXED - MATCHED WITH API USAGE)
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Optional

# =========================================================
# CONFIG
# =========================================================

HERE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.environ.get("BAS_SQLITE_PATH", os.path.join(HERE, "bas.db"))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")

_lock = threading.RLock()

# =========================================================
# CONNECTION
# =========================================================

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

# =========================================================
# INIT DB
# =========================================================

def init_db() -> None:
    with get_conn() as conn:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

# =========================================================
# USERS
# =========================================================

def upsert_user(username: str, pin_hash: str, salt: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (username, pin_hash, salt)
            VALUES (?, ?, ?)
            ON CONFLICT(username)
            DO UPDATE SET pin_hash=excluded.pin_hash, salt=excluded.salt
            RETURNING id
            """,
            (username, pin_hash, salt),
        )
        return int(cur.fetchone()[0])


def get_user(username: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()


def mark_enrolled(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET enrolled = 1 WHERE id = ?",
            (user_id,)
        )

# =========================================================
# SESSIONS
# =========================================================

def create_session(session_id: str,
                   user_id: int,
                   ip: str = "",
                   user_agent: str = "") -> str:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                id, user_id, issued_at, last_seen,
                ip, user_agent, revoked, trust_score
            )
            VALUES (?, ?, datetime('now'), datetime('now'), ?, ?, 0, 100.0)
            """,
            (session_id, user_id, ip, user_agent),
        )
        return session_id


def touch_session(session_id: str, trust_score: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET last_seen = datetime('now'),
                trust_score = ?
            WHERE id = ? AND revoked = 0
            """,
            (trust_score, session_id),
        )


def revoke_session(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE id = ?",
            (session_id,)
        )


def get_session(session_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND revoked = 0",
            (session_id,)
        ).fetchone()

# =========================================================
# TELEMETRY
# =========================================================

def insert_telemetry(session_id: Optional[str],
                     user_id: Optional[int],
                     channel: str,
                     payload: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO telemetry_events (session_id, user_id, ts, channel, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, user_id, time.time() * 1000, channel, json.dumps(payload)),
        )

# =========================================================
# PROFILES
# =========================================================

def load_profile(user_id: int) -> dict:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT feature_json, samples FROM behavior_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    if not r:
        return {"features": {}, "samples": 0}

    return {
        "features": json.loads(r["feature_json"]),
        "samples": int(r["samples"])
    }


def save_profile(user_id: int, features: dict, samples: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO behavior_profiles (user_id, feature_json, samples)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                feature_json = excluded.feature_json,
                samples = excluded.samples,
                updated_at = datetime('now')
            """,
            (user_id, json.dumps(features), samples),
        )

# =========================================================
# AUTH SCORES
# =========================================================

def record_score(session_id: Optional[str],
                 user_id: Optional[int],
                 score: float,
                 risk: str,
                 breakdown: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO auth_scores (session_id, user_id, score, risk, breakdown)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, user_id, float(score), risk, json.dumps(breakdown)),
        )

# =========================================================
# ANOMALIES (🔥 FIXED HERE)
# =========================================================

def record_anomaly(user_id: Optional[int],
                   session_id: Optional[str],
                   severity: str,
                   feature: str,
                   z: float,
                   detail: str = "",
                   score: Optional[float] = None) -> None:
    """
    FIX:
    - Added `score` so your API call doesn't crash
    - Keeps backward compatibility
    """
    payload_detail = detail

    # If score exists, attach it into detail for traceability
    if score is not None:
        payload_detail = json.dumps({
            "detail": detail,
            "score": score
        })

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO anomalies (
                user_id, session_id, severity, feature, z_score, detail
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                session_id,
                severity,
                feature,
                float(z),
                payload_detail
            ),
        )

# =========================================================
# DEBUG
# =========================================================

if __name__ == "__main__":
    init_db()
    print(f"DB initialized at {DB_FILE}")