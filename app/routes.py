"""HTTP routes."""
from urllib.parse import urlparse

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from . import ai, db
from .models import STATUSES, AdminUser, Appointment
from .validators import (validate_appointment, validate_chat_payload,
                         validate_status)

bp = Blueprint("main", __name__)

CLINIC = {
    "name": "Riverside Demo Clinic",
    "hours": [("Monday - Friday", "09:00 - 17:00"), ("Saturday", "09:00 - 13:00"), ("Sunday", "Closed")],
    "services": [
        ("General consultation", "Talk through a health concern with a clinician."),
        ("Vaccination", "Routine adult and child immunisations."),
        ("Routine check-up", "Basic preventive health review."),
        ("Blood pressure monitoring", "Simple readings and follow-up guidance."),
        ("Nutrition counselling", "General healthy-eating support."),
    ],
    "contact": {"phone": "+00 000 000 0000", "email": "demo@example.com", "address": "1 Example Street, Demo City"},
}


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/chat")
def chat():
    return render_template("chat.html", demo_mode=ai.is_demo_mode(),
                           max_chars=current_app.config["CHAT_MAX_MESSAGE_CHARS"])


@bp.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True)
    messages, error = validate_chat_payload(
        payload,
        current_app.config["CHAT_MAX_MESSAGE_CHARS"],
        current_app.config["CHAT_MAX_HISTORY"],
    )
    if error:
        return jsonify(error=error), 400
    return jsonify(ai.get_reply(messages))


@bp.route("/appointment", methods=["GET", "POST"])
def appointment():
    if request.method == "POST":
        data, errors = validate_appointment(request.form)
        if errors:
            return render_template("appointment.html", errors=errors, values=request.form), 400
        appt = Appointment(**data)
        db.session.add(appt)
        db.session.commit()
        current_app.logger.info("Appointment request #%s saved", appt.id)
        return redirect(url_for("main.appointment_success", ref=appt.id))
    return render_template("appointment.html", errors={}, values={})


@bp.get("/appointment/success")
def appointment_success():
    ref = request.args.get("ref", type=int)
    return render_template("success.html", ref=ref)


@bp.get("/clinic")
def clinic():
    return render_template("clinic.html", clinic=CLINIC)


def _safe_next(target):
    if not target:
        return None
    parsed = urlparse(target)
    return target if not parsed.netloc and not parsed.scheme and target.startswith("/") and not target.startswith("//") else None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()[:50]
        password = request.form.get("password") or ""
        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            current_app.logger.info("Staff login: %s", username)
            return redirect(_safe_next(request.args.get("next")) or url_for("main.dashboard"))
        current_app.logger.warning("Failed staff login for '%s'", username)
        flash("Incorrect username or password.", "error")
        return render_template("login.html"), 401
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@bp.get("/dashboard")
@login_required
def dashboard():
    q = (request.args.get("q") or "").strip()[:100]
    status = request.args.get("status") if request.args.get("status") in STATUSES else ""
    query = Appointment.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Appointment.patient_name.ilike(like),
                                 Appointment.email.ilike(like),
                                 Appointment.reason.ilike(like)))
    if status:
        query = query.filter(Appointment.status == status)
    appts = query.order_by(Appointment.created_at.desc()).all()
    return render_template("dashboard.html", appts=appts, q=q, status=status, statuses=STATUSES)


@bp.post("/dashboard/<int:appt_id>/status")
@login_required
def update_status(appt_id):
    appt = db.session.get(Appointment, appt_id)
    if appt is None:
        return render_template("error.html", code=404, message="Request not found."), 404
    new_status = validate_status(request.form.get("status"))
    if new_status is None:
        flash("Invalid status.", "error")
    else:
        appt.status = new_status
        db.session.commit()
        current_app.logger.info("Appointment #%s set to %s", appt.id, new_status)
        flash(f"Request #{appt.id} marked {new_status}.", "success")
    return redirect(url_for("main.dashboard", q=request.args.get("q", ""), status=request.args.get("filter", "")))
