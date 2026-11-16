CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('doctor', 'patient')),
    preferred_language TEXT NOT NULL DEFAULT 'en'
        CHECK (preferred_language IN ('en', 'fr')),
    theme_preference TEXT NOT NULL DEFAULT 'light'
        CHECK (theme_preference IN ('light', 'dark')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE patient_profiles (
    id INTEGER PRIMARY KEY,
    doctor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    patient_user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    display_name TEXT NOT NULL,
    profile_status TEXT NOT NULL DEFAULT 'pending_assessment'
        CHECK (profile_status IN ('pending_assessment', 'ready', 'linked')),
    risk_score REAL,
    systolic_threshold INTEGER,
    diastolic_threshold INTEGER,
    initial_delay_seconds INTEGER NOT NULL DEFAULT 86400
        CHECK (initial_delay_seconds > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (systolic_threshold IS NULL AND diastolic_threshold IS NULL)
        OR (
            systolic_threshold IS NOT NULL AND diastolic_threshold IS NOT NULL
            AND systolic_threshold > 0 AND diastolic_threshold > 0
        )
    )
);

CREATE TABLE patient_invites (
    id INTEGER PRIMARY KEY,
    patient_profile_id INTEGER NOT NULL
        REFERENCES patient_profiles(id) ON DELETE CASCADE,
    issued_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    code_hash TEXT NOT NULL UNIQUE,
    issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE risk_assessments (
    id INTEGER PRIMARY KEY,
    patient_profile_id INTEGER NOT NULL
        REFERENCES patient_profiles(id) ON DELETE CASCADE,
    questionnaire_version TEXT NOT NULL,
    risk_score REAL NOT NULL,
    systolic_threshold INTEGER NOT NULL CHECK (systolic_threshold > 0),
    diastolic_threshold INTEGER NOT NULL CHECK (diastolic_threshold > 0),
    assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_answers (
    id INTEGER PRIMARY KEY,
    assessment_id INTEGER NOT NULL
        REFERENCES risk_assessments(id) ON DELETE CASCADE,
    question_key TEXT NOT NULL,
    answer_value TEXT NOT NULL,
    UNIQUE (assessment_id, question_key)
);

CREATE TABLE measurements (
    id INTEGER PRIMARY KEY,
    patient_profile_id INTEGER NOT NULL
        REFERENCES patient_profiles(id) ON DELETE CASCADE,
    measured_at TEXT NOT NULL,
    grade INTEGER CHECK (grade BETWEEN 0 AND 3),
    status TEXT NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('pending_confirmation', 'recorded', 'discarded')),
    next_delay_seconds INTEGER CHECK (next_delay_seconds > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vital_readings (
    id INTEGER PRIMARY KEY,
    measurement_id INTEGER NOT NULL
        REFERENCES measurements(id) ON DELETE CASCADE,
    reading_kind TEXT NOT NULL CHECK (reading_kind IN ('initial', 'confirmation')),
    systolic INTEGER NOT NULL CHECK (systolic > 0),
    diastolic INTEGER NOT NULL CHECK (diastolic > 0),
    pulse INTEGER NOT NULL CHECK (pulse > 0),
    measured_at TEXT NOT NULL,
    UNIQUE (measurement_id, reading_kind)
);

CREATE TABLE symptom_entries (
    id INTEGER PRIMARY KEY,
    measurement_id INTEGER NOT NULL
        REFERENCES measurements(id) ON DELETE CASCADE,
    symptom_key TEXT NOT NULL CHECK (
        symptom_key IN (
            'malDeTete', 'vertige', 'visionFloue', 'essoufflement',
            'saignementDeNez', 'fatigue', 'confusion', 'perteDeBalan'
        )
    ),
    intensity INTEGER NOT NULL CHECK (intensity BETWEEN 0 AND 5),
    UNIQUE (measurement_id, symptom_key)
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    patient_profile_id INTEGER NOT NULL
        REFERENCES patient_profiles(id) ON DELETE CASCADE,
    measurement_id INTEGER REFERENCES measurements(id) ON DELETE SET NULL,
    grade INTEGER CHECK (grade BETWEEN 1 AND 3),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TEXT
);

CREATE TABLE doctor_notes (
    id INTEGER PRIMARY KEY,
    patient_profile_id INTEGER NOT NULL
        REFERENCES patient_profiles(id) ON DELETE CASCADE,
    doctor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    note TEXT NOT NULL CHECK (length(trim(note)) > 0),
    noted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_patient_profiles_doctor
    ON patient_profiles(doctor_id, created_at);
CREATE INDEX idx_measurements_patient_time
    ON measurements(patient_profile_id, measured_at);
CREATE INDEX idx_vital_readings_measurement
    ON vital_readings(measurement_id);
CREATE INDEX idx_alerts_patient_ack_time
    ON alerts(patient_profile_id, acknowledged_at, created_at);
CREATE INDEX idx_doctor_notes_patient_time
    ON doctor_notes(patient_profile_id, noted_at);
CREATE INDEX idx_patient_invites_code_expiry
    ON patient_invites(code_hash, expires_at, consumed_at);
