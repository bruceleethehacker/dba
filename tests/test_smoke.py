"""Smoke tests for the additive modules. Run with: python -m pytest tests/"""

import os
import sys
import tempfile

os.environ["BAS_SQLITE_PATH"] = os.path.join(tempfile.gettempdir(), "bas-test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import sqlite_store as store                  # noqa: E402
from biometrics.features import extract_all, to_vector  # noqa: E402
from ml.anomaly import AnomalyDetector                # noqa: E402
from security.session import SessionGuard             # noqa: E402


def setup_module(_):
    if os.path.exists(store.DB_FILE):
        os.remove(store.DB_FILE)
    store.init_db()


def test_user_crud_and_session_token():
    uid = store.upsert_user("alice", "h", "s")
    assert uid > 0
    guard = SessionGuard(secret="testsecret")
    token = guard.issue(uid, ip="1.1.1.1", ua="ua")
    claims = guard.verify(token, ip="1.1.1.1", ua="ua")
    assert claims and claims["uid"] == uid
    # wrong fingerprint rejected
    assert guard.verify(token, ip="2.2.2.2", ua="ua") is None
    guard.revoke(token)
    assert guard.verify(token, ip="1.1.1.1", ua="ua") is None


def test_feature_extraction_and_anomaly():
    batch = {
        "typing": [
            {"type": "down", "key": "a", "t": 0},
            {"type": "up",   "key": "a", "t": 80},
            {"type": "down", "key": "b", "t": 120},
            {"type": "up",   "key": "b", "t": 200},
        ],
        "scrolling": [{"t": 0, "dy": 5, "vy": 50}, {"t": 50, "dy": -3, "vy": -60}],
        "taps": [{"t": 0, "x": 10, "y": 10, "pressure": 0.5},
                 {"t": 200, "x": 20, "y": 10, "pressure": 0.4}],
        "swipes": [[{"t": 0, "x": 0, "y": 0}, {"t": 50, "x": 30, "y": 5},
                    {"t": 100, "x": 60, "y": 8}]],
        "motion": [{"t": i, "ax": 0.1 * i, "ay": 0, "az": 9.8,
                    "gx": 0, "gy": 0, "gz": 0} for i in range(10)],
    }
    feats = extract_all(batch)
    assert "typing_speed_cps" in feats
    assert len(to_vector(feats)) == len(feats)

    uid = store.upsert_user("bob", "h", "s")
    det = AnomalyDetector.load_for_user(uid)
    for _ in range(10):
        det.update_profile(feats)
    score, breakdown = det.score(feats)
    assert 0.0 <= score <= 100.0
    assert set(breakdown.keys()) == {"typing", "scroll", "tap", "swipe", "motion"}
