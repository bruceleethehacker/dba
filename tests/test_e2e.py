"""End-to-end smoke test: register -> enroll -> ensure SQLite was filled
and the ML score actually changes with input."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# isolated DB
os.environ["BAS_SQLITE_PATH"] = os.path.join(ROOT, "db", "bas-test.db")
if os.path.exists("/tmp/bas-test.db"):
    os.remove("/tmp/bas-test.db")

from app import app, TFLiteService  # noqa: E402
from db import sqlite_store as store  # noqa: E402

client = app.test_client()

# 1. register
r = client.post("/register", json={
    "fullName": "Test", "email": "t@x.com", "pin": "1234"
})
assert r.status_code == 200, r.data

# 2. enroll with rich features
feats = {
    "typing": {"avgSpeed": 60, "avgKeyDelay": 120, "errorRate": 0.05, "samples": 40},
    "scrolling": {"avgSpeed": 200, "totalDistance": 1500, "directionChanges": 8, "samples": 30},
    "tap": {"avgReactionTime": 320, "accuracy": 92, "samples": 10},
    "swipe": {"avgSpeed": 500, "avgDistance": 180, "avgAngle": 45, "samples": 6},
    "motion": {"stabilityScore": 85, "movementVariation": 10, "samples": 10},
}
r = client.post("/api/enrollment", json=feats)
print("enroll:", r.status_code, r.get_json())
assert r.status_code == 200

# 3. SQLite must have a user + telemetry rows
with store.get_conn() as conn:
    nu = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    nt = conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()[0]
print(f"SQLite users={nu} telemetry={nt}")
assert nu >= 1, "user not stored"
assert nt >= 1, "telemetry not stored"

# 4. v2 telemetry endpoint must accept and persist
r = client.post("/api/v2/telemetry", json={
    "typing": [{"type": "down", "key": "a", "t": 100}],
    "scrolling": [{"y": 10, "t": 1}],
    "taps": [{"x": 5, "y": 5, "t": 1}],
})
print("v2 telemetry:", r.status_code, r.get_json())
assert r.status_code == 200

with store.get_conn() as conn:
    nt2 = conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()[0]
print(f"telemetry after v2: {nt2}")
assert nt2 > nt, "v2 telemetry did not persist"

# 5. ML score must vary with input (not the old hardcoded 0.85)
s1 = TFLiteService.predict_user(feats, email="t@x.com")
feats2 = json.loads(json.dumps(feats))
feats2["typing"]["avgSpeed"] = 250
feats2["tap"]["avgReactionTime"] = 80
s2 = TFLiteService.predict_user(feats2, email="t@x.com")
print(f"ML scores: same={s1}  fast-input={s2}")
assert s1 != s2, "ML score is constant — model not live"

# 6. auth/score endpoint blends ML + baseline
r = client.post("/api/auth/score", json=feats2)
print("auth score:", r.get_json())
assert r.status_code == 200
assert "ml_score" in r.get_json()

print("\n✓ ALL CHECKS PASSED")
# print(store.DB_FILE)

# print(os.path.exists(os.path.dirname(store.DB_FILE)))