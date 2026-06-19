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

# Android wrapper (Capacitor / TWA)

This folder contains the configuration to ship the Flask web app as an
installable Android app **without modifying the existing Flask code**.

## Option A — Capacitor (recommended, fastest path)

```bash
npm init @capacitor/app behavioral-auth -- --app-id dev.lovable.behavioralauth
cd behavioral-auth
npm install @capacitor/android @capacitor/motion @capacitor/device @capacitor/haptics
cp ../capacitor.config.json ./capacitor.config.json
npx cap add android
# point server.url at your deployed Flask host, then
npx cap sync android
npx cap open android   # build & sign in Android Studio
```

Merge `AndroidManifest.snippet.xml` into
`android/app/src/main/AndroidManifest.xml` so the app gets the sensor
permissions required by `sensors/sensor_bridge.js`.

## Option B — Trusted Web Activity (TWA)

Use Bubblewrap to wrap the deployed PWA:

```bash
npm i -g @bubblewrap/cli
bubblewrap init --manifest=https://YOUR-FLASK-HOST/mobile/pwa/manifest.webmanifest
bubblewrap build
```

Both options consume the same `mobile/pwa/service-worker.js` and
`manifest.webmanifest` and talk to the same `/api/v2/telemetry` endpoint,
so behavioral biometrics, continuous auth, anomaly detection, and
TFLite inference all work identically on web and Android.

## On-device TFLite inference

Ship `ml/models/keras_user_<id>_int8.tflite` inside `android/app/src/main/assets/`
and load with the standard TFLite Android interpreter (NNAPI delegate
recommended). Use the JSON scaler in `ml/models/scaler_user_<id>.json`
to normalize inputs identically to training.

