from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.database import get_db
from app.repositories.patient import (
    get_latest_measurement,
    get_linked_patient,
    get_owned_measurement,
)
from app.security import patient_required
from app.services.monitoring import (
    parse_symptoms,
    parse_vitals,
    record_confirmation,
    record_measurement,
)
from app.services.patient_history import SYMPTOMS, TIMEFRAMES, get_patient_history
from app.translations import translate


patient = Blueprint("patient", __name__, url_prefix="/patient")


def _current_patient():
    profile = get_linked_patient(get_db(), session["user_id"])
    if profile is None:
        abort(404)
    return profile


def _parse_utc(value):
    if value.endswith("Z"):
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    else:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=timezone.utc)


def _next_due_at(patient_profile, latest):
    if latest is not None:
        base = _parse_utc(latest["measured_at"])
        delay = latest["next_delay_seconds"] or patient_profile[
            "initial_delay_seconds"
        ]
    else:
        base = _parse_utc(patient_profile["patient_created_at"])
        delay = patient_profile["initial_delay_seconds"]
    return (base + timedelta(seconds=delay)).strftime("%Y-%m-%dT%H:%M:%SZ")


@patient.route("/")
@patient_required
def dashboard():
    profile = _current_patient()
    latest = get_latest_measurement(get_db(), profile["id"])
    return render_template(
        "patient/dashboard.html",
        patient=profile,
        latest=latest,
        next_due_at=None if latest and latest["status"] == "pending_confirmation"
        else _next_due_at(profile, latest),
    )


@patient.route("/measurements/new", methods=("GET", "POST"))
@patient_required
def new_measurement():
    database = get_db()
    profile = _current_patient()
    form_values = {}
    latest = get_latest_measurement(database, profile["id"])
    if latest is not None and latest["status"] == "pending_confirmation":
        return redirect(
            url_for("patient.confirm_measurement", measurement_id=latest["id"])
        )

    if request.method == "POST":
        form_values = request.form.to_dict()
        try:
            systolic, diastolic, pulse = parse_vitals(request.form)
            symptoms = parse_symptoms(request.form)
            result = record_measurement(
                database, profile, systolic, diastolic, pulse, symptoms
            )
        except ValueError:
            flash("measurement_invalid", "error")
        else:
            if result["symptom_total"] == 5:
                flash("symptom_boundary_review", "warning")
            elif result["status"] == "pending_confirmation":
                flash("measurement_confirmation_required")
            else:
                flash("measurement_saved")
            if result["status"] == "pending_confirmation":
                return redirect(
                    url_for(
                        "patient.confirm_measurement",
                        measurement_id=result["id"],
                    )
                )
            return redirect(url_for("patient.dashboard"))

    return render_template(
        "patient/measurement.html",
        patient=profile,
        symptoms=SYMPTOMS,
        form_values=form_values,
    )


@patient.route(
    "/measurements/<int:measurement_id>/confirm", methods=("GET", "POST")
)
@patient_required
def confirm_measurement(measurement_id):
    database = get_db()
    profile = _current_patient()
    measurement = get_owned_measurement(database, profile["id"], measurement_id)
    if measurement is None or measurement["status"] != "pending_confirmation":
        abort(404)

    if request.method == "POST":
        try:
            systolic, diastolic, pulse = parse_vitals(request.form)
            result = record_confirmation(
                database, profile, measurement_id, systolic, diastolic, pulse
            )
        except ValueError:
            flash("measurement_invalid", "error")
        except LookupError:
            abort(404)
        else:
            if result["symptom_total"] == 5:
                flash("symptom_boundary_review", "warning")
            flash("measurement_saved")
            return redirect(url_for("patient.dashboard"))

    return render_template(
        "patient/confirmation.html",
        measurement=measurement,
        patient=profile,
    )


@patient.route("/history")
@patient_required
def history():
    profile = _current_patient()
    timeframe = request.args.get("range", "week")
    if timeframe not in TIMEFRAMES:
        timeframe = "week"
    history_data = get_patient_history(get_db(), profile, timeframe)
    for symptom in history_data["symptom_datasets"]:
        symptom["label"] = translate(symptom["label_key"])
    return render_template(
        "patient/history.html",
        patient=profile,
        history=history_data,
        timeframe=timeframe,
    )


@patient.route("/settings", methods=("GET", "POST"))
@patient_required
def settings():
    if request.method == "POST":
        language = request.form.get("language")
        theme = request.form.get("theme")
        if language not in ("en", "fr") or theme not in ("light", "dark"):
            abort(400)
        database = get_db()
        database.execute(
            """
            UPDATE users
            SET preferred_language = ?, theme_preference = ?
            WHERE id = ? AND role = 'patient'
            """,
            (language, theme, session["user_id"]),
        )
        database.commit()
        session["language"] = language
        session["theme"] = theme
        flash("settings_saved")
        return redirect(url_for("patient.settings"))

    preferences = get_db().execute(
        """
        SELECT preferred_language, theme_preference
        FROM users WHERE id = ? AND role = 'patient'
        """,
        (session["user_id"],),
    ).fetchone()
    return render_template("patient/settings.html", preferences=preferences)
