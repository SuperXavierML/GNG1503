from math import sqrt

from app.repositories.doctor import list_notes


TIMEFRAMES = {
    "week": "-7 days",
    "two_weeks": "-14 days",
    "thirty_days": "-30 days",
}
PREVIOUS_TIMEFRAMES = {
    "week": ("-14 days", "-7 days"),
    "two_weeks": ("-28 days", "-14 days"),
    "thirty_days": ("-60 days", "-30 days"),
}
MEASUREMENT_FIELDS = ("systolic", "diastolic", "pulse")

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
SYMPTOM_ICONS = {
    "malDeTete": "activity",
    "vertige": "rotate-cw",
    "visionFloue": "eye-off",
    "essoufflement": "wind",
    "saignementDeNez": "droplet",
    "fatigue": "battery-low",
    "confusion": "brain",
    "perteDeBalan": "move-horizontal",
}


def get_patient_history(database, patient, timeframe):
    interval = TIMEFRAMES.get(timeframe, TIMEFRAMES["week"])
    measurements = [
        dict(row)
        for row in database.execute(
            """
            SELECT m.id, m.measured_at, m.grade, m.status,
                   m.next_delay_seconds,
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
    for measurement in measurements:
        measurement["abnormal_systolic"] = (
            measurement["systolic"] is not None
            and patient["systolic_threshold"] is not None
            and measurement["systolic"] >= patient["systolic_threshold"]
        )
        measurement["abnormal_diastolic"] = (
            measurement["diastolic"] is not None
            and patient["diastolic_threshold"] is not None
            and measurement["diastolic"] >= patient["diastolic_threshold"]
        )
        measurement["abnormal"] = (
            measurement["abnormal_systolic"]
            or measurement["abnormal_diastolic"]
        )
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


def get_measurement_log(database, patient):
    rows = database.execute(
        """
        SELECT m.id, m.measured_at, m.grade, m.status,
               COALESCE(c.systolic, i.systolic) AS systolic,
               COALESCE(c.diastolic, i.diastolic) AS diastolic,
               COALESCE(c.pulse, i.pulse) AS pulse,
               COALESCE(c.systolic, i.systolic)
                   - COALESCE(c.diastolic, i.diastolic) AS pulse_pressure,
               COALESCE((
                   SELECT SUM(s.intensity)
                   FROM symptom_entries AS s
                   WHERE s.measurement_id = m.id
               ), 0) AS symptom_total
        FROM measurements AS m
        LEFT JOIN vital_readings AS i
            ON i.measurement_id = m.id AND i.reading_kind = 'initial'
        LEFT JOIN vital_readings AS c
            ON c.measurement_id = m.id AND c.reading_kind = 'confirmation'
        WHERE m.patient_profile_id = ?
        ORDER BY m.measured_at DESC, m.id DESC
        """,
        (patient["id"],),
    ).fetchall()
    return [
        {
            **dict(row),
            "valid": (
                row["status"] == "recorded"
                and row["grade"] == 0
                and row["systolic"] is not None
                and row["diastolic"] is not None
                and patient["systolic_threshold"] is not None
                and patient["diastolic_threshold"] is not None
                and row["systolic"] < patient["systolic_threshold"]
                and row["diastolic"] < patient["diastolic_threshold"]
                and 20 <= row["pulse_pressure"] <= 60
                and row["symptom_total"] <= 8
            ),
        }
        for row in rows
    ]


def _period_measurements(database, patient_id, start_modifier, end_modifier):
    return database.execute(
        """
        SELECT COALESCE(c.systolic, i.systolic) AS systolic,
               COALESCE(c.diastolic, i.diastolic) AS diastolic,
               COALESCE(c.pulse, i.pulse) AS pulse
        FROM measurements AS m
        LEFT JOIN vital_readings AS i
            ON i.measurement_id = m.id AND i.reading_kind = 'initial'
        LEFT JOIN vital_readings AS c
            ON c.measurement_id = m.id AND c.reading_kind = 'confirmation'
        WHERE m.patient_profile_id = ?
          AND m.measured_at >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)
          AND m.measured_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)
        ORDER BY m.measured_at, m.id
        """,
        (patient_id, start_modifier, end_modifier),
    ).fetchall()


def _statistics(rows, field):
    values = [row[field] for row in rows if row[field] is not None]
    if not values:
        return {
            "count": 0,
            "mean": None,
            "mean_raw": None,
            "minimum": None,
            "maximum": None,
            "standard_deviation": None,
            "standard_deviation_percent": None,
        }
    mean = sum(values) / len(values)
    standard_deviation = sqrt(
        sum((value - mean) ** 2 for value in values) / len(values)
    )
    return {
        "count": len(values),
        "mean": round(mean, 2),
        "mean_raw": mean,
        "minimum": min(values),
        "maximum": max(values),
        "standard_deviation": round(standard_deviation, 2),
        "standard_deviation_percent": (
            round(standard_deviation / abs(mean) * 100, 2)
            if mean
            else None
        ),
    }


def get_patient_analysis(database, patient, timeframe):
    current = get_patient_history(database, patient, timeframe)
    previous_start, previous_end = PREVIOUS_TIMEFRAMES.get(
        timeframe, PREVIOUS_TIMEFRAMES["week"]
    )
    previous_rows = _period_measurements(
        database, patient["id"], previous_start, previous_end
    )
    statistics = {}
    metric_names = (
        "mean",
        "standard_deviation",
        "standard_deviation_percent",
        "mean_variation_percent",
    )
    for field in MEASUREMENT_FIELDS:
        current_stats = _statistics(current["measurements"], field)
        previous_stats = _statistics(previous_rows, field)
        current_mean = current_stats["mean_raw"]
        previous_mean = previous_stats["mean_raw"]
        mean_delta_raw = (
            current_mean - previous_mean
            if current_mean is not None and previous_mean is not None
            else None
        )
        mean_delta = (
            round(mean_delta_raw, 2) if mean_delta_raw is not None else None
        )
        variation = (
            round(mean_delta_raw / abs(previous_mean) * 100, 2)
            if mean_delta_raw is not None and previous_mean
            else None
        )
        current_stats["mean_variation_percent"] = variation
        current_stats["mean_delta"] = mean_delta
        current_stats["previous_mean"] = previous_stats["mean"]
        for metric in metric_names:
            current_value = current_stats.get(metric)
            previous_value = previous_stats.get(metric)
            if metric == "mean_variation_percent":
                current_stats.setdefault("graphs", {})[metric] = {
                    "current": (
                        min(abs(current_value), 100)
                        if current_value is not None
                        else 0
                    ),
                    "previous": 0,
                }
                continue
            scale = max(
                abs(current_value or 0),
                abs(previous_value or 0),
                1,
            )
            current_stats.setdefault("graphs", {})[metric] = {
                "current": round(abs(current_value or 0) / scale * 100, 1),
                "previous": round(abs(previous_value or 0) / scale * 100, 1),
            }
        statistics[field] = current_stats

    return {
        **current,
        "statistics": statistics,
        "previous_period": {
            field: _statistics(previous_rows, field)
            for field in MEASUREMENT_FIELDS
        },
    }
