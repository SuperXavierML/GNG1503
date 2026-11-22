import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.database import get_db
from app.security import establish_user_session
from app.services.patient_linking import redeem_access_code


patient_link = Blueprint("patient_link", __name__)


@patient_link.route("/link", methods=("GET", "POST"))
def link_account():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        code = request.form.get("code", "")
        if not email or "@" not in email or any(char.isspace() for char in email):
            flash("email_required", "error")
        elif len(password) < 8:
            flash("password_minimum", "error")
        else:
            try:
                linked = redeem_access_code(
                    get_db(), code, email, password
                )
            except sqlite3.IntegrityError:
                get_db().rollback()
                linked = False

            if linked:
                patient_user = get_db().execute(
                    """
                    SELECT id, display_name, email, role, preferred_language,
                           theme_preference
                    FROM users WHERE email = ? AND role = 'patient'
                    """,
                    (email,),
                ).fetchone()
                if patient_user is None:
                    raise RuntimeError(
                        "Redeemed access code did not create a patient account."
                    )
                establish_user_session(patient_user)
                flash("linked")
                return redirect(url_for("patient.dashboard"))
            flash("invalid_code", "error")

    return render_template("patient_link/link.html")
