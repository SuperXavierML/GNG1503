import csv
import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, initialize_database
from app.services.patient_history import get_measurement_log, get_patient_analysis


class UIRequirementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(Path(self.temp_dir.name) / "ui.sqlite3"),
            }
        )
        initialize_database(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            database = get_db()
            doctor = database.execute(
                """
                INSERT INTO users (email, display_name, password_hash, role)
                VALUES (?, ?, ?, 'doctor')
                """,
                ("doctor@example.test", "Dr. Example", generate_password_hash("test")),
            )
            patient_user = database.execute(
                """
                INSERT INTO users (email, display_name, password_hash, role)
                VALUES (?, ?, ?, 'patient')
                """,
                ("patient@example.test", "Account Name", generate_password_hash("test")),
            )
            self.doctor_id = doctor.lastrowid
            self.patient_user_id = patient_user.lastrowid
            patient = database.execute(
                """
                INSERT INTO patient_profiles
                    (doctor_id, patient_user_id, display_name, profile_status,
                     systolic_threshold, diastolic_threshold)
                VALUES (?, ?, 'Patient One', 'linked', 140, 90)
                """,
                (self.doctor_id, self.patient_user_id),
            )
            self.patient_id = patient.lastrowid
            database.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def sign_in(self, role):
        user_id = self.patient_user_id if role == "patient" else self.doctor_id
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["user_role"] = role
            session["display_name"] = (
                "Account Name" if role == "patient" else "Dr. Example"
            )
            session["language"] = "en"
            session["theme"] = "light"
            session["csrf_token"] = "ui-test-token"

    def add_measurement(self, days_ago, systolic, diastolic, pulse=70):
        measured_at = (
            datetime.now(timezone.utc) - timedelta(days=days_ago)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.app.app_context():
            database = get_db()
            row = database.execute(
                """
                INSERT INTO measurements
                    (patient_profile_id, measured_at, grade, status)
                VALUES (?, ?, ?, 'recorded')
                """,
                (
                    self.patient_id,
                    measured_at,
                    int(systolic >= 140 or diastolic >= 90),
                ),
            )
            measurement_id = row.lastrowid
            database.execute(
                """
                INSERT INTO vital_readings
                    (measurement_id, reading_kind, systolic, diastolic, pulse, measured_at)
                VALUES (?, 'initial', ?, ?, ?, ?)
                """,
                (measurement_id, systolic, diastolic, pulse, measured_at),
            )
            database.commit()
        return measured_at

    def test_patient_analysis_includes_all_history_and_downloads_csv(self):
        measured_at = self.add_measurement(1, 120, 80)
        self.add_measurement(2, 140, 95)
        self.sign_in("patient")

        legacy_page = self.client.get("/patient/history")
        self.assertEqual(legacy_page.status_code, 302)
        self.assertEqual(legacy_page.headers["Location"], "/patient/analysis")

        page = self.client.get("/patient/analysis")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"All previous measurements", page.data)
        self.assertIn(b"Valid", page.data)
        self.assertIn(b"Not valid", page.data)
        self.assertIn(b"blood-pressure-chart", page.data)
        self.assertIn(b"Compare measurements", page.data)
        self.assertIn(
            f'data-utc-time="{measured_at}"'.encode("utf-8"),
            page.data,
        )

        legacy_csv = self.client.get("/patient/history.csv")
        self.assertEqual(legacy_csv.status_code, 302)
        self.assertEqual(legacy_csv.headers["Location"], "/patient/analysis")

        response = self.client.get("/patient/analysis.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["Content-Type"])
        self.assertIn("attachment", response.headers["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8"))))
        self.assertEqual(len(rows), 3)
        self.assertIn("yes", [row[4] for row in rows])
        self.assertIn("no", [row[4] for row in rows])

    def test_patient_bottom_navigation_omits_measurement_and_history(self):
        self.sign_in("patient")

        dashboard = self.client.get("/patient/")

        navigation = dashboard.data.split(b'<nav class="bottom-navigation"', 1)[1]
        navigation = navigation.split(b"</nav>", 1)[0]
        self.assertNotIn(b">Measure<", navigation)
        self.assertNotIn(b">History<", navigation)
        self.assertIn(b'href="/patient/measurements/new"', dashboard.data)

    def test_dashboard_omits_pulse_pressure_notice_and_keeps_timestamp(self):
        measured_at = self.add_measurement(0, 130, 65)
        self.sign_in("patient")

        response = self.client.get("/patient/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f'data-utc-time="{measured_at}"'.encode("utf-8"),
            response.data,
        )
        self.assertNotIn(b"pulse_pressure_review", response.data)
        self.assertNotIn(b"outside the 20 to 60 mmHg range", response.data)

    def test_analysis_computes_population_statistics_and_previous_period_change(self):
        self.add_measurement(1, 120, 80, 60)
        self.add_measurement(3, 140, 100, 80)
        self.add_measurement(8, 100, 70, 50)
        self.add_measurement(10, 110, 80, 70)
        with self.app.app_context():
            profile = get_db().execute(
                "SELECT * FROM patient_profiles WHERE id = ?",
                (self.patient_id,),
            ).fetchone()
            analysis = get_patient_analysis(get_db(), profile, "week")

        systolic = analysis["statistics"]["systolic"]
        self.assertEqual(systolic["mean"], 130)
        self.assertEqual(systolic["standard_deviation"], 10)
        self.assertEqual(systolic["standard_deviation_percent"], 7.69)
        self.assertEqual(systolic["previous_mean"], 105)
        self.assertEqual(systolic["mean_delta"], 25)
        self.assertEqual(systolic["mean_variation_percent"], 23.81)

        self.sign_in("patient")
        response = self.client.get("/patient/analysis?range=thirty_days")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"30 days", response.data)
        self.assertIn(b"Mean change vs previous period", response.data)
        self.assertIn(b"stat-bars", response.data)
        self.assertNotIn(b"1 month", response.data)
        self.assertNotIn(b"6 months", response.data)

    def test_history_validity_uses_all_normal_measurement_rules(self):
        timestamps = {
            "normal": self.add_measurement(1, 120, 80),
            "pulse_pressure": self.add_measurement(2, 120, 59),
            "symptom_eight": self.add_measurement(3, 120, 80),
            "symptom_nine": self.add_measurement(4, 120, 80),
            "pending": self.add_measurement(5, 120, 80),
        }
        with self.app.app_context():
            database = get_db()
            for name in ("symptom_eight", "symptom_nine"):
                measurement_id = database.execute(
                    "SELECT id FROM measurements WHERE measured_at = ?",
                    (timestamps[name],),
                ).fetchone()["id"]
                symptom_total = 8 if name == "symptom_eight" else 9
                database.executemany(
                    """
                    INSERT INTO symptom_entries
                        (measurement_id, symptom_key, intensity)
                    VALUES (?, ?, ?)
                    """,
                    (
                        (measurement_id, "malDeTete", 5),
                        (measurement_id, "vertige", symptom_total - 5),
                    ),
                )
            database.execute(
                "UPDATE measurements SET status = 'pending_confirmation' WHERE measured_at = ?",
                (timestamps["pending"],),
            )
            database.commit()
            profile = database.execute(
                "SELECT * FROM patient_profiles WHERE id = ?",
                (self.patient_id,),
            ).fetchone()
            validity = {
                row["measured_at"]: row["valid"]
                for row in get_measurement_log(database, profile)
            }

        self.assertTrue(validity[timestamps["normal"]])
        self.assertFalse(validity[timestamps["pulse_pressure"]])
        self.assertTrue(validity[timestamps["symptom_eight"]])
        self.assertFalse(validity[timestamps["symptom_nine"]])
        self.assertFalse(validity[timestamps["pending"]])

    def test_patient_and_doctor_can_exchange_messages_and_search_patients(self):
        self.sign_in("patient")
        response = self.client.post(
            "/patient/messages",
            data={"csrf_token": "ui-test-token", "body": "Hello doctor"},
        )
        self.assertEqual(response.status_code, 302)

        self.sign_in("doctor")
        notification = self.client.get("/doctor/")
        self.assertIn(b'class="message-notification-dot"', notification.data)
        self.assertIn(b'class="patient-unread-dot"', notification.data)
        response = self.client.get("/doctor/messages")
        self.assertIn(b'class="patient-unread-dot"', response.data)
        redirect_response = self.client.get("/doctor/patients?q=Patient")
        self.assertEqual(redirect_response.status_code, 302)
        self.assertEqual(
            redirect_response.headers["Location"],
            "/doctor/?q=Patient#patients",
        )
        response = self.client.get("/doctor/?q=Patient")
        self.assertIn(b'type="search"', response.data)
        self.assertIn(b"Patient One", response.data)
        redirect_response = self.client.get("/doctor/patients?q=missing")
        self.assertEqual(redirect_response.status_code, 302)
        response = self.client.get("/doctor/?q=missing")
        self.assertIn(b"No patients match this search", response.data)
        conversation = self.client.get(
            f"/doctor/patients/{self.patient_id}/messages"
        )
        self.assertNotIn(
            b'class="message-notification-dot"', conversation.data
        )
        with self.app.app_context():
            read_at = get_db().execute(
                "SELECT read_at FROM messages WHERE body = 'Hello doctor'"
            ).fetchone()["read_at"]
        self.assertIsNotNone(read_at)
        response = self.client.post(
            f"/doctor/patients/{self.patient_id}/messages",
            data={"csrf_token": "ui-test-token", "body": "I received your note"},
        )
        self.assertEqual(response.status_code, 302)

        self.sign_in("patient")
        notification = self.client.get("/patient/")
        self.assertIn(b'class="message-notification-dot"', notification.data)
        response = self.client.get("/patient/messages")
        self.assertNotIn(b'class="message-notification-dot"', response.data)
        self.assertIn(b"Hello doctor", response.data)
        self.assertIn(b"I received your note", response.data)

    def test_doctor_patient_history_table_and_csv_include_all_readings(self):
        old_timestamp = self.add_measurement(45, 120, 80)
        self.add_measurement(1, 140, 95)
        self.sign_in("doctor")

        page = self.client.get(f"/doctor/patients/{self.patient_id}?range=week")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b"All previous measurements", page.data)
        self.assertIn(f'data-utc-time="{old_timestamp}"'.encode(), page.data)

        response = self.client.get(
            f"/doctor/patients/{self.patient_id}/history.csv"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["Content-Type"])
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8"))))
        self.assertEqual(len(rows), 3)

    def test_patient_display_name_is_independent_of_clinical_record_name(self):
        self.sign_in("patient")
        response = self.client.post(
            "/patient/settings",
            data={
                "csrf_token": "ui-test-token",
                "language": "en",
                "theme": "light",
                "display_name": "My Account Name",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            database = get_db()
            account_name = database.execute(
                "SELECT display_name FROM users WHERE id = ?",
                (self.patient_user_id,),
            ).fetchone()["display_name"]
            patient_name = database.execute(
                "SELECT display_name FROM patient_profiles WHERE id = ?",
                (self.patient_id,),
            ).fetchone()["display_name"]
        self.assertEqual(account_name, "My Account Name")
        self.assertEqual(patient_name, "Patient One")

    def test_doctor_can_choose_an_account_display_name(self):
        self.sign_in("doctor")
        response = self.client.post(
            "/doctor/settings",
            data={
                "csrf_token": "ui-test-token",
                "language": "en",
                "theme": "light",
                "display_name": "Care Team",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            name = get_db().execute(
                "SELECT display_name FROM users WHERE id = ?",
                (self.doctor_id,),
            ).fetchone()["display_name"]
        self.assertEqual(name, "Care Team")

    def test_symptom_selection_uses_local_icons_and_descriptive_intensities(self):
        self.sign_in("patient")
        response = self.client.get("/patient/measurements/new")
        self.assertRegex(
            response.data.decode("utf-8"),
            r'<option value="0" selected>0 - Not present</option>',
        )
        self.assertIn(b"1 - Very mild", response.data)
        self.assertIn(b"5 - Very severe", response.data)
        for icon in (
            "activity",
            "rotate-cw",
            "eye-off",
            "wind",
            "droplet",
            "battery-low",
            "brain",
            "move-horizontal",
        ):
            self.assertIn(f"/static/icons/{icon}.svg".encode("utf-8"), response.data)
            asset = self.client.get(f"/static/icons/{icon}.svg")
            try:
                self.assertEqual(asset.status_code, 200)
            finally:
                asset.close()

    def test_doctor_patient_list_shows_the_current_health_grade(self):
        self.add_measurement(0, 120, 80)
        self.sign_in("doctor")

        legacy_page = self.client.get("/doctor/patients")
        self.assertEqual(legacy_page.status_code, 302)
        self.assertEqual(legacy_page.headers["Location"], "/doctor/#patients")
        response = self.client.get("/doctor/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Patient One", response.data)
        self.assertIn(b"Good", response.data)
        navigation = response.data.split(
            b'<nav class="bottom-navigation"', 1
        )[1].split(b"</nav>", 1)[0]
        self.assertNotIn(b">Patients<", navigation)

    def test_doctor_alerts_are_ordered_by_severity_then_oldest_unread(self):
        names = ("Lower severity older", "Higher newer", "Higher older")
        patient_ids = [self.patient_id]
        with self.app.app_context():
            database = get_db()
            database.execute(
                "UPDATE patient_profiles SET display_name = ? WHERE id = ?",
                ("Lower severity older", self.patient_id),
            )
            for name in names[1:]:
                row = database.execute(
                    """
                    INSERT INTO patient_profiles
                        (doctor_id, display_name, profile_status,
                         systolic_threshold, diastolic_threshold)
                    VALUES (?, ?, 'ready', 140, 90)
                    """,
                    (self.doctor_id, name),
                )
                patient_ids.append(row.lastrowid)
            alerts = (
                (patient_ids[0], 1, "2026-01-01 00:00:00"),
                (patient_ids[1], 3, "2026-11-01 00:00:00"),
                (patient_ids[2], 3, "2026-10-01 00:00:00"),
            )
            database.executemany(
                """
                INSERT INTO alerts (patient_profile_id, grade, reason, created_at)
                VALUES (?, ?, 'test alert', ?)
                """,
                alerts,
            )
            database.commit()

        self.sign_in("doctor")
        response = self.client.get("/doctor/")
        positions = [
            response.data.index(name.encode("utf-8"))
            for name in ("Higher older", "Higher newer", "Lower severity older")
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn(
            f'href="/doctor/patients/{patient_ids[2]}"'.encode("utf-8"),
            response.data,
        )


if __name__ == "__main__":
    unittest.main()
