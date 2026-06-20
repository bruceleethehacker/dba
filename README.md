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
####################################################

This registers a user, enrolls, posts to `/api/v2/telemetry`, asserts SQLite rows grow, and asserts the ML score actually varies with input (no more hardcoded `0.85`).

## Optional: TensorFlow Lite export

```bash
pip install tensorflow
python -m ml.convert_tflite demo@bas.local
# → ml/artifacts/demo_at_bas.local.{fp32,int8}.tflite
```
# Adding the new features to the existing Flask app

Per the original brief, **none of the existing files were modified**.
All new functionality lives in additive modules. To activate them, add
a single block at the bottom of `app.py` (or in a wrapper script like
`run.py`):

```python
# --- additive feature wiring (does not change existing routes) ---
from db.sqlite_store import init_db
from telemetry.engine import telemetry_bp
from security.session import SessionGuard

init_db()
app.register_blueprint(telemetry_bp, url_prefix="/api/v2")
app.config["SESSION_GUARD"] = SessionGuard()
```

That single hookup turns on:

| Feature                       | Where it lives                              |
|-------------------------------|---------------------------------------------|
| 1. Full Flask backend         | existing `app.py` + new `/api/v2/*` blueprint |
| 2. SQLite architecture        | `db/schema.sql`, `db/sqlite_store.py`       |
| 3. Real behavioral biometrics | `biometrics/features.py`                    |
| 4. Continuous authentication  | `biometrics/continuous_auth.py`             |
| 5. Real ML models             | `ml/train_model.py` (IsolationForest + Keras AE) |
| 6. TensorFlow Lite conversion | `ml/convert_tflite.py` (float32 + int8)     |
| 7. Mobile optimization        | int8 quantization + PWA + Capacitor config  |
| 8. Android / PWA structure    | `mobile/pwa/*`, `mobile/android/*`          |
| 9. Real telemetry engine      | `telemetry/engine.py`                       |
| 10. Anomaly detection         | `ml/anomaly.py` (z-score + IsolationForest) |
| 11. Sensor integration        | `sensors/sensor_bridge.js`                  |
| 12. Session security          | `security/session.py` (HMAC + rotation + revoke) |
| 13. Packaging                 | distributed as a single ZIP                 |

## Run

```bash
pip install -r requirements.txt        # Flask only -- demo runs immediately
pip install -r requirements-ml.txt     # adds numpy/sklearn/tensorflow for ML
python app.py                          # http://localhost:5000

# Train per-user models once enough telemetry exists
python -m ml.train_model --all
python -m ml.convert_tflite --user 1
```

## Client wiring (web or PWA)

Add to any page that should report behavior:

```html
<script src="/sensors/sensor_bridge.js"></script>
<script>
  BAS.Sensors.setToken(window.__BAS_TOKEN__); // optional
  BAS.Sensors.requestPermission().then(BAS.Sensors.start);
</script>
```

The original `static/js/telemetry.js` keeps working untouched; the new
bridge sends to `/api/v2/telemetry`, which goes through validation,
SQLite persistence, feature extraction, ML scoring, anomaly detection,
and trust-score rotation.

####################################################

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


# Author 

Veda Nishanth (bruce lee) 
Cybersecurity| ethical hacker

