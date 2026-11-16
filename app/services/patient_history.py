from app.repositories.doctor import list_notes


TIMEFRAMES = {
    "week": "-7 days",
    "two_weeks": "-14 days",
    "month": "-1 month",
    "six_months": "-6 months",
}

SYMPTOMS = (
    ("malDeTete", "symptom_headache"),
    ("vertige", "symptom_dizziness"),
    ("visionFloue", "symptom_blurred_vision"),
    ("essoufflement", "symptom_shortness_of_breath"),
    ("saignementDeNez", "symptom_nosebleed"),
    ("fatigue", "symptom_fatigue"),
    ("confusion", "symptom_confusion"),
    ("perteDeBalan", "symptom_loss_of_balance"),
)


def get_patient_history(database, patient, timeframe):
    interval = TIMEFRAMES.get(timeframe, TIMEFRAMES["week"])
    measurements = [
        dict(row)
        for row in database.execute(
            """
            SELECT m.id, m.measured_at, m.grade, m.next_delay_seconds,
                   COALESCE(c.systolic, i.systolic) AS systolic,
                   COALESCE(c.diastolic, i.diastolic) AS diastolic,
                   COALESCE(c.pulse, i.pulse) AS pulse,
                   COALESCE(c.systolic, i.systolic)
                       - COALESCE(c.diastolic, i.diastolic) AS pulse_pressure
            FROM measurements AS m
            LEFT JOIN vital_readings AS i
                ON i.measurement_id = m.id AND i.reading_kind = 'initial'
            LEFT JOIN vital_readings AS c
                ON c.measurement_id = m.id AND c.reading_kind = 'confirmation'
            WHERE m.patient_profile_id = ?
              AND m.measured_at >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)
            ORDER BY m.measured_at, m.id
            """,
            (patient["id"], interval),
        ).fetchall()
    ]
    symptom_rows = database.execute(
        """
        SELECT s.measurement_id, s.symptom_key, s.intensity
        FROM symptom_entries AS s
        JOIN measurements AS m ON m.id = s.measurement_id
        WHERE m.patient_profile_id = ?
          AND m.measured_at >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)
        """,
        (patient["id"], interval),
    ).fetchall()

    labels = [row["measured_at"] for row in measurements]
    symptom_values = {key: {} for key, _ in SYMPTOMS}
    for row in symptom_rows:
        symptom_values[row["symptom_key"]][row["measurement_id"]] = row["intensity"]

    datasets = [
        {
            "key": key,
            "label_key": label,
            "data": [
                symptom_values[key].get(row["id"])
                for row in measurements
            ],
        }
        for key, label in SYMPTOMS
    ]

    def values(field):
        return [row[field] for row in measurements if row[field] is not None]

    summaries = {}
    for field in ("systolic", "diastolic", "pulse_pressure", "pulse"):
        observed = values(field)
        summaries[field] = {
            "minimum": min(observed) if observed else None,
            "maximum": max(observed) if observed else None,
        }

    return {
        "measurements": measurements,
        "labels": labels,
        "symptom_datasets": datasets,
        "summaries": summaries,
        "notes": list_notes(database, patient["id"]),
        "threshold": {
            "systolic": patient["systolic_threshold"],
            "diastolic": patient["diastolic_threshold"],
        },
    }
