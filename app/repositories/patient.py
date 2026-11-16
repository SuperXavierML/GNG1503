def get_linked_patient(database, patient_user_id):
    return database.execute(
        """
        SELECT p.id, p.doctor_id, p.patient_user_id, p.display_name,
               p.profile_status, p.risk_score, p.systolic_threshold,
               p.diastolic_threshold, p.initial_delay_seconds,
               p.updated_at, u.created_at AS patient_created_at
        FROM patient_profiles AS p
        JOIN users AS u ON u.id = p.patient_user_id
        WHERE p.patient_user_id = ? AND u.role = 'patient'
        """,
        (patient_user_id,),
    ).fetchone()


def get_latest_measurement(database, patient_id):
    return database.execute(
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
        ORDER BY m.measured_at DESC, m.id DESC
        LIMIT 1
        """,
        (patient_id,),
    ).fetchone()


def get_owned_measurement(database, patient_id, measurement_id):
    return database.execute(
        """
        SELECT id, measured_at, grade, status, next_delay_seconds
        FROM measurements
        WHERE id = ? AND patient_profile_id = ?
        """,
        (measurement_id, patient_id),
    ).fetchone()
