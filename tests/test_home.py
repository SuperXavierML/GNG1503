import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.database import initialize_database


class HomePageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.database_path),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_home_page_is_public_and_does_not_initialize_database(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Solutions SPHM", response.data)
        self.assertIn(b"Make blood pressure tracking easier to follow.", response.data)
        self.assertIn(b"For patients", response.data)
        self.assertIn(b"For doctors", response.data)
        self.assertFalse(self.database_path.exists())

    def test_database_initialization_creates_parent_and_file(self):
        initialize_database(self.app)

        self.assertTrue(self.database_path.is_file())

    def test_public_home_uses_selected_french_language(self):
        with self.client.session_transaction() as session:
            session["language"] = "fr"

        response = self.client.get("/")

        self.assertIn(b'<html lang="fr">', response.data)
        self.assertIn("Faciliter le suivi".encode("utf-8"), response.data)


if __name__ == "__main__":
    unittest.main()
