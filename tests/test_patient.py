import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, initialize_database
from app.repositories.doctor import create_draft_patient
from app.services.patient_linking import issue_access_code
from app.services.risk_assessment import save_risk_assessment


class PatientWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(Path(self.temp_dir.name) / "patient.sqlite3"),
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

    def create_doctor(self):
        with self.app.app_context():
            database = get_db()
            result = database.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES ('doctor@example.test', ?, 'doctor')
                """,
                (generate_password_hash("doctor-password"),),
            )
            database.commit()
            return result.lastrowid

    def create_prepared_profile(self, doctor_id):
        with self.app.app_context():
            database = get_db()
            patient_id = create_draft_patient(
                database, doctor_id, "Patient One"
            )
            save_risk_assessment(
                database,
                doctor_id,
                patient_id,
                "test-questionnaire",
                {"test_answer": "saved"},
                0,
                140,
                90,
            )
            code = issue_access_code(database, doctor_id, patient_id)
        return patient_id, code

    def link_patient(self, email="patient@example.test"):
        doctor_id = self.create_doctor()
        patient_id, code = self.create_prepared_profile(doctor_id)
        self.client.get("/link")
        response = self.client.post(
            "/link",
            data={
                "csrf_token": self.csrf_token(),
                "code": code,
                "email": email,
                "password": "patient-password",
            },
            follow_redirects=True,
        )
        return doctor_id, patient_id, response

    @staticmethod
    def measurement_form(systolic, diastolic, pulse=72):
        values = {
            "systolic": str(systolic),
            "diastolic": str(diastolic),
            "pulse": str(pulse),
        }
        values.update(
            {
                key: "0"
                for key in (
                    "malDeTete",
                    "vertige",
                    "visionFloue",
                    "essoufflement",
                    "saignementDeNez",
                    "fatigue",
                    "confusion",
                    "perteDeBalan",
                )
            }
        )
        return values

    def test_account_creation_measurement_confirmation_and_history(self):
        _, patient_id, response = self.link_patient()
        self.assertIn(b"Your account is linked", response.data)
        self.assertIn(b"measurement-countdown", response.data)

        self.client.get("/patient/measurements/new")
        first = self.client.post(
            "/patient/measurements/new",
            data={
                "csrf_token": self.csrf_token(),
                **self.measurement_form(120, 80),
            },
            follow_redirects=True,
        )
        self.assertEqual(first.status_code, 200)

        self.client.get("/patient/measurements/new")
        concerning = self.client.post(
            "/patient/measurements/new",
            data={
                "csrf_token": self.csrf_token(),
                **self.measurement_form(145, 95),
            },
            follow_redirects=True,
        )
        self.assertIn(b"Confirm reading", concerning.data)

        with self.app.app_context():
            pending = get_db().execute(
                """
                SELECT id, status, grade FROM measurements
                WHERE patient_profile_id = ? ORDER BY id DESC LIMIT 1
                """,
                (patient_id,),
            ).fetchone()
        self.assertEqual(pending["status"], "pending_confirmation")
        self.assertEqual(pending["grade"], 1)

        self.client.get(f"/patient/measurements/{pending['id']}/confirm")
        confirmation = self.client.post(
            f"/patient/measurements/{pending['id']}/confirm",
            data={
                "csrf_token": self.csrf_token(),
                "systolic": "146",
                "diastolic": "94",
                "pulse": "74",
            },
            follow_redirects=True,
        )
        self.assertEqual(confirmation.status_code, 200)

        with self.app.app_context():
            database = get_db()
            readings = database.execute(
                "SELECT COUNT(*) FROM vital_readings"
            ).fetchone()[0]
            symptoms = database.execute(
                """
                SELECT COUNT(*) FROM symptom_entries
                JOIN measurements ON measurements.id = symptom_entries.measurement_id
                WHERE measurements.patient_profile_id = ?
                """,
                (patient_id,),
            ).fetchone()[0]
            finalized = database.execute(
                "SELECT status, next_delay_seconds FROM measurements WHERE id = ?",
                (pending["id"],),
            ).fetchone()
        self.assertEqual(readings, 3)
        self.assertEqual(symptoms, 16)
        self.assertEqual(finalized["status"], "recorded")
        self.assertEqual(finalized["next_delay_seconds"], 12 * 60 * 60)

        history = self.client.get("/patient/history?range=month")
        self.assertEqual(history.status_code, 200)
        self.assertIn(b"id=\"blood-pressure-chart\"", history.data)
        self.assertIn(b"id=\"symptom-chart\"", history.data)

    def test_patient_settings_save_language_and_theme(self):
        _, _, response = self.link_patient()
        self.assertEqual(response.status_code, 200)
        self.client.get("/patient/settings")
        response = self.client.post(
            "/patient/settings",
            data={
                "csrf_token": self.csrf_token(),
                "language": "fr",
                "theme": "dark",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<html lang="fr">', response.data)
        self.assertIn(b'<body data-theme="dark">', response.data)

    def test_patient_routes_do_not_expose_another_profiles_confirmation(self):
        doctor_id, patient_id, response = self.link_patient()
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            database = get_db()
            other_profile = create_draft_patient(
                database, doctor_id, "Other Patient"
            )
            result = database.execute(
                """
                INSERT INTO measurements
                    (patient_profile_id, measured_at, grade, status)
                VALUES (?, '2026-01-01T00:00:00Z', 1, 'pending_confirmation')
                """,
                (other_profile,),
            )
            database.commit()
            other_measurement_id = result.lastrowid

        response = self.client.get(
            f"/patient/measurements/{other_measurement_id}/confirm"
        )
        self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            linked = get_db().execute(
                "SELECT patient_user_id FROM patient_profiles WHERE id = ?",
                (patient_id,),
            ).fetchone()
        self.assertIsNotNone(linked["patient_user_id"])

    def test_patient_login_redirects_to_patient_dashboard(self):
        self.link_patient()
        self.client.post(
            "/auth/logout",
            data={"csrf_token": self.csrf_token()},
        )
        self.client.get("/auth/login")
        response = self.client.post(
            "/auth/login",
            data={
                "csrf_token": self.csrf_token(),
                "email": "patient@example.test",
                "password": "patient-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/patient/")

    def test_invalid_measurement_is_not_persisted(self):
        self.link_patient()
        self.client.get("/patient/measurements/new")
        form = self.measurement_form(120, 80)
        form["malDeTete"] = "9"
        response = self.client.post(
            "/patient/measurements/new",
            data={
                "csrf_token": self.csrf_token(),
                **form,
            },
            follow_redirects=True,
        )
        self.assertIn(b"Enter positive whole-number vital readings", response.data)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) FROM measurements"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_missing_symptom_answer_is_not_defaulted_to_zero(self):
        self.link_patient()
        self.client.get("/patient/measurements/new")
        response = self.client.post(
            "/patient/measurements/new",
            data={
                "csrf_token": self.csrf_token(),
                "systolic": "120",
                "diastolic": "80",
                "pulse": "70",
                "malDeTete": "0",
            },
            follow_redirects=True,
        )
        self.assertIn(b"for every symptom", response.data)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) FROM measurements"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_normal_readings_reset_delay_and_grade_three_uses_five_minutes(self):
        _, patient_id, _ = self.link_patient()

        self.client.get("/patient/measurements/new")
        first = self.client.post(
            "/patient/measurements/new",
            data={
                "csrf_token": self.csrf_token(),
                **self.measurement_form(145, 95),
            },
            follow_redirects=True,
        )
        self.assertEqual(first.status_code, 200)

        self.client.get("/patient/measurements/new")
        changed_grade = self.client.post(
            "/patient/measurements/new",
            data={
                "csrf_token": self.csrf_token(),
                **self.measurement_form(120, 80),
            },
            follow_redirects=True,
        )
        self.assertIn(b"Confirm reading", changed_grade.data)

        with self.app.app_context():
            pending_id = get_db().execute(
                """
                SELECT id FROM measurements
                WHERE patient_profile_id = ? AND status = 'pending_confirmation'
                """,
                (patient_id,),
            ).fetchone()["id"]
        self.client.get(f"/patient/measurements/{pending_id}/confirm")
        self.client.post(
            f"/patient/measurements/{pending_id}/confirm",
            data={
                "csrf_token": self.csrf_token(),
                "systolic": "120",
                "diastolic": "80",
                "pulse": "72",
            },
            follow_redirects=True,
        )

        for _ in range(2):
            self.client.get("/patient/measurements/new")
            self.client.post(
                "/patient/measurements/new",
                data={
                    "csrf_token": self.csrf_token(),
                    **self.measurement_form(120, 80),
                },
                follow_redirects=True,
            )
        with self.app.app_context():
            normal_delay = get_db().execute(
                """
                SELECT next_delay_seconds FROM measurements
                WHERE patient_profile_id = ?
                ORDER BY measured_at DESC, id DESC LIMIT 1
                """,
                (patient_id,),
            ).fetchone()["next_delay_seconds"]
        self.assertEqual(normal_delay, 24 * 60 * 60)

        self.client.get("/patient/measurements/new")
        grade_three = self.client.post(
            "/patient/measurements/new",
            data={
                "csrf_token": self.csrf_token(),
                **self.measurement_form(180, 110),
            },
            follow_redirects=True,
        )
        self.assertIn(b"Confirm reading", grade_three.data)
        with self.app.app_context():
            severe = get_db().execute(
                """
                SELECT id, next_delay_seconds FROM measurements
                WHERE patient_profile_id = ? AND status = 'pending_confirmation'
                """,
                (patient_id,),
            ).fetchone()
        self.assertEqual(severe["next_delay_seconds"], 5 * 60)


if __name__ == "__main__":
    unittest.main()
