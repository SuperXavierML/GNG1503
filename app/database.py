import sqlite3
from pathlib import Path
from threading import Lock

from flask import current_app, g


SCHEMA_VERSION = 2


def get_db():
    if "db" not in g:
        if not current_app.extensions["database_schema_initialized"]:
            with current_app.extensions["database_schema_lock"]:
                if not current_app.extensions["database_schema_initialized"]:
                    initialize_database(current_app)
                    current_app.extensions["database_schema_initialized"] = True

        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path, timeout=10)
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    app.extensions["database_schema_lock"] = Lock()
    app.extensions["database_schema_initialized"] = False


def initialize_database(app):
    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} is newer than "
                f"supported version {SCHEMA_VERSION}."
            )
        if version == 0:
            schema_path = Path(__file__).with_name("schema.sql")
            schema = schema_path.read_text(encoding="utf-8")
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + schema
                + f"\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
            )
        elif version == 1:
            connection.executescript(
                """
                BEGIN IMMEDIATE;
                ALTER TABLE users
                    ADD COLUMN theme_preference TEXT NOT NULL DEFAULT 'light'
                    CHECK (theme_preference IN ('light', 'dark'));
                PRAGMA user_version = 2;
                COMMIT;
                """
            )
    finally:
        connection.close()
