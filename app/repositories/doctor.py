def list_patients(database, doctor_id, search=""):
    statement = """
        SELECT p.id, p.display_name, p.profile_status, p.risk_score,
               p.created_at, COUNT(a.id) AS new_alert_count
        FROM patient_profiles AS p
        LEFT JOIN alerts AS a
            ON a.patient_profile_id = p.id AND a.acknowledged_at IS NULL
        WHERE p.doctor_id = ?
    """
    parameters = [doctor_id]
    search = search.strip()
    if search:
        statement += " AND instr(lower(p.display_name), lower(?)) > 0"
        parameters.append(search)
    statement += """
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """
    return database.execute(
        statement,
        parameters,
    ).fetchall()


def get_patient(database, doctor_id, patient_id):
    return database.execute(
        """
        SELECT id, display_name, profile_status, risk_score,
               systolic_threshold, diastolic_threshold,
               initial_delay_seconds
        FROM patient_profiles
        WHERE id = ? AND doctor_id = ?
        """,
        (patient_id, doctor_id),
    ).fetchone()


def list_unacknowledged_alerts(database, doctor_id):
    return database.execute(
        """
        SELECT a.id, a.grade, a.reason, a.created_at,
               p.id AS patient_id, p.display_name AS patient_name
        FROM alerts AS a
        JOIN patient_profiles AS p ON p.id = a.patient_profile_id
        WHERE p.doctor_id = ? AND a.acknowledged_at IS NULL
        ORDER BY COALESCE(a.grade, 0) DESC, a.created_at ASC, a.id ASC
        """,
        (doctor_id,),
    ).fetchall()


def acknowledge_alert(database, doctor_id, alert_id):
    result = database.execute(
        """
        UPDATE alerts
        SET acknowledged_at = CURRENT_TIMESTAMP
        WHERE id = ? AND patient_profile_id IN (
            SELECT id FROM patient_profiles WHERE doctor_id = ?
        ) AND acknowledged_at IS NULL
        """,
        (alert_id, doctor_id),
    )
    database.commit()
    return result.rowcount == 1


def create_draft_patient(database, doctor_id, display_name):
    result = database.execute(
        """
        INSERT INTO patient_profiles (doctor_id, display_name, profile_status)
        VALUES (?, ?, 'pending_assessment')
        """,
        (doctor_id, display_name),
    )
    database.commit()
    return result.lastrowid


def list_notes(database, patient_id):
    return database.execute(
        """
        SELECT note, noted_at
        FROM doctor_notes
        WHERE patient_profile_id = ?
        ORDER BY noted_at DESC, id DESC
        """,
        (patient_id,),
    ).fetchall()


def create_note(database, doctor_id, patient_id, note):
    database.execute(
        """
        INSERT INTO doctor_notes (patient_profile_id, doctor_id, note)
        VALUES (?, ?, ?)
        """,
        (patient_id, doctor_id, note),
    )
    database.commit()


def get_measurement_pair(database, patient_id, first_id, second_id):
    if first_id == second_id:
        return None
    rows = database.execute(
        """
        SELECT m.id, m.measured_at, m.grade,
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
        WHERE m.patient_profile_id = ? AND m.id IN (?, ?)
        ORDER BY m.measured_at, m.id
        """,
        (patient_id, first_id, second_id),
    ).fetchall()
    if len(rows) != 2:
        return None
    return rows


def list_comparison_measurements(database, patient_id):
    return database.execute(
        """
        SELECT id, measured_at
        FROM measurements
        WHERE patient_profile_id = ?
          AND measured_at >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-6 months')
        ORDER BY measured_at DESC, id DESC
        """,
        (patient_id,),
    ).fetchall()
