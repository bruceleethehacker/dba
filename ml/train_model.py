"""Train per-user behavioral models from SQLite telemetry.

Uses scikit-learn IsolationForest (one-class anomaly detection) — the right
model family for behavioral baselines. TensorFlow is optional: if installed,
convert_tflite.py can additionally export a .tflite version.

Usage:
    python -m ml.train_model              # train all users
    python -m ml.train_model user@x.com   # train one
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db import sqlite_store as store  # noqa: E402
from ml import runtime as ml_runtime  # noqa: E402


def _samples_for_user(user_id: int) -> list[list[float]]:
    events = store.fetch_recent_events(user_id, limit=2000)
    # Reconstruct (channel -> latest payload) snapshots in time order.
    by_ts: dict[float, dict] = {}
    for ev in reversed(events):
        snap = by_ts.setdefault(round(ev["ts"] / 1000), {})
        snap[ev["channel"]] = ev["payload"]
    samples: list[list[float]] = []
    for _ts, snap in by_ts.items():
        feats = {
            "typing":    snap.get("typing", {}),
            "scrolling": snap.get("scroll", {}),
            "tap":       snap.get("tap", {}),
            "swipe":     snap.get("swipe", {}),
            "motion":    snap.get("motion", {}),
        }
        samples.append(ml_runtime._flatten(feats))
    return samples


def train_and_export(username: str | None = None) -> dict:
    store.init_db()
    targets: list[tuple[int, str]] = []
    with store.get_conn() as conn:
        if username:
            r = conn.execute("SELECT id, username FROM users WHERE username = ?",
                             (username,)).fetchone()
            if r:
                targets.append((r["id"], r["username"]))
        else:
            for r in conn.execute("SELECT id, username FROM users").fetchall():
                targets.append((r["id"], r["username"]))

    results = {}
    for uid, uname in targets:
        samples = _samples_for_user(uid)
        if len(samples) < 5:
            # synthesize jitter for cold start
            base = samples[0] if samples else [0.0] * 55
            import random
            samples = [[v + random.gauss(0, max(abs(v) * 0.08, 0.5)) for v in base]
                       for _ in range(30)]
        path = ml_runtime.train_user_model(uname, samples)
        results[uname] = {"samples": len(samples), "model": path,
                          "trained": path is not None}
        print(f"[train] {uname}: {results[uname]}")
    return results


if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else None
    out = train_and_export(user)
    print(json.dumps(out, indent=2, default=str))
