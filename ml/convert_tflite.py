"""Optional TFLite export. Only runs if TensorFlow is installed.

Wraps the trained sklearn IsolationForest into a tiny Keras MLP that
mimics its decision_function, then converts to .tflite with float32
and int8 quantization variants for mobile.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART_DIR = os.path.join(HERE, "artifacts")


def convert(email: str) -> dict:
    try:
        import joblib
        import numpy as np
        import tensorflow as tf
    except Exception as e:
        return {"ok": False, "skipped": True,
                "reason": f"TensorFlow/joblib unavailable: {e}"}

    safe = email.replace("@", "_at_")
    src = os.path.join(ART_DIR, f"{safe}.joblib")
    if not os.path.exists(src):
        return {"ok": False, "reason": f"no model for {email}"}

    model = joblib.load(src)
    # generate a synthetic dataset and let TF learn to mimic the IF score
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (2000, 55)).astype("float32")
    y = model.decision_function(X).astype("float32")

    keras_model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(55,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(1),
    ])
    keras_model.compile(optimizer="adam", loss="mse")
    keras_model.fit(X, y, epochs=8, verbose=0)

    conv = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    tflite_fp32 = conv.convert()
    fp32_path = os.path.join(ART_DIR, f"{safe}.fp32.tflite")
    with open(fp32_path, "wb") as f:
        f.write(tflite_fp32)

    conv_int8 = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    conv_int8.optimizations = [tf.lite.Optimize.DEFAULT]
    int8_path = os.path.join(ART_DIR, f"{safe}.int8.tflite")
    with open(int8_path, "wb") as f:
        f.write(conv_int8.convert())

    return {"ok": True, "fp32": fp32_path, "int8": int8_path}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m ml.convert_tflite <email>")
        sys.exit(1)
    print(convert(sys.argv[1]))
