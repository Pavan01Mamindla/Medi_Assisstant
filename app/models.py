"""Database models. Deliberately minimal: no medical history is stored."""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager

STATUSES = ("Pending", "Approved", "Cancelled")


def _now():
    return datetime.now(timezone.utc)


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)


class AdminUser(UserMixin, db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        # werkzeug uses salted scrypt/pbkdf2 hashes; plain passwords are never stored.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(AdminUser, int(user_id))
    except (TypeError, ValueError):
        return None
