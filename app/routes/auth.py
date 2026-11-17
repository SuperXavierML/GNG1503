import sqlite3

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import get_db


auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        error = None

        if not email or "@" not in email or any(char.isspace() for char in email):
            error = "email_required"
        elif len(password) < 8:
            error = "password_minimum"

        if error is None:
            try:
                database = get_db()
                database.execute(
                    """
                    INSERT INTO users (email, display_name, password_hash, role)
                    VALUES (?, ?, ?, 'doctor')
                    """,
                    (
                        email,
                        email.split("@", 1)[0],
                        generate_password_hash(password),
                    ),
                )
                database.commit()
                flash("doctor_account_created")
                return redirect(url_for("auth.login"))
            except sqlite3.IntegrityError:
                get_db().rollback()
                error = "email_exists"

        flash(error, "error")

    return render_template("auth/register.html")


@auth.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        session.clear()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            """
            SELECT id, display_name, email, password_hash, role,
                   preferred_language, theme_preference
            FROM users WHERE email = ?
            """,
            (email,),
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("invalid_login", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_role"] = user["role"]
            session["display_name"] = (
                user["display_name"] or user["email"].split("@", 1)[0]
            )
            session["language"] = user["preferred_language"]
            session["theme"] = user["theme_preference"]
            if user["role"] == "doctor":
                return redirect(url_for("doctor.dashboard"))
            return redirect(url_for("patient.dashboard"))

    return render_template("auth/login.html")


@auth.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("main.home"))
