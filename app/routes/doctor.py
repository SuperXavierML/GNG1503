from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.database import get_db
from app.repositories.messages import create_message, list_messages
from app.repositories.doctor import (
    acknowledge_alert,
    create_note,
    get_measurement_pair,
    get_patient,
    list_comparison_measurements,
    list_patients,
    list_unacknowledged_alerts,
)
from app.security import doctor_required
from app.services.patient_history import TIMEFRAMES, get_patient_history
from app.services.patient_linking import issue_access_code
from app.services.risk_assessment import (
    calculate_risk_result,
    create_patient_profile,
    parse_threshold_overrides,
    parse_risk_answers,
)
from app.translations import translate


doctor = Blueprint("doctor", __name__, url_prefix="/doctor")


@doctor.route("/")
@doctor_required
def dashboard():
    database = get_db()
    doctor_id = session["user_id"]
    return render_template(
        "doctor/dashboard.html",
        account_display_name=session.get("display_name", ""),
        alerts=list_unacknowledged_alerts(database, doctor_id),
    )


@doctor.route("/patients")
@doctor_required
def patients():
    search = request.args.get("q", "").strip()
    return render_template(
        "doctor/patients.html",
        patients=list_patients(get_db(), session["user_id"], search),
        search=search,
    )


@doctor.route("/messages")
@doctor_required
def messages():
    return render_template(
        "doctor/messages.html",
        patients=list_patients(get_db(), session["user_id"]),
    )


@doctor.route(
    "/patients/<int:patient_id>/messages", methods=("GET", "POST")
)
@doctor_required
def patient_messages(patient_id):
    database = get_db()
    patient = get_patient(database, session["user_id"], patient_id)
    if patient is None:
        abort(404)
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body:
            flash("message_required", "error")
        elif len(body) > 2000:
            flash("message_too_long", "error")
        else:
            create_message(database, patient_id, session["user_id"], body)
            return redirect(
                url_for("doctor.patient_messages", patient_id=patient_id)
            )
    return render_template(
        "messages.html",
        conversation_name=patient["display_name"],
        messages=list_messages(database, patient_id),
        form_action=url_for(
            "doctor.patient_messages", patient_id=patient_id
        ),
        back_url=url_for("doctor.messages"),
        back_label=translate("messages"),
    )


@doctor.route("/patients/new", methods=("GET", "POST"))
@doctor_required
def new_patient():
    form_values = {}
    if request.method == "POST":
        form_values = request.form.to_dict()
        display_name = request.form.get("display_name", "").strip()
        if not display_name or len(display_name) > 100:
            flash("invalid_patient_name", "error")
        else:
            try:
                answers = parse_risk_answers(request.form)
                result = calculate_risk_result(answers)
                threshold_override = parse_threshold_overrides(request.form)
                patient_id = create_patient_profile(
                    get_db(),
                    session["user_id"],
                    display_name,
                    result,
                    threshold_override,
                )
            except ValueError:
                flash("risk_questionnaire_invalid", "error")
            else:
                flash("profile_created")
                return redirect(
                    url_for("doctor.patient_history", patient_id=patient_id)
                )
    return render_template(
        "doctor/new_patient.html",
        form_values=form_values,
    )


@doctor.route("/patients/<int:patient_id>")
@doctor_required
def patient_history(patient_id):
    return _render_patient_history(patient_id)


def _render_patient_history(patient_id, issued_access_code=None):
    database = get_db()
    patient = get_patient(database, session["user_id"], patient_id)
    if patient is None:
        abort(404)

    timeframe = request.args.get("range", "week")
    if timeframe not in TIMEFRAMES:
        timeframe = "week"
    history = get_patient_history(database, patient, timeframe)
    for symptom in history["symptom_datasets"]:
        symptom["label"] = translate(symptom["label_key"])

    comparison = None
    comparison_measurements = list_comparison_measurements(database, patient_id)
    first_id = request.args.get("first", type=int)
    second_id = request.args.get("second", type=int)
    if len(comparison_measurements) >= 2:
        if first_id is None:
            first_id = comparison_measurements[0]["id"]
        if second_id is None:
            second_id = comparison_measurements[1]["id"]
    if first_id is not None and second_id is not None:
        comparison = get_measurement_pair(
            database, patient_id, first_id, second_id
        )
        if comparison is None:
            flash("no_comparison", "error")
        else:
            comparison = [dict(reading) for reading in comparison]

    response = make_response(
        render_template(
            "doctor/patient_history.html",
            patient=patient,
            history=history,
            timeframe=timeframe,
            timeframes=TIMEFRAMES,
            comparison=comparison,
            comparison_measurements=comparison_measurements,
            selected_first_id=first_id,
            selected_second_id=second_id,
            issued_access_code=issued_access_code,
        )
    )
    if issued_access_code is not None:
        response.headers["Cache-Control"] = "no-store"
    return response


@doctor.route("/patients/<int:patient_id>/notes", methods=("POST",))
@doctor_required
def add_patient_note(patient_id):
    database = get_db()
    patient = get_patient(database, session["user_id"], patient_id)
    if patient is None:
        abort(404)

    note = request.form.get("note", "").strip()
    if not note:
        flash("note_required", "error")
    elif len(note) > 5000:
        flash("note_too_long", "error")
    else:
        create_note(database, session["user_id"], patient_id, note)
    return redirect(url_for("doctor.patient_history", patient_id=patient_id))


@doctor.route("/patients/<int:patient_id>/access-code", methods=("POST",))
@doctor_required
def create_access_code(patient_id):
    code = issue_access_code(get_db(), session["user_id"], patient_id)
    if code is None:
        flash("profile_not_ready", "error")
        return redirect(url_for("doctor.patient_history", patient_id=patient_id))
    return _render_patient_history(patient_id, code)


@doctor.route("/alerts/<int:alert_id>/acknowledge", methods=("POST",))
@doctor_required
def acknowledge_patient_alert(alert_id):
    updated = acknowledge_alert(get_db(), session["user_id"], alert_id)
    if not updated:
        abort(404)
    return redirect(url_for("doctor.dashboard"))


@doctor.route("/settings", methods=("GET", "POST"))
@doctor_required
def settings():
    if request.method == "POST":
        language = request.form.get("language")
        theme = request.form.get("theme")
        display_name = request.form.get("display_name")
        if theme is None:
            theme = get_db().execute(
                "SELECT theme_preference FROM users WHERE id = ? AND role = 'doctor'",
                (session["user_id"],),
            ).fetchone()["theme_preference"]
        if (
            language not in ("en", "fr")
            or theme not in ("light", "dark")
        ):
            abort(400)
        if display_name is not None:
            display_name = display_name.strip()
            if not display_name or len(display_name) > 100:
                abort(400)
        database = get_db()
        if display_name is None:
            database.execute(
                """
                UPDATE users
                SET preferred_language = ?, theme_preference = ?
                WHERE id = ? AND role = 'doctor'
                """,
                (language, theme, session["user_id"]),
            )
        else:
            database.execute(
                """
                UPDATE users
                SET preferred_language = ?, theme_preference = ?, display_name = ?
                WHERE id = ? AND role = 'doctor'
                """,
                (language, theme, display_name, session["user_id"]),
            )
        database.commit()
        session["language"] = language
        session["theme"] = theme
        if display_name is not None:
            session["display_name"] = display_name
        flash("settings_saved")
        return redirect(url_for("doctor.settings"))

    return render_template(
        "doctor/settings.html",
        preferences=get_db().execute(
            """
            SELECT preferred_language, theme_preference,
                   COALESCE(NULLIF(display_name, ''), substr(email, 1, instr(email, '@') - 1))
                       AS display_name
            FROM users WHERE id = ? AND role = 'doctor'
            """,
            (session["user_id"],),
        ).fetchone(),
    )
