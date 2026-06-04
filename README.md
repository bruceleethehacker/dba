# Behavioral Authentication System (Enhanced)

Real behavioral biometric authentication: Flask + SQLite + scikit-learn (with optional TensorFlow Lite export) + PWA/Android mobile shell.

## Quick start

```bash
pip install -r requirements.txt
python bootstrap.py            # init SQLite, seed demo user, train demo model
flask --app app run            # http://localhost:5000
```

## What's wired up

| Feature | Where |
|---|---|
| Full Flask backend | `app.py` (untouched logic) + `integration.py` (additive) |
| SQLite architecture | `db/sqlite_store.py`, `db/schema.sql` (auto-init) |
| Real behavioral biometrics | `biometrics/features.py` |
| Continuous authentication | `biometrics/continuous_auth.py` + `/api/v2/ca/state` |
| Real ML models | `ml/runtime.py` (IsolationForest, scikit-learn) |
| TensorFlow Lite conversion | `ml/convert_tflite.py` (optional, requires `pip install tensorflow`) |
| Mobile optimization / PWA / Android | `mobile/` |
| Real telemetry engine | `telemetry/engine.py` → `/api/v2/telemetry` |
| Anomaly detection | `ml/anomaly.py` (Z-score + IsolationForest) |
| Sensor integration | `static/js/sensor_bridge.js` (DeviceMotion / Orientation) |
| Session security | `security/session.py` (HMAC, rotation, fingerprint) |
| Dual write (JSON + SQLite) | `integration.py::dual_write` |

## Verify it works

```bash
python tests/test_e2e.py
```

This registers a user, enrolls, posts to `/api/v2/telemetry`, asserts SQLite rows grow, and asserts the ML score actually varies with input (no more hardcoded `0.85`).

## Optional: TensorFlow Lite export

```bash
pip install tensorflow
python -m ml.convert_tflite demo@bas.local
# → ml/artifacts/demo_at_bas.local.{fp32,int8}.tflite
```
