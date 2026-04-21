-- =========================================================
-- SQLite Schema for Fall Detection System
-- =========================================================

-- ─── Patients ───────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER,
    status TEXT DEFAULT 'NORMAL',
    medical_history TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ─── Devices ────────────────────────────────────
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    patient_id TEXT REFERENCES patients(patient_id),
    type TEXT NOT NULL,  -- 'WEARABLE' or 'CAMERA'
    battery_level INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ─── Motion Data ───────────────────────────────
CREATE TABLE IF NOT EXISTS motion_data (
    time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    patient_id TEXT REFERENCES patients(patient_id),
    device_id TEXT REFERENCES devices(device_id),
    ax REAL,
    ay REAL,
    az REAL,
    gyro REAL,
    smv REAL,
    motion_type TEXT DEFAULT 'normal',
    PRIMARY KEY (time, patient_id)
);

-- ─── Vital Signs ───────────────────────────────
CREATE TABLE IF NOT EXISTS vital_signs (
    time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    patient_id TEXT REFERENCES patients(patient_id),
    device_id TEXT REFERENCES devices(device_id),
    heart_rate INTEGER,
    spo2 INTEGER,
    PRIMARY KEY (time, patient_id)
);

-- ─── Audio Events ──────────────────────────────
CREATE TABLE IF NOT EXISTS audio_events (
    time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    patient_id TEXT REFERENCES patients(patient_id),
    device_id TEXT REFERENCES devices(device_id),
    distress_detected BOOLEAN DEFAULT FALSE,
    audio_activity BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (time, patient_id)
);

-- ─── Event Log (Alerts & State Changes) ────────
CREATE TABLE IF NOT EXISTS event_log (
    id TEXT PRIMARY KEY,
    time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    patient_id TEXT REFERENCES patients(patient_id),
    event_type TEXT NOT NULL,
    confidence REAL,
    metadata TEXT, -- Stored as JSON string
    resolved BOOLEAN DEFAULT FALSE,
    resolution_time DATETIME
);

-- ─── Seed Data for Testing ─────────────────────
INSERT OR IGNORE INTO patients (patient_id, name, age, status)
VALUES ('patient_01', 'John Doe', 78, 'NORMAL');

INSERT OR IGNORE INTO devices (device_id, patient_id, type, battery_level)
VALUES 
    ('AA:BB:CC:DD:EE:01', 'patient_01', 'WEARABLE', 87),
    ('CAM-01-LR', 'patient_01', 'CAMERA', 100);
