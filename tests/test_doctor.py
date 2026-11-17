import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, initialize_database
from app.services.patient_history import get_patient_history
from app.services.patient_linking import issue_access_code
from app.services.risk_assessment import save_risk_assessment


class DoctorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "doctor.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.database_path),
            }
        )
        initialize_database(self.app)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf_token(self):
        with self.client.session_transaction() as session:
            token = session.get("csrf_token")
        if token is None:
            raise AssertionError("Load a form before requesting its CSRF token.")
        return token

    def create_doctor(self, email="doctor@example.test"):
        with self.app.app_context():
            database = get_db()
            result = database.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (?, ?, 'doctor')
                """,
                (email, generate_password_hash("test-password")),
            )
            database.commit()
            return result.lastrowid

    def create_patient(self, doctor_id, status="ready", name="Patient One"):
        with self.app.app_context():
            database = get_db()
            result = database.execute(
                """
                INSERT INTO patient_profiles
                    (doctor_id, display_name, profile_status, risk_score,
                     systolic_threshold, diastolic_threshold)
                VALUES (?, ?, ?, 1, 140, 90)
                """,
                (doctor_id, name, status),
            )
            database.commit()
            return result.lastrowid

    def sign_in(self, email="doctor@example.test", password="test-password"):
        self.client.get("/auth/login")
        response = self.client.post(
            "/auth/login",
            data={
                "csrf_token": self.csrf_token(),
                "email": email,
                "password": password,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

    def test_registration_login_and_doctor_route_protection(self):
        self.assertEqual(self.client.get("/doctor/").status_code, 302)

        self.client.get("/auth/register")
        response = self.client.post(
            "/auth/register",
            data={
                "csrf_token": self.csrf_token(),
                "email": "new-doctor@example.test",
                "password": "safe-test-password",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            user = get_db().execute(
                "SELECT role, password_hash FROM users WHERE email = ?",
                ("new-doctor@example.test",),
            ).fetchone()
        self.assertEqual(user["role"], "doctor")
        self.assertNotEqual(user["password_hash"], "safe-test-password")

        self.sign_in("new-doctor@example.test", "safe-test-password")
        response = self.client.get("/doctor/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Doctor dashboard", response.data)

    def test_csrf_rejects_state_changing_post(self):
        self.client.get("/auth/register")
        response = self.client.post(
            "/auth/register",
            data={"email": "doctor@example.test", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 400)

    def test_risk_assessment_persists_results_and_24_hour_initial_delay(self):
        doctor_id = self.create_doctor()
        patient_id = self.create_patient(
            doctor_id, status="pending_assessment", name="Higher-risk patient"
        )
        no_risk_patient_id = self.create_patient(
            doctor_id, status="pending_assessment", name="No-risk patient"
        )
        with self.app.app_context():
            database = get_db()
            save_risk_assessment(
                database,
                doctor_id,
                patient_id,
                "approved-questionnaire-v1",
                {"question_a": "answer"},
                2.5,
                125,
                75,
            )
            save_risk_assessment(
                database,
                doctor_id,
                no_risk_patient_id,
                "approved-questionnaire-v1",
                {"question_a": "answer"},
                0,
                140,
                90,
            )
            profile = database.execute(
                """
                SELECT profile_status, risk_score, systolic_threshold,
                       diastolic_threshold, initial_delay_seconds
                FROM patient_profiles WHERE id = ?
                """,
                (patient_id,),
            ).fetchone()
            no_risk_delay = database.execute(
                "SELECT initial_delay_seconds FROM patient_profiles WHERE id = ?",
                (no_risk_patient_id,),
            ).fetchone()["initial_delay_seconds"]
            answer = database.execute(
                """
                SELECT answer_value FROM risk_answers
                JOIN risk_assessments ON risk_assessments.id = risk_answers.assessment_id
                WHERE risk_assessments.patient_profile_id = ?
                """,
                (patient_id,),
            ).fetchone()

        self.assertEqual(profile["profile_status"], "ready")
        self.assertEqual(profile["initial_delay_seconds"], 24 * 60 * 60)
        self.assertEqual(profile["systolic_threshold"], 125)
        self.assertEqual(profile["diastolic_threshold"], 75)
        self.assertEqual(no_risk_delay, 24 * 60 * 60)
        self.assertEqual(answer["answer_value"], '"answer"')

    def test_risk_assessment_rejects_thresholds_outside_specified_extremes(self):
        doctor_id = self.create_doctor()
        patient_id = self.create_patient(
            doctor_id, status="pending_assessment"
        )
        with self.app.app_context():
            database = get_db()
            with self.assertRaises(ValueError):
                save_risk_assessment(
                    database,
                    doctor_id,
                    patient_id,
                    "approved-questionnaire-v1",
                    {"question_a": "answer"},
                    1,
                    141,
                    90,
                )
            count = database.execute(
                "SELECT COUNT(*) FROM risk_assessments"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_link_code_is_one_time_and_stored_as_a_hash(self):
        doctor_id = self.create_doctor()
        patient_id = self.create_patient(doctor_id)
        self.sign_in()

        self.client.get(f"/doctor/patients/{patient_id}")
        response = self.client.post(
            f"/doctor/patients/{patient_id}/access-code",
            data={"csrf_token": self.csrf_token()},
            follow_redirects=True,
        )
        match = re.search(rb"<code>([^<]+)</code>", response.data)
        self.assertIsNotNone(match)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        code = match.group(1).decode("utf-8")
        with self.client.session_transaction() as session:
            self.assertNotIn("issued_access_code", session)

        self.client.get("/link")
        response = self.client.post(
            "/link",
            data={
                "csrf_token": self.csrf_token(),
                "code": code,
                "email": "patient@example.test",
                "password": "patient-password",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Your account is linked", response.data)

        with self.app.app_context():
            database = get_db()
            profile = database.execute(
                "SELECT patient_user_id, profile_status FROM patient_profiles WHERE id = ?",
                (patient_id,),
            ).fetchone()
            invite = database.execute(
                "SELECT code_hash, consumed_at FROM patient_invites WHERE patient_profile_id = ?",
                (patient_id,),
            ).fetchone()
        self.assertIsNotNone(profile["patient_user_id"])
        self.assertEqual(profile["profile_status"], "linked")
        self.assertNotEqual(invite["code_hash"], code)
        self.assertIsNotNone(invite["consumed_at"])

        self.client.get("/link")
        response = self.client.post(
            "/link",
            data={
                "csrf_token": self.csrf_token(),
                "code": code,
                "email": "second-patient@example.test",
                "password": "patient-password",
            },
        )
        self.assertIn(b"invalid, expired, or already used", response.data)

    def test_patient_history_gaps_notes_compare_and_ownership(self):
        doctor_id = self.create_doctor()
        other_doctor_id = self.create_doctor("other@example.test")
        patient_id = self.create_patient(doctor_id)
        first_id, second_id = self.add_sample_measurements(patient_id)
        self.add_confirmation_reading(first_id)
        self.sign_in()

        response = self.client.get(f"/doctor/patients/{patient_id}?range=week")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"id=\"blood-pressure-chart\"", response.data)
        self.assertIn(b"id=\"symptom-chart\"", response.data)

        with self.app.app_context():
            database = get_db()
            profile = database.execute(
                "SELECT * FROM patient_profiles WHERE id = ?",
                (patient_id,),
            ).fetchone()
            history = get_patient_history(database, profile, "week")
        headache = next(
            item for item in history["symptom_datasets"]
            if item["key"] == "malDeTete"
        )
        self.assertEqual(headache["data"], [3, None])
        self.assertEqual(history["measurements"][0]["systolic"], 150)
        self.assertEqual(history["summaries"]["pulse"]["minimum"], 73)
        self.assertEqual(history["summaries"]["pulse"]["maximum"], 74)

        self.client.get(f"/doctor/patients/{patient_id}")
        response = self.client.post(
            f"/doctor/patients/{patient_id}/notes",
            data={"csrf_token": self.csrf_token(), "note": "Follow-up note"},
            follow_redirects=True,
        )
        self.assertIn(b"Follow-up note", response.data)

        response = self.client.get(
            f"/doctor/patients/{patient_id}?first={first_id}&second={second_id}"
        )
        self.assertIn(b"Selected measurements", response.data)
        self.assertIn(b'id="measurement-comparison-chart"', response.data)
        self.assertIn(b"Difference (later - earlier)", response.data)
        self.assertIn(b"-12 mmHg", response.data)
        self.assertIn(b"-6 mmHg", response.data)
        self.assertIn(b"+1 bpm", response.data)

        with self.app.app_context():
            database = get_db()
            database.execute(
                "UPDATE patient_profiles SET doctor_id = ? WHERE id = ?",
                (other_doctor_id, patient_id),
            )
            database.commit()
        self.assertEqual(
            self.client.get(f"/doctor/patients/{patient_id}").status_code,
            404,
        )

    def test_comparison_preselects_latest_readings_and_allows_same_day(self):
        doctor_id = self.create_doctor()
        patient_id = self.create_patient(doctor_id)
        first_id, second_id = self.add_sample_measurements(patient_id)
        same_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.app.app_context():
            database = get_db()
            database.execute(
                "UPDATE measurements SET measured_at = ? WHERE id IN (?, ?)",
                (same_time, first_id, second_id),
            )
            database.commit()
        self.sign_in()

        response = self.client.get(f"/doctor/patients/{patient_id}")

        self.assertIn(f'value="{second_id}" selected'.encode("utf-8"), response.data)
        self.assertIn(f'value="{first_id}" selected'.encode("utf-8"), response.data)
        response = self.client.get(
            f"/doctor/patients/{patient_id}?first={first_id}&second={second_id}"
        )
        self.assertIn(b'id="measurement-comparison-chart"', response.data)

    def test_settings_persist_french_preference(self):
        doctor_id = self.create_doctor()
        self.sign_in()
        self.client.get("/doctor/settings")
        response = self.client.post(
            "/doctor/settings",
            data={
                "csrf_token": self.csrf_token(),
                "language": "fr",
                "theme": "dark",
            },
            follow_redirects=True,
        )
        self.assertIn("Paramètres".encode("utf-8"), response.data)
        self.assertIn(b'<body data-theme="dark"', response.data)
        with self.app.app_context():
            preferences = get_db().execute(
                "SELECT preferred_language, theme_preference FROM users WHERE id = ?",
                (doctor_id,),
            ).fetchone()
        self.assertEqual(preferences["preferred_language"], "fr")
        self.assertEqual(preferences["theme_preference"], "dark")

    def test_dashboard_shows_and_acknowledges_only_stored_alerts(self):
        doctor_id = self.create_doctor()
        patient_id = self.create_patient(doctor_id)
        with self.app.app_context():
            database = get_db()
            alert = database.execute(
                """
                INSERT INTO alerts (patient_profile_id, grade, reason)
                VALUES (?, 2, 'Test alert')
                """,
                (patient_id,),
            )
            database.commit()
            alert_id = alert.lastrowid

        self.sign_in()
        response = self.client.get("/doctor/")
        self.assertIn(b"Test alert", response.data)
        self.client.post(
            f"/doctor/alerts/{alert_id}/acknowledge",
            data={"csrf_token": self.csrf_token()},
            follow_redirects=True,
        )
        response = self.client.get("/doctor/")
        self.assertIn(b"There are no new alerts.", response.data)

        with self.app.app_context():
            acknowledged_at = get_db().execute(
                "SELECT acknowledged_at FROM alerts WHERE id = ?",
                (alert_id,),
            ).fetchone()["acknowledged_at"]
        self.assertIsNotNone(acknowledged_at)

    def test_patient_draft_waits_for_approved_assessment_before_linking(self):
        self.create_doctor()
        self.sign_in()
        self.client.get("/doctor/patients/new")
        response = self.client.post(
            "/doctor/patients/new",
            data={
                "csrf_token": self.csrf_token(),
                "display_name": "Draft Patient",
            },
            follow_redirects=True,
        )
        self.assertIn(
            b"Risk questionnaire and approved scoring rules are required",
            response.data,
        )
        with self.app.app_context():
            database = get_db()
            patient = database.execute(
                """
                SELECT id, profile_status, initial_delay_seconds
                FROM patient_profiles WHERE display_name = ?
                """,
                ("Draft Patient",),
            ).fetchone()
        self.assertEqual(patient["profile_status"], "pending_assessment")
        self.assertEqual(patient["initial_delay_seconds"], 24 * 60 * 60)

        response = self.client.post(
            f"/doctor/patients/{patient['id']}/access-code",
            data={"csrf_token": self.csrf_token()},
            follow_redirects=True,
        )
        self.assertIn(b"Complete the approved risk assessment", response.data)

    def test_doctor_questionnaire_activates_profile_before_code_issue(self):
        self.create_doctor()
        self.sign_in()
        self.client.get("/doctor/patients/new")
        self.client.post(
            "/doctor/patients/new",
            data={
                "csrf_token": self.csrf_token(),
                "display_name": "Assessed Patient",
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            patient_id = get_db().execute(
                "SELECT id FROM patient_profiles WHERE display_name = ?",
                ("Assessed Patient",),
            ).fetchone()["id"]

        self.client.get(f"/doctor/patients/{patient_id}/assessment")
        response = self.client.post(
            f"/doctor/patients/{patient_id}/assessment",
            data={
                "csrf_token": self.csrf_token(),
                "age_years": "40",
                "height_cm": "160",
                "weight_kg": "60",
                "alcohol_standard_drinks_per_week": "2",
                "current_smoker": "no",
                "pregnant": "not_applicable",
                "cardiovascular_disease": "no",
                "stroke_tia_history": "no",
                "premature_family_history": "no",
                "chronic_kidney_disease": "no",
                "diabetes_type": "none",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Risk assessment saved.", response.data)

        with self.app.app_context():
            database = get_db()
            profile = database.execute(
                """
                SELECT profile_status, systolic_threshold, diastolic_threshold,
                       initial_delay_seconds
                FROM patient_profiles WHERE id = ?
                """,
                (patient_id,),
            ).fetchone()
            answer_count = database.execute(
                """
                SELECT COUNT(*) FROM risk_answers
                JOIN risk_assessments ON risk_assessments.id = risk_answers.assessment_id
                WHERE risk_assessments.patient_profile_id = ?
                """,
                (patient_id,),
            ).fetchone()[0]
        self.assertEqual(profile["profile_status"], "ready")
        self.assertEqual(profile["systolic_threshold"], 140)
        self.assertEqual(profile["diastolic_threshold"], 90)
        self.assertEqual(profile["initial_delay_seconds"], 24 * 60 * 60)
        self.assertEqual(answer_count, 14)

    def test_expired_patient_invite_cannot_be_redeemed(self):
        doctor_id = self.create_doctor()
        patient_id = self.create_patient(doctor_id)
        with self.app.app_context():
            database = get_db()
            code = issue_access_code(database, doctor_id, patient_id)
            database.execute(
                """
                UPDATE patient_invites
                SET expires_at = '2000-01-01T00:00:00Z'
                WHERE patient_profile_id = ?
                """,
                (patient_id,),
            )
            database.commit()

        self.client.get("/link")
        response = self.client.post(
            "/link",
            data={
                "csrf_token": self.csrf_token(),
                "code": code,
                "email": "expired@example.test",
                "password": "patient-password",
            },
            follow_redirects=True,
        )
        self.assertIn(b"invalid, expired, or already used", response.data)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) FROM users WHERE role = 'patient'"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def add_sample_measurements(self, patient_id):
        current = datetime.now(timezone.utc)
        with self.app.app_context():
            database = get_db()
            ids = []
            for days_ago, systolic, diastolic, pulse in (
                (2, 145, 95, 70),
                (1, 138, 88, 74),
            ):
                measured_at = (current - timedelta(days=days_ago)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                measurement = database.execute(
                    """
                    INSERT INTO measurements
                        (patient_profile_id, measured_at, grade, status)
                    VALUES (?, ?, 1, 'recorded')
                    """,
                    (patient_id, measured_at),
                )
                measurement_id = measurement.lastrowid
                ids.append(measurement_id)
                database.execute(
                    """
                    INSERT INTO vital_readings
                        (measurement_id, reading_kind, systolic, diastolic, pulse, measured_at)
                    VALUES (?, 'initial', ?, ?, ?, ?)
                    """,
                    (measurement_id, systolic, diastolic, pulse, measured_at),
                )
            database.execute(
                """
                INSERT INTO symptom_entries (measurement_id, symptom_key, intensity)
                VALUES (?, 'malDeTete', 3)
                """,
                (ids[0],),
            )
            database.commit()
        return ids

    def add_confirmation_reading(self, measurement_id):
        measured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.app.app_context():
            database = get_db()
            database.execute(
                """
                INSERT INTO vital_readings
                    (measurement_id, reading_kind, systolic, diastolic, pulse, measured_at)
                VALUES (?, 'confirmation', 150, 94, 73, ?)
                """,
                (measurement_id, measured_at),
            )
            database.commit()


if __name__ == "__main__":
    unittest.main()
