import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db  # noqa: E402
from app.models import AdminUser  # noqa: E402
from config import TestConfig  # noqa: E402


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = AdminUser(username="staff")
        user.set_password("correct-horse-battery")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def logged_in(client):
    client.post("/login", data={"username": "staff", "password": "correct-horse-battery"})
    return client


@pytest.fixture()
def valid_form():
    return {
        "patient_name": "Asha Demo",
        "email": "asha@example.com",
        "preferred_date": (date.today() + timedelta(days=3)).isoformat(),
        "reason": "Routine check-up",
    }
