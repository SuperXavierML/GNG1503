from pathlib import Path
import secrets

from flask import Flask

from app.config import Config
from app.database import (
    init_app as init_database,
    initialize_database,
)
from app.routes.auth import auth
from app.routes.doctor import doctor
from app.routes.main import main
from app.routes.patient import patient
from app.routes.patient_link import patient_link
from app.security import get_csrf_token, protect_csrf
from app.translations import translate


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    if app.config["DATABASE"] is None:
        app.config["DATABASE"] = str(
            Path(app.instance_path) / "hypertension.sqlite3"
        )

    init_database(app)
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(doctor)
    app.register_blueprint(patient)
    app.register_blueprint(patient_link)
    app.before_request(protect_csrf)

    @app.context_processor
    def inject_template_helpers():
        return {
            "t": translate,
            "csrf_token": get_csrf_token,
        }

    @app.cli.command("init-db")
    def init_db_command():
        initialize_database(app)

    return app
