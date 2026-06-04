"""One-shot bootstrap: initialize SQLite, seed demo data, train models,
print summary. Run once after install:

    python bootstrap.py
"""
from __future__ import annotations

import hashlib
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from db import sqlite_store as store  # noqa: E402
from ml import runtime as ml_runtime   # noqa: E402


def seed_demo_user(email: str = "demo@bas.local", n_samples: int = 40) -> int:
    pin_hash = hashlib.sha256(b"0000").hexdigest()
    uid = store.upsert_user(email, pin_hash, "demo-salt")
    store.mark_enrolled(uid)
    samples = []
    for i in range(n_samples):
        feats = {
            "typing":    {"avgSpeed": 60 + random.gauss(0, 6),
                          "avgKeyDelay": 120 + random.gauss(0, 15),
                          "errorRate": max(0, random.gauss(0.05, 0.02)),
                          "samples": 50},
            "scrolling": {"avgSpeed": 200 + random.gauss(0, 20),
                          "totalDistance": 1500 + random.gauss(0, 200),
                          "directionChanges": int(8 + random.gauss(0, 2)),
                          "samples": 30},
            "tap":       {"avgReactionTime": 320 + random.gauss(0, 30),
                          "accuracy": 90 + random.gauss(0, 4),
                          "samples": 10},
            "swipe":     {"avgSpeed": 500 + random.gauss(0, 40),
                          "avgDistance": 180 + random.gauss(0, 20),
                          "avgAngle": 45 + random.gauss(0, 10),
                          "samples": 6},
            "motion":    {"stabilityScore": 85 + random.gauss(0, 5),
                          "movementVariation": 10 + random.gauss(0, 2),
                          "samples": 10},
        }
        for ch, p in feats.items():
            store.insert_telemetry(None, uid, ch, p)
        samples.append(ml_runtime._flatten(feats))
    path = ml_runtime.train_user_model(email, samples)
    return uid, path


def main():
    print("→ Initializing SQLite…")
    store.init_db()
    print("→ Seeding demo user + telemetry…")
    uid, model_path = seed_demo_user()
    print(f"   demo user_id={uid}")
    print(f"   model: {model_path or 'sklearn missing — using heuristic fallback'}")

    with store.get_conn() as conn:
        u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        t = conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()[0]
        s = conn.execute("SELECT COUNT(*) FROM auth_scores").fetchone()[0]
    print(f"→ DB row counts: users={u}  telemetry={t}  scores={s}")
    print("✓ Bootstrap complete. Start the app with:  flask --app app run")


if __name__ == "__main__":
    main()
