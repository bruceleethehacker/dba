-- SQLite schema for behavioral authentication system.
-- Loaded by db/sqlite_store.py via init_db().

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    pin_hash        TEXT NOT NULL,
    salt            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    enrolled        INTEGER NOT NULL DEFAULT 0,
    risk_profile    TEXT NOT NULL DEFAULT 'standard'
);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,            -- HMAC session token
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    issued_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen       TEXT NOT NULL DEFAULT (datetime('now')),
    ip              TEXT,
    user_agent      TEXT,
    revoked         INTEGER NOT NULL DEFAULT 0,
    trust_score     REAL NOT NULL DEFAULT 100.0
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- Raw telemetry events (append-only).
CREATE TABLE IF NOT EXISTS telemetry_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ts              REAL NOT NULL,               -- client epoch ms
    channel         TEXT NOT NULL,               -- typing|scroll|tap|swipe|motion|sensor
    payload         TEXT NOT NULL                -- JSON blob
);

CREATE INDEX IF NOT EXISTS idx_tel_user_ts  ON telemetry_events(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_tel_channel  ON telemetry_events(channel);

-- Per-user behavioral profile baselines (rolling means/stds).
CREATE TABLE IF NOT EXISTS behavior_profiles (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    feature_json    TEXT NOT NULL,               -- JSON of feature->{mean,std,n}
    samples         INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Continuous-auth scoring history.
CREATE TABLE IF NOT EXISTS auth_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,
    user_id         INTEGER,
    ts              TEXT NOT NULL DEFAULT (datetime('now')),
    score           REAL NOT NULL,
    risk            TEXT NOT NULL,               -- low|medium|high|critical
    breakdown       TEXT NOT NULL                -- JSON per-channel
);

CREATE INDEX IF NOT EXISTS idx_auth_user_ts ON auth_scores(user_id, ts);

-- Anomaly detections.
CREATE TABLE IF NOT EXISTS anomalies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    session_id      TEXT,
    ts              TEXT NOT NULL DEFAULT (datetime('now')),
    severity        TEXT NOT NULL,
    feature         TEXT NOT NULL,
    z_score         REAL NOT NULL,
    detail          TEXT
);
