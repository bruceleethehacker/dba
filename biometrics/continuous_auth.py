"""Continuous authentication engine.

Runs in the background of an authenticated session, ingests telemetry
batches, scores them against the user's behavioral profile, updates a
rolling trust score, and triggers step-up auth or session revocation
when trust falls below configurable thresholds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from biometrics.features import extract_all, to_vector
from db import sqlite_store as store
from ml.anomaly import AnomalyDetector


@dataclass
class TrustState:
    user_id: int
    session_id: str
    score: float = 100.0          # 0..100
    last_update: float = field(default_factory=time.time)
    decay_per_min: float = 2.0    # passive decay encourages fresh telemetry
    history: list[float] = field(default_factory=list)


def risk_band(score: float) -> str:
    if score >= 80: return "low"
    if score >= 60: return "medium"
    if score >= 40: return "high"
    return "critical"


class ContinuousAuth:
    """Per-session continuous authenticator.

    Plug in `on_step_up` / `on_revoke` callbacks to integrate with the
    Flask app. Designed to be additive — does not modify the original
    /api/score endpoint; mount as a new endpoint under e.g. /api/v2/ca.
    """

    def __init__(self,
                 on_step_up: Optional[Callable[[TrustState], None]] = None,
                 on_revoke: Optional[Callable[[TrustState], None]] = None,
                 step_up_threshold: float = 55.0,
                 revoke_threshold: float = 30.0):
        self._states: dict[str, TrustState] = {}
        self._detectors: dict[int, AnomalyDetector] = {}
        self.on_step_up = on_step_up
        self.on_revoke = on_revoke
        self.step_up_threshold = step_up_threshold
        self.revoke_threshold = revoke_threshold

    # ---- state ----
    def start(self, session_id: str, user_id: int) -> TrustState:
        st = TrustState(user_id=user_id, session_id=session_id)
        self._states[session_id] = st
        return st

    def stop(self, session_id: str) -> None:
        self._states.pop(session_id, None)

    def _detector(self, user_id: int) -> AnomalyDetector:
        det = self._detectors.get(user_id)
        if det is None:
            det = AnomalyDetector.load_for_user(user_id)
            self._detectors[user_id] = det
        return det

    # ---- ingest ----
    def ingest(self, session_id: str, batch: dict) -> dict:
        st = self._states.get(session_id)
        if st is None:
            return {"error": "unknown session"}

        # passive decay
        now = time.time()
        elapsed_min = (now - st.last_update) / 60.0
        st.score = max(0.0, st.score - st.decay_per_min * elapsed_min)
        st.last_update = now

        features = extract_all(batch)
        vec = to_vector(features)
        det = self._detector(st.user_id)
        match, breakdown = det.score(features)
        anomalies = det.detect(features)

        # blended update: 70% prior trust, 30% fresh match (0..100)
        st.score = max(0.0, min(100.0, 0.7 * st.score + 0.3 * match))
        # penalize per anomaly
        st.score = max(0.0, st.score - 5.0 * len(anomalies))
        st.history.append(st.score)
        if len(st.history) > 200:
            st.history = st.history[-200:]

        risk = risk_band(st.score)
        store.record_score(session_id, st.user_id, st.score, risk, breakdown)
        for a in anomalies:
            store.record_anomaly(st.user_id, session_id, a["severity"],
                                 a["feature"], a["z"], a.get("detail", ""))
        store.touch_session(session_id, st.score)

        action = "continue"
        if st.score < self.revoke_threshold:
            action = "revoke"
            if self.on_revoke:
                self.on_revoke(st)
        elif st.score < self.step_up_threshold:
            action = "step_up"
            if self.on_step_up:
                self.on_step_up(st)

        return {
            "trust": st.score,
            "risk": risk,
            "action": action,
            "breakdown": breakdown,
            "anomalies": anomalies,
        }

    def snapshot(self, session_id: str) -> Optional[dict]:
        st = self._states.get(session_id)
        if not st:
            return None
        return {"trust": st.score, "risk": risk_band(st.score),
                "history": st.history[-50:]}
