import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.database import get_db, initialize_database


class DatabaseSchemaTests(unittest.TestCase):
    def test_initialization_is_repeatable_and_records_schema_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(Path(temp_dir) / "nested" / "test.sqlite3"),
                }
            )

            initialize_database(app)
            initialize_database(app)

            connection = sqlite3.connect(app.config["DATABASE"])
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(users)")
                }
            finally:
                connection.close()

            self.assertEqual(version, 2)
            self.assertTrue(
                {
                    "users",
                    "patient_profiles",
                    "patient_invites",
                    "risk_assessments",
                    "risk_answers",
                    "measurements",
                    "vital_readings",
                    "symptom_entries",
                    "alerts",
                    "doctor_notes",
                }.issubset(tables)
            )
            self.assertIn("theme_preference", columns)

    def test_first_database_access_migrates_version_one_without_data_loss(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "version-one.sqlite3"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    preferred_language TEXT NOT NULL DEFAULT 'en',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES ('patient@example.test', 'hash', 'patient')
                """
            )
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
            connection.close()

            app = create_app(
                {"TESTING": True, "DATABASE": str(database_path)}
            )
            with app.app_context():
                database = get_db()
                version = database.execute("PRAGMA user_version").fetchone()[0]
                user = database.execute(
                    "SELECT email, theme_preference FROM users WHERE id = 1"
                ).fetchone()

            self.assertEqual(version, 2)
            self.assertEqual(
                (user["email"], user["theme_preference"]),
                ("patient@example.test", "light"),
            )

    def test_flask_cli_initializes_database_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "cli.sqlite3"
            app = create_app(
                {"TESTING": True, "DATABASE": str(database_path)}
            )

            result = app.test_cli_runner().invoke(args=["init-db"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(database_path.is_file())


if __name__ == "__main__":
    unittest.main()
