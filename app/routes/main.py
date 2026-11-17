from flask import Blueprint, abort, render_template, request, session


main = Blueprint("main", __name__)


@main.route("/")
def home():
    language = request.args.get("language")
    if language is not None:
        if language not in ("en", "fr"):
            abort(400)
        session["language"] = language
    return render_template("home.html")
