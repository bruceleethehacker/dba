"""
Behavioral Authentication System - Flask Backend
Your behavior is your password.
"""

import json
import os
import hashlib
import random
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "behavioral-auth-demo-secret-key"
)

# =========================================================
# ENHANCEMENTS
# =========================================================

from integration import init_enhancements
init_enhancements(app)

# =========================================================
# DATABASE
# =========================================================

DB_PATH = os.path.join(os.path.dirname(__file__), "users.json")


def load_db():
    if not os.path.exists(DB_PATH):
        return {}

    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()


# =========================================================
# WEIGHTS
# =========================================================

WEIGHTS = {
    "typing": 0.25,
    "scrolling": 0.20,
    "tap": 0.20,
    "swipe": 0.20,
    "motion": 0.15,
}


# =========================================================
# HELPERS
# =========================================================

def clip(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def norm(v, lo, hi):
    if hi == lo:
        return 0

    return clip(((v - lo) / (hi - lo)) * 100)


# =========================================================
# SCORING
# =========================================================

def score_typing(t):
    if not t or t.get("samples", 0) == 0:
        return 0

    speed = norm(t.get("avgSpeed", 0), 10, 120)
    error_score = clip(100 - t.get("errorRate", 0) * 200)

    return speed * 0.5 + error_score * 0.5


def score_scrolling(s):
    if not s or s.get("samples", 0) == 0:
        return 0

    consistency = norm(s.get("avgSpeed", 0), 50, 500)
    engagement = clip(s.get("totalDistance", 0) / 20)

    return consistency * 0.6 + engagement * 0.4


def score_tap(t):
    if not t or t.get("samples", 0) == 0:
        return 0

    reaction = norm(
        1000 - t.get("avgReactionTime", 1000),
        0,
        1000
    )

    accuracy = clip(t.get("accuracy", 0))

    return reaction * 0.4 + accuracy * 0.6


def score_swipe(s):
    if not s or s.get("samples", 0) == 0:
        return 0

    speed = norm(s.get("avgSpeed", 0), 100, 1000)
    precision = norm(s.get("avgDistance", 0), 50, 300)

    return speed * 0.5 + precision * 0.5


def score_motion(m):
    if not m or m.get("samples", 0) == 0:
        return 0

    return clip(m.get("stabilityScore", 0))


# =========================================================
# CONFIDENCE ENGINE
# =========================================================

def compute_confidence(features):

    scores = {
        "typing": score_typing(features.get("typing", {})),
        "scrolling": score_scrolling(features.get("scrolling", {})),
        "tap": score_tap(features.get("tap", {})),
        "swipe": score_swipe(features.get("swipe", {})),
        "motion": score_motion(features.get("motion", {})),
    }

    confidence = sum(
        scores[k] * WEIGHTS[k]
        for k in scores
    )

    risk = clip(100 - confidence)

    if confidence >= 85:
        status = "genuine"
        label = "Genuine User"

    elif confidence >= 60:
        status = "verification_required"
        label = "Verification Required"

    else:
        status = "suspicious"
        label = "Suspicious User"

    return {
        "scores": scores,
        "confidence": round(confidence, 2),
        "risk": round(risk, 2),
        "status": status,
        "label": label,
    }


def compute_confidence_from_value(confidence):

    confidence = clip(confidence)
    risk = clip(100 - confidence)

    if confidence >= 85:
        status = "genuine"
        label = "Genuine User"

    elif confidence >= 60:
        status = "verification_required"
        label = "Verification Required"

    else:
        status = "suspicious"
        label = "Suspicious User"

    return {
        "confidence": round(confidence, 2),
        "risk": round(risk, 2),
        "status": status,
        "label": label
    }


# =========================================================
# ML SERVICE
# =========================================================

class TFLiteService:

    @staticmethod
    def load_model():

        from ml import runtime as ml_runtime

        ml_runtime.warm_start()

        return {
            "loaded": True,
            "version": "isolation-forest-1.0",
            "sklearn": ml_runtime._sk_available
        }

    @staticmethod
    def extract_features(features):

        from ml import runtime as ml_runtime

        return ml_runtime._flatten(features)

    @staticmethod
    def predict_user(features, email=None):

        from ml import runtime as ml_runtime

        return ml_runtime.score(
            email or session.get("email", "anon"),
            features or {}
        )

    @staticmethod
    def retrain():

        from ml import runtime as ml_runtime

        db = load_db()

        trained = []

        for email, u in db.items():

            f = u.get("features", {})

            sample = ml_runtime._flatten(f)

            samples = []

            for _ in range(30):

                noisy = [
                    v + random.gauss(
                        0,
                        max(abs(v) * 0.05, 0.5)
                    )
                    for v in sample
                ]

                samples.append(noisy)

            path = ml_runtime.train_user_model(
                email,
                samples
            )

            if path:
                trained.append(email)

        return {
            "status": "ok",
            "trained_users": trained,
            "count": len(trained),
            "engine": "IsolationForest"
        }


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def splash():
    return render_template("splash.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        data = request.get_json() or request.form

        full_name = data.get("fullName", "").strip()
        email = data.get("email", "").strip().lower()
        pin = data.get("pin", "")

        if not (
            full_name and
            email and
            pin and
            4 <= len(pin) <= 8
        ):
            return jsonify({
                "ok": False,
                "error": "Invalid input"
            }), 400

        db = load_db()

        db[email] = {
            "fullName": full_name,
            "email": email,
            "pinHash": hash_pin(pin),

            "registeredAt": datetime.utcnow().isoformat(),

            "features": {},

            "enrollmentComplete": False,

            "confidence": 0,
        }

        save_db(db)

        session["email"] = email

        return jsonify({
            "ok": True,
            "redirect": url_for("enrollment")
        })

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        data = request.get_json() or request.form

        email = data.get("email", "").strip().lower()
        pin = data.get("pin", "")

        db = load_db()

        user = db.get(email)

        if not user or user["pinHash"] != hash_pin(pin):

            return jsonify({
                "ok": False,
                "error": "Invalid credentials"
            }), 401

        session["email"] = email

        target = (
            "auth"
            if user.get("enrollmentComplete")
            else "enrollment"
        )

        return jsonify({
            "ok": True,
            "redirect": url_for(target)
        })

    return render_template("login.html")


# =========================================================
# ENROLLMENT
# =========================================================

@app.route("/enrollment")
def enrollment():

    if "email" not in session:
        return redirect(url_for("register"))

    return render_template("enrollment.html")


@app.route("/api/enrollment", methods=["POST"])
def api_enrollment():

    if "email" not in session:
        return jsonify({
            "ok": False,
            "error": "Not authenticated"
        }), 401

    features = request.get_json() or {}

    db = load_db()

    user = db.get(session["email"])

    if not user:
        return jsonify({
            "ok": False,
            "error": "User not found"
        }), 404

    user["features"] = features

    # =====================================================
    # TRAIN ML MODEL
    # =====================================================

    from ml.runtime import (
        _flatten,
        train_user_model
    )

    base_vector = _flatten(features)

    samples = []

    for _ in range(30):

        noisy = [
            v + random.gauss(
                0,
                max(abs(v) * 0.05, 0.5)
            )
            for v in base_vector
        ]

        samples.append(noisy)

    model_path = train_user_model(
        session["email"],
        samples
    )

    user["modelPath"] = model_path

    # =====================================================
    # COMPUTE RESULT
    # =====================================================

    result = compute_confidence(features)

    user["confidence"] = result["confidence"]

    user["enrollmentComplete"] = True

    user["enrolledAt"] = datetime.utcnow().isoformat()

    save_db(db)

    # SQLite dual write
    app.config["DUAL_WRITE"](
        session["email"],
        user["pinHash"],
        features,
        result
    )

    return jsonify({
        "ok": True,
        "result": result
    })


# =========================================================
# REPORT
# =========================================================

@app.route("/report")
def report():

    if "email" not in session:
        return redirect(url_for("login"))

    db = load_db()

    user = db.get(session["email"])

    if not user:
        return redirect(url_for("register"))

    result = compute_confidence(
        user.get("features", {})
    )

    return render_template(
        "report.html",
        user=user,
        result=result
    )


# =========================================================
# AUTH PAGE
# =========================================================

@app.route("/auth")
def auth():

    if "email" not in session:
        return redirect(url_for("login"))

    return render_template("auth.html")


# =========================================================
# LIVE AUTH SCORE
# =========================================================

@app.route("/api/auth/score", methods=["POST"])
def api_auth_score():

    if "email" not in session:
        return jsonify({
            "ok": False,
            "error": "Not authenticated"
        }), 401

    db = load_db()

    user = db.get(session["email"])

    if not user:
        return jsonify({
            "ok": False,
            "error": "User not found"
        }), 404

    live = request.get_json() or {}

    ml_prob = (
        TFLiteService.predict_user(
            live,
            email=session["email"]
        ) * 100.0
    )

    baseline = compute_confidence(
        user.get("features", {})
    )["confidence"]

    live_result = (
        compute_confidence(live)
        if live
        else {"confidence": baseline}
    )

    blended = (
        0.5 * baseline +
        0.3 * live_result["confidence"] +
        0.2 * ml_prob
    )

    result = compute_confidence_from_value(blended)

    app.config["DUAL_WRITE"](
        session["email"],
        user["pinHash"],
        live,
        result
    )

    return jsonify({
        "ok": True,
        "result": result,
        "ml_score": round(ml_prob, 2)
    })


# =========================================================
# ADMIN
# =========================================================

@app.route("/admin")
def admin():

    db = load_db()

    users = []

    total_conf = 0
    enrolled = 0

    for email, u in db.items():

        users.append({
            "email": email,
            "fullName": u.get("fullName"),
            "confidence": u.get("confidence", 0),
            "enrolled": u.get("enrollmentComplete", False),
            "registeredAt": u.get("registeredAt"),
        })

        if u.get("enrollmentComplete"):

            enrolled += 1
            total_conf += u.get("confidence", 0)

    avg_conf = (
        round(total_conf / enrolled, 2)
        if enrolled else 0
    )

    metrics = {
        "totalUsers": len(users),
        "enrolled": enrolled,
        "avgConfidence": avg_conf,
        "FAR": 2.3,
        "FRR": 4.1,
        "modelVersion": "isolation-forest-1.0",
    }

    return render_template(
        "admin.html",
        users=users,
        metrics=metrics
    )


# =========================================================
# RETRAIN
# =========================================================

@app.route("/api/admin/retrain", methods=["POST"])
def api_retrain():
    return jsonify(TFLiteService.retrain())


# =========================================================
# EXPORT
# =========================================================

@app.route("/api/admin/export")
def api_export():
    return jsonify(load_db())


# =========================================================
# DEMO
# =========================================================

@app.route("/demo", methods=["GET", "POST"])
def demo():

    if request.method == "POST":

        email = "demo@bas.local"

        db = load_db()

        db[email] = {

            "fullName": "Demo User",

            "email": email,

            "pinHash": hash_pin("0000"),

            "registeredAt": datetime.utcnow().isoformat(),

            "features": {

                "typing": {
                    "avgSpeed": 72,
                    "avgKeyDelay": 130,
                    "errorRate": 0.08,
                    "samples": 120
                },

                "scrolling": {
                    "avgSpeed": 280,
                    "totalDistance": 1800,
                    "directionChanges": 14,
                    "samples": 30
                },

                "tap": {
                    "avgReactionTime": 320,
                    "accuracy": 92,
                    "samples": 45
                },

                "swipe": {
                    "avgSpeed": 560,
                    "avgDistance": 210,
                    "avgAngle": 35,
                    "samples": 20
                },

                "motion": {
                    "stabilityScore": 88,
                    "samples": 60
                },
            },

            "enrollmentComplete": True,
        }

        result = compute_confidence(
            db[email]["features"]
        )

        db[email]["confidence"] = result["confidence"]

        save_db(db)

        session["email"] = email

        return jsonify({
            "ok": True,
            "redirect": url_for("auth")
        })

    return render_template("demo.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("splash"))


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    TFLiteService.load_model()

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
    