from functools import wraps
import secrets

from flask import abort, redirect, request, session, url_for


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def protect_csrf():
    if request.method == "POST":
        submitted = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(submitted, expected):
            abort(400)


def establish_user_session(user):
    session.clear()
    session["user_id"] = user["id"]
    session["user_role"] = user["role"]
    session["display_name"] = (
        user["display_name"] or user["email"].split("@", 1)[0]
    )
    session["language"] = user["preferred_language"]
    session["theme"] = user["theme_preference"]


def doctor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_role") != "doctor":
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def patient_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_role") != "patient":
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped
