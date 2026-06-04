"""Anomaly detection for behavioral features.

Two-layer detector:
1. Per-feature z-score detector against the user's rolling profile
   (works from day one, no training data required).
2. Optional Isolation Forest (scikit-learn) for joint-distribution
   anomalies; loaded lazily if sklearn + a saved model is available.

Profiles are stored in SQLite (`behavior_profiles` table) using
Welford's online algorithm so means/variances update incrementally.
"""

from __future__ import annotations

import json
import math
import os
import pickle
from typing import Optional

from db import sqlite_store as store


def _welford_update(mean: float, m2: float, n: int, x: float):
    n += 1
    delta = x - mean
    mean += delta / n
    m2 += delta * (x - mean)
    return mean, m2, n


class AnomalyDetector:
    SEVERE_Z = 4.0
    HIGH_Z = 3.0
    MED_Z = 2.0

    def __init__(self, user_id: int, profile: dict):
        self.user_id = user_id
        self.features: dict[str, dict] = profile.get("features", {})
        self.samples: int = profile.get("samples", 0)
        self._iforest = None
        self._try_load_iforest()

    @classmethod
    def load_for_user(cls, user_id: int) -> "AnomalyDetector":
        return cls(user_id, store.load_profile(user_id))

    # ---- model ----
    def _try_load_iforest(self):
        path = os.path.join(os.path.dirname(__file__),
                            f"models/iforest_user_{self.user_id}.pkl")
        if not os.path.exists(path):
            return
        try:
            with open(path, "rb") as f:
                self._iforest = pickle.load(f)
        except Exception:
            self._iforest = None

    # ---- updates ----
    def update_profile(self, features: dict) -> None:
        for k, v in features.items():
            entry = self.features.get(k, {"mean": 0.0, "m2": 0.0, "n": 0})
            mean, m2, n = _welford_update(entry["mean"], entry["m2"], entry["n"], float(v))
            self.features[k] = {"mean": mean, "m2": m2, "n": n}
        self.samples += 1
        store.save_profile(self.user_id, self.features, self.samples)

    # ---- scoring ----
    def _z(self, key: str, x: float) -> float:
        e = self.features.get(key)
        if not e or e["n"] < 5:
            return 0.0
        var = e["m2"] / max(e["n"] - 1, 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std < 1e-6:
            return 0.0
        return (float(x) - e["mean"]) / std

    def score(self, features: dict) -> tuple[float, dict]:
        """Return (match_score 0..100, per-channel breakdown)."""
        channels: dict[str, list[float]] = {
            "typing": [], "scroll": [], "tap": [], "swipe": [], "motion": []
        }
        for k, v in features.items():
            z = abs(self._z(k, v))
            prefix = k.split("_", 1)[0]
            if prefix in channels:
                channels[prefix].append(z)
        breakdown = {}
        for ch, zs in channels.items():
            if not zs:
                breakdown[ch] = 100.0
                continue
            mean_z = sum(zs) / len(zs)
            # map z in [0,4] -> score [100,0]
            breakdown[ch] = max(0.0, 100.0 - 25.0 * mean_z)
        match = sum(breakdown.values()) / len(breakdown)

        if self._iforest is not None:
            try:
                from biometrics.features_vector import build_vector  # type: ignore
                vec = build_vector(features)
                # decision_function: higher = more normal
                df = float(self._iforest.decision_function([vec])[0])
                # blend
                match = 0.7 * match + 0.3 * max(0.0, min(100.0, 50.0 + 50.0 * df))
            except Exception:
                pass
        return match, breakdown

    def detect(self, features: dict) -> list[dict]:
        out = []
        for k, v in features.items():
            z = self._z(k, float(v))
            az = abs(z)
            if az >= self.SEVERE_Z:
                sev = "critical"
            elif az >= self.HIGH_Z:
                sev = "high"
            elif az >= self.MED_Z:
                sev = "medium"
            else:
                continue
            out.append({"feature": k, "z": z, "severity": sev,
                        "detail": f"value={v:.3f}"})
        return out
