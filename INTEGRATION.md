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
