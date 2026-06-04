"""
Lightweight ML runtime that actually loads + scores.

Uses scikit-learn IsolationForest per user (saved as joblib).
Falls back to a heuristic model if sklearn is unavailable.
"""

from __future__ import annotations

import os
import math
from typing import Optional

# =========================================================
# MODEL STORAGE
# =========================================================

ART_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(ART_DIR, exist_ok=True)

_model_cache: dict[str, object] = {}

# =========================================================
# OPTIONAL SKLEARN SUPPORT
# =========================================================

_sk_available = False

try:
    import joblib  # type: ignore
    from sklearn.ensemble import IsolationForest  # type: ignore

    _sk_available = True

except Exception:
    _sk_available = False


# =========================================================
# HELPERS
# =========================================================

def _safe_email(email: str) -> str:
    return email.replace("@", "_at_").replace("/", "_")


def _model_path(email: str) -> str:
    return os.path.join(
        ART_DIR,
        f"{_safe_email(email)}.joblib"
    )


# =========================================================
# MODEL LOADING
# =========================================================

def warm_start() -> None:
    """
    Load all saved models into memory.
    """

    if not _sk_available:
        return

    for file in os.listdir(ART_DIR):

        if not file.endswith(".joblib"):
            continue

        try:
            path = os.path.join(ART_DIR, file)

            model = joblib.load(path)

            key = file.replace(".joblib", "")

            _model_cache[key] = model

            print(f"[ML] Loaded model: {file}")

        except Exception as e:
            print(f"[ML] Failed loading {file}: {e}")


# =========================================================
# FEATURE FLATTENING
# =========================================================

def _flatten(features: dict) -> list[float]:
    """
    Convert nested behavioral feature dictionary
    into flat numeric vector.
    """

    keys = [
        "typing",
        "scrolling",
        "tap",
        "swipe",
        "motion"
    ]

    subkeys = [
        "avgSpeed",
        "avgKeyDelay",
        "errorRate",
        "totalDistance",
        "directionChanges",
        "avgReactionTime",
        "accuracy",
        "avgDistance",
        "avgAngle",
        "stabilityScore",
        "movementVariation"
    ]

    vector: list[float] = []

    for key in keys:

        block = features.get(key, {}) or {}

        for sub in subkeys:

            value = block.get(sub, 0)

            try:
                vector.append(float(value))

            except Exception:
                vector.append(0.0)

    return vector


# =========================================================
# SCORING
# =========================================================

def score(email: str, features: dict) -> float:
    """
    Return genuineness score between 0.0 and 1.0
    """

    vector = _flatten(features)

    # Empty features
    if not any(vector):
        return 0.5

    key = _safe_email(email)

    model = _model_cache.get(key)

    # =====================================================
    # REAL MODEL SCORING
    # =====================================================

    if _sk_available and model is not None:

        try:
            raw = float(model.decision_function([vector])[0])

            # Normalize
            normalized = 0.5 + raw

            normalized = max(0.0, min(1.0, normalized))

            return round(normalized, 4)

        except Exception as e:
            print(f"[ML] Prediction error: {e}")

    # =====================================================
    # FALLBACK HEURISTIC
    # =====================================================

    channels = [
        vector[i:i + 11]
        for i in range(0, len(vector), 11)
    ]

    total_signal = 0.0

    for channel in channels:

        avg = sum(channel) / max(len(channel), 1)

        signal = 1.0 / (
            1.0 + math.exp(-(avg - 50) / 100.0)
        )

        total_signal += signal

    score_value = total_signal / max(len(channels), 1)

    score_value = max(0.05, min(0.99, score_value))

    return round(score_value, 4)


# =========================================================
# TRAINING
# =========================================================

def train_user_model(
    email: str,
    samples: list[list[float]]
) -> Optional[str]:
    """
    Train IsolationForest model for user.
    """

    if not _sk_available:
        print("[ML] sklearn unavailable")
        return None

    if len(samples) < 5:
        print("[ML] Not enough samples")
        return None

    try:
        model = IsolationForest(
            n_estimators=64,
            contamination=0.1,
            random_state=42
        )

        model.fit(samples)

        path = _model_path(email)

        joblib.dump(model, path)

        _model_cache[_safe_email(email)] = model

        print(f"[ML] Model trained for {email}")

        return path

    except Exception as e:
        print(f"[ML] Training failed: {e}")
        return None