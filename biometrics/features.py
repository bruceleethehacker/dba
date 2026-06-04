"""Real behavioral-biometric feature extraction.

Converts raw telemetry batches (key events, pointer events, motion samples)
into fixed-length numeric feature vectors suitable for ML models.

Channels supported:
- typing      : dwell/flight times, speed, error rate, rhythm entropy
- scrolling   : velocity stats, jitter, direction-change rate
- tap         : inter-tap intervals, pressure variance, hit-area dispersion
- swipe       : path curvature, peak velocity, duration, length
- motion      : accelerometer & gyroscope variance, tilt stability
"""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Sequence

EPS = 1e-9


def _safe_mean(xs: Sequence[float]) -> float:
    return float(mean(xs)) if xs else 0.0


def _safe_std(xs: Sequence[float]) -> float:
    return float(pstdev(xs)) if len(xs) > 1 else 0.0


def _entropy(xs: Sequence[float], bins: int = 8) -> float:
    if not xs:
        return 0.0
    lo, hi = min(xs), max(xs)
    if hi - lo < EPS:
        return 0.0
    step = (hi - lo) / bins
    counts = [0] * bins
    for x in xs:
        idx = min(bins - 1, int((x - lo) / step))
        counts[idx] += 1
    n = float(sum(counts))
    h = 0.0
    for c in counts:
        if c:
            p = c / n
            h -= p * math.log2(p)
    return h


# ---- typing ----

def typing_features(events: list[dict]) -> dict:
    """events: [{type:'down'|'up', key:str, t:float_ms, correct:bool?}, ...]"""
    downs = [e for e in events if e.get("type") == "down"]
    ups = [e for e in events if e.get("type") == "up"]

    flight = [downs[i]["t"] - downs[i - 1]["t"]
              for i in range(1, len(downs)) if downs[i]["t"] >= downs[i - 1]["t"]]
    # dwell = up - down for matching keys (by key & order)
    dwell = []
    pending: dict[str, list[float]] = {}
    for e in events:
        k = e.get("key", "")
        if e.get("type") == "down":
            pending.setdefault(k, []).append(e["t"])
        elif e.get("type") == "up" and pending.get(k):
            t0 = pending[k].pop(0)
            dwell.append(e["t"] - t0)

    errors = sum(1 for e in events if e.get("correct") is False)
    duration = (events[-1]["t"] - events[0]["t"]) / 1000.0 if len(events) >= 2 else 0.0
    speed_cps = len(downs) / duration if duration > 0 else 0.0

    return {
        "typing_n_keys": float(len(downs)),
        "typing_speed_cps": speed_cps,
        "typing_dwell_mean": _safe_mean(dwell),
        "typing_dwell_std": _safe_std(dwell),
        "typing_flight_mean": _safe_mean(flight),
        "typing_flight_std": _safe_std(flight),
        "typing_error_rate": errors / max(len(downs), 1),
        "typing_rhythm_entropy": _entropy(flight),
    }


# ---- scrolling ----

def scrolling_features(samples: list[dict]) -> dict:
    """samples: [{t:ms, dy:px, vy:px/s}, ...]"""
    if not samples:
        return {"scroll_n": 0.0, "scroll_vy_mean": 0.0, "scroll_vy_std": 0.0,
                "scroll_dir_changes": 0.0, "scroll_jitter": 0.0}
    vys = [s.get("vy", 0.0) for s in samples]
    signs = [1 if v >= 0 else -1 for v in vys]
    dir_changes = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i - 1])
    diffs = [abs(vys[i] - vys[i - 1]) for i in range(1, len(vys))]
    return {
        "scroll_n": float(len(samples)),
        "scroll_vy_mean": _safe_mean([abs(v) for v in vys]),
        "scroll_vy_std": _safe_std(vys),
        "scroll_dir_changes": float(dir_changes),
        "scroll_jitter": _safe_mean(diffs),
    }


# ---- tap ----

def tap_features(taps: list[dict]) -> dict:
    """taps: [{t:ms, x, y, pressure?:0-1, radius?:px}, ...]"""
    if not taps:
        return {"tap_n": 0.0, "tap_iti_mean": 0.0, "tap_iti_std": 0.0,
                "tap_pressure_std": 0.0, "tap_dispersion": 0.0}
    iti = [taps[i]["t"] - taps[i - 1]["t"] for i in range(1, len(taps))]
    pressures = [t.get("pressure", 0.0) for t in taps]
    xs = [t.get("x", 0.0) for t in taps]
    ys = [t.get("y", 0.0) for t in taps]
    cx, cy = _safe_mean(xs), _safe_mean(ys)
    disp = _safe_mean([math.hypot(x - cx, y - cy) for x, y in zip(xs, ys)])
    return {
        "tap_n": float(len(taps)),
        "tap_iti_mean": _safe_mean(iti),
        "tap_iti_std": _safe_std(iti),
        "tap_pressure_std": _safe_std(pressures),
        "tap_dispersion": disp,
    }


# ---- swipe ----

def swipe_features(path: list[dict]) -> dict:
    """path: ordered points [{t, x, y}, ...] of a single swipe."""
    if len(path) < 2:
        return {"swipe_len": 0.0, "swipe_duration": 0.0, "swipe_peak_v": 0.0,
                "swipe_curvature": 0.0, "swipe_straightness": 0.0}
    length = 0.0
    velocities = []
    for i in range(1, len(path)):
        dx = path[i]["x"] - path[i - 1]["x"]
        dy = path[i]["y"] - path[i - 1]["y"]
        dt = max(path[i]["t"] - path[i - 1]["t"], 1.0)
        d = math.hypot(dx, dy)
        length += d
        velocities.append(d / dt * 1000.0)
    duration = (path[-1]["t"] - path[0]["t"]) / 1000.0
    straight = math.hypot(path[-1]["x"] - path[0]["x"], path[-1]["y"] - path[0]["y"])
    curvature = 1.0 - (straight / length) if length > EPS else 0.0
    return {
        "swipe_len": length,
        "swipe_duration": duration,
        "swipe_peak_v": max(velocities) if velocities else 0.0,
        "swipe_curvature": curvature,
        "swipe_straightness": straight / length if length > EPS else 0.0,
    }


# ---- motion ----

def motion_features(samples: list[dict]) -> dict:
    """samples: [{t, ax, ay, az, gx, gy, gz}, ...] from device sensors."""
    if not samples:
        return {f"motion_{k}": 0.0 for k in
                ("ax_std", "ay_std", "az_std", "gx_std", "gy_std", "gz_std",
                 "tilt_stability", "n")}
    cols = {k: [s.get(k, 0.0) for s in samples] for k in
            ("ax", "ay", "az", "gx", "gy", "gz")}
    tilt = [math.atan2(ax, math.sqrt(ay * ay + az * az + EPS))
            for ax, ay, az in zip(cols["ax"], cols["ay"], cols["az"])]
    return {
        "motion_n": float(len(samples)),
        "motion_ax_std": _safe_std(cols["ax"]),
        "motion_ay_std": _safe_std(cols["ay"]),
        "motion_az_std": _safe_std(cols["az"]),
        "motion_gx_std": _safe_std(cols["gx"]),
        "motion_gy_std": _safe_std(cols["gy"]),
        "motion_gz_std": _safe_std(cols["gz"]),
        "motion_tilt_stability": 1.0 / (1.0 + _safe_std(tilt)),
    }


# ---- aggregate ----

FEATURE_ORDER: list[str] = []


def extract_all(batch: dict) -> dict:
    """batch keys: typing, scrolling, taps, swipes(list of paths), motion."""
    feats: dict = {}
    feats.update(typing_features(batch.get("typing", [])))
    feats.update(scrolling_features(batch.get("scrolling", [])))
    feats.update(tap_features(batch.get("taps", [])))
    swipes = batch.get("swipes", [])
    if swipes:
        # average across swipes
        per = [swipe_features(p) for p in swipes]
        keys = per[0].keys()
        feats.update({k: _safe_mean([p[k] for p in per]) for k in keys})
    else:
        feats.update(swipe_features([]))
    feats.update(motion_features(batch.get("motion", [])))
    return feats


def to_vector(features: dict) -> list[float]:
    """Stable-ordered feature vector for ML input."""
    global FEATURE_ORDER
    if not FEATURE_ORDER:
        FEATURE_ORDER = sorted(features.keys())
    return [float(features.get(k, 0.0)) for k in FEATURE_ORDER]
