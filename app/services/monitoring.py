from datetime import datetime, timezone


INITIAL_DELAY_SECONDS = 24 * 60 * 60
MINIMUM_DELAY_SECONDS = 5 * 60
SYMPTOM_KEYS = (
    "malDeTete",
    "vertige",
    "visionFloue",
    "essoufflement",
    "saignementDeNez",
    "fatigue",
    "confusion",
    "perteDeBalan",
)


def parse_vitals(form):
    try:
        systolic = int(form.get("systolic", ""))
        diastolic = int(form.get("diastolic", ""))
        pulse = int(form.get("pulse", ""))
    except (TypeError, ValueError) as error:
        raise ValueError("Vital readings must be whole numbers.") from error
    if systolic <= 0 or diastolic <= 0 or pulse <= 0:
        raise ValueError("Vital readings must be positive.")
    return systolic, diastolic, pulse


def parse_symptoms(form):
    symptoms = {}
    for key in SYMPTOM_KEYS:
        try:
            intensity = int(form.get(key, ""))
        except (TypeError, ValueError) as error:
            raise ValueError("Every symptom must have an intensity.") from error
        if not 0 <= intensity <= 5:
            raise ValueError("Symptom intensities must be from 0 to 5.")
        symptoms[key] = intensity
    return symptoms


def classify_grade(systolic, diastolic, patient, symptom_total=0):
    pulse_pressure = systolic - diastolic
    if systolic >= 180 or diastolic >= 110:
        return 3
    if systolic >= 160 or diastolic >= 100:
        return 2
    if (
        systolic >= patient["systolic_threshold"]
        or diastolic >= patient["diastolic_threshold"]
        or not 20 <= pulse_pressure <= 60
        or symptom_total > 5
    ):
        return 1
    return 0


def _next_delay(database, patient_id, grade, symptom_total, exclude_id=None):
    if grade == 3:
        return MINIMUM_DELAY_SECONDS

    points = 0.5 * symptom_total
    if grade == 2:
        factor = min(1, 0.7 + 0.05 * points)
        return max(
            MINIMUM_DELAY_SECONDS,
            round(INITIAL_DELAY_SECONDS * (1 - factor)),
        )
    if grade == 1:
        factor = min(1, 0.5 + 0.05 * points)
        return max(
            MINIMUM_DELAY_SECONDS,
            round(INITIAL_DELAY_SECONDS * (1 - factor)),
        )

    parameters = [patient_id]
    exclusion = ""
    if exclude_id is not None:
        exclusion = "AND id != ?"
        parameters.append(exclude_id)
    previous = database.execute(
        f"""
        SELECT grade, next_delay_seconds
        FROM measurements
        WHERE patient_profile_id = ? AND status = 'recorded' {exclusion}
        ORDER BY measured_at DESC, id DESC
        LIMIT 2
        """,
        parameters,
    ).fetchall()
    if len(previous) == 2 and all(row["grade"] == 0 for row in previous):
        return INITIAL_DELAY_SECONDS
    if previous:
        return min(
            INITIAL_DELAY_SECONDS,
            previous[0]["next_delay_seconds"] or INITIAL_DELAY_SECONDS,
        )
    return INITIAL_DELAY_SECONDS


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_measurement(database, patient, systolic, diastolic, pulse, symptoms):
    symptom_total = sum(symptoms.values())
    with database:
        database.execute("BEGIN IMMEDIATE")
        latest = database.execute(
            """
            SELECT id, grade, status FROM measurements
            WHERE patient_profile_id = ?
            ORDER BY measured_at DESC, id DESC LIMIT 1
            """,
            (patient["id"],),
        ).fetchone()
        if latest is not None and latest["status"] == "pending_confirmation":
            raise ValueError("A confirmation reading is required first.")

        grade = classify_grade(systolic, diastolic, patient, symptom_total)
        status = (
            "pending_confirmation"
            if latest is not None and latest["grade"] != grade
            else "recorded"
        )
        delay = _next_delay(database, patient["id"], grade, symptom_total)
        measured_at = _timestamp()
        result = database.execute(
            """
            INSERT INTO measurements
                (patient_profile_id, measured_at, grade, status, next_delay_seconds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (patient["id"], measured_at, grade, status, delay),
        )
        measurement_id = result.lastrowid
        database.execute(
            """
            INSERT INTO vital_readings
                (measurement_id, reading_kind, systolic, diastolic, pulse, measured_at)
            VALUES (?, 'initial', ?, ?, ?, ?)
            """,
            (measurement_id, systolic, diastolic, pulse, measured_at),
        )
        database.executemany(
            """
            INSERT INTO symptom_entries (measurement_id, symptom_key, intensity)
            VALUES (?, ?, ?)
            """,
            [
                (measurement_id, key, symptoms[key])
                for key in SYMPTOM_KEYS
            ],
        )
    return {
        "id": measurement_id,
        "grade": grade,
        "status": status,
        "next_delay_seconds": delay,
        "pulse_pressure": systolic - diastolic,
        "symptom_total": symptom_total,
    }


def record_confirmation(
    database, patient, measurement_id, systolic, diastolic, pulse
):
    with database:
        database.execute("BEGIN IMMEDIATE")
        measurement = database.execute(
            """
            SELECT id, measured_at, grade, status
            FROM measurements
            WHERE id = ? AND patient_profile_id = ?
            """,
            (measurement_id, patient["id"]),
        ).fetchone()
        if measurement is None or measurement["status"] != "pending_confirmation":
            raise LookupError("Pending measurement not found.")

        symptom_total = database.execute(
            """
            SELECT COALESCE(SUM(intensity), 0)
            FROM symptom_entries WHERE measurement_id = ?
            """,
            (measurement_id,),
        ).fetchone()[0]
        grade = classify_grade(systolic, diastolic, patient, symptom_total)
        delay = _next_delay(
            database,
            patient["id"],
            grade,
            symptom_total,
            exclude_id=measurement_id,
        )
        measured_at = _timestamp()
        updated = database.execute(
            """
            UPDATE measurements
            SET grade = ?, status = 'recorded', next_delay_seconds = ?
            WHERE id = ? AND patient_profile_id = ?
              AND status = 'pending_confirmation'
            """,
            (grade, delay, measurement_id, patient["id"]),
        )
        if updated.rowcount != 1:
            raise LookupError("Pending measurement not found.")
        database.execute(
            """
            INSERT INTO vital_readings
                (measurement_id, reading_kind, systolic, diastolic, pulse, measured_at)
            VALUES (?, 'confirmation', ?, ?, ?, ?)
            """,
            (measurement_id, systolic, diastolic, pulse, measured_at),
        )
    return {
        "id": measurement_id,
        "grade": grade,
        "status": "recorded",
        "next_delay_seconds": delay,
        "pulse_pressure": systolic - diastolic,
        "symptom_total": symptom_total,
    }
