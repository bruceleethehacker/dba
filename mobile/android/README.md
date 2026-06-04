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
