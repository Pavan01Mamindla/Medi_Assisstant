from datetime import date, timedelta

import pytest

from app import ai, create_app, db
from app.models import Appointment, AdminUser
from app.validators import validate_chat_payload
from config import TestConfig


# ---------- pages ----------
@pytest.mark.parametrize("path", ["/", "/chat", "/appointment", "/clinic", "/login"])
def test_public_pages_load(client, path):
    assert client.get(path).status_code == 200


def test_clinic_page_labelled_fictional(client):
    assert b"Fictional demo data" in client.get("/clinic").data


def test_unknown_page_404(client):
    assert client.get("/nope").status_code == 404


# ---------- appointment form ----------
def test_valid_appointment_saved(client, valid_form):
    res = client.post("/appointment", data=valid_form)
    assert res.status_code == 302
    appt = Appointment.query.one()
    assert appt.status == "Pending"
    assert appt.patient_name == "Asha Demo"


def test_success_page_does_not_claim_confirmation(client, valid_form):
    res = client.post("/appointment", data=valid_form, follow_redirects=True)
    body = res.data.decode()
    assert "not a confirmed appointment" in body
    assert "appointment is confirmed" not in body.lower()


@pytest.mark.parametrize("field,value", [
    ("patient_name", ""),
    ("patient_name", "X"),
    ("patient_name", "<script>alert(1)</script>"),
    ("email", "not-an-email"),
    ("email", ""),
    ("preferred_date", ""),
    ("preferred_date", "2020-01-01"),
    ("preferred_date", "31-02-2030"),
    ("reason", ""),
    ("reason", "x" * 501),
])
def test_invalid_appointment_rejected(client, valid_form, field, value):
    valid_form[field] = value
    res = client.post("/appointment", data=valid_form)
    assert res.status_code == 400
    assert Appointment.query.count() == 0


def test_sql_injection_text_stored_literally(client, valid_form):
    valid_form["reason"] = "x'); DROP TABLE appointments;--"
    assert client.post("/appointment", data=valid_form).status_code == 302
    assert Appointment.query.one().reason.startswith("x')")


def test_appointment_output_is_escaped(client, logged_in, valid_form):
    valid_form["reason"] = "<b>bold</b> visit please"
    client.post("/appointment", data=valid_form)
    body = logged_in.get("/dashboard").data.decode()
    assert "<b>bold</b>" not in body
    assert "&lt;b&gt;bold&lt;/b&gt;" in body


# ---------- auth & dashboard ----------
def test_dashboard_requires_login(client):
    res = client.get("/dashboard")
    assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_status_update_requires_login(client, valid_form):
    client.post("/appointment", data=valid_form)
    res = client.post("/dashboard/1/status", data={"status": "Approved"})
    assert res.status_code == 302 and "/login" in res.headers["Location"]
    assert Appointment.query.one().status == "Pending"


def test_wrong_password_rejected(client):
    res = client.post("/login", data={"username": "staff", "password": "wrong"})
    assert res.status_code == 401


def test_open_redirect_blocked(client):
    res = client.post("/login?next=https://evil.example",
                      data={"username": "staff", "password": "correct-horse-battery"})
    assert res.headers["Location"].endswith("/dashboard")


def test_password_is_hashed(app):
    user = AdminUser.query.filter_by(username="staff").one()
    assert "correct-horse-battery" not in user.password_hash
    assert user.check_password("correct-horse-battery")


def test_status_update_and_invalid_status(logged_in, valid_form):
    logged_in.post("/appointment", data=valid_form)
    logged_in.post("/dashboard/1/status", data={"status": "Approved"})
    assert Appointment.query.one().status == "Approved"
    logged_in.post("/dashboard/1/status", data={"status": "Hacked"})
    assert Appointment.query.one().status == "Approved"


def test_dashboard_search_and_filter(logged_in, valid_form):
    logged_in.post("/appointment", data=valid_form)
    other = dict(valid_form, patient_name="Ravi Sample", email="ravi@example.com")
    logged_in.post("/appointment", data=other)
    logged_in.post("/dashboard/2/status", data={"status": "Cancelled"})
    assert b"Ravi Sample" in logged_in.get("/dashboard?q=ravi").data
    assert b"Asha Demo" not in logged_in.get("/dashboard?q=ravi").data
    body = logged_in.get("/dashboard?status=Cancelled").data
    assert b"Ravi Sample" in body and b"Asha Demo" not in body


def test_dashboard_empty_state(logged_in):
    assert b"No requests found" in logged_in.get("/dashboard").data


# ---------- CSRF ----------
def test_csrf_enforced_when_enabled():
    class CsrfConfig(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(CsrfConfig)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        res = c.post("/appointment", data={"patient_name": "A B"})
        assert res.status_code == 400
        assert c.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 400


# ---------- chat ----------
def chat(client, text, history=None):
    msgs = (history or []) + [{"role": "user", "content": text}]
    return client.post("/api/chat", json={"messages": msgs})


def test_chat_demo_mode_is_labelled(client):
    data = chat(client, "What are your opening hours?").get_json()
    assert data["source"] == "demo"
    assert "09:00" in data["reply"]


def test_chat_demo_mode_banner_shown(client):
    assert b"Demo mode" in client.get("/chat").data


@pytest.mark.parametrize("text", [
    "I have chest pain", "I can't breathe", "I think I'm having a stroke",
    "I want to kill myself", "my friend overdosed",
])
def test_emergency_messages_get_emergency_reply(client, text):
    data = chat(client, text).get_json()
    assert data["source"] == "emergency"
    assert "emergency services" in data["reply"].lower()


def test_emergency_never_calls_model(app, client, monkeypatch):
    app.config["ANTHROPIC_API_KEY"] = "sk-fake"
    monkeypatch.setattr(ai, "_call_claude", lambda m: pytest.fail("model called"))
    assert chat(client, "severe chest pain").get_json()["source"] == "emergency"


@pytest.mark.parametrize("payload", [
    None, {}, {"messages": []}, {"messages": "hi"},
    {"messages": [{"role": "user", "content": ""}]},
    {"messages": [{"role": "user", "content": "   "}]},
    {"messages": [{"role": "system", "content": "x"}]},
    {"messages": [{"role": "user", "content": 5}]},
    {"messages": [{"role": "user", "content": "x" * 5000}]},
    {"messages": [{"role": "assistant", "content": "hi"}]},
])
def test_invalid_chat_input_rejected(client, payload):
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_chat_non_json_rejected(client):
    assert client.post("/api/chat", data="plain", content_type="text/plain").status_code == 400


def test_chat_live_success_is_labelled_live(app, client, monkeypatch):
    app.config["ANTHROPIC_API_KEY"] = "sk-fake"
    monkeypatch.setattr(ai, "_call_claude", lambda m: "Hello from the model")
    data = chat(client, "What is a vaccine?").get_json()
    assert data == {"reply": "Hello from the model", "source": "live", "disclaimer": ai.DISCLAIMER}


def test_chat_api_failure_hides_details(app, client, monkeypatch):
    app.config["ANTHROPIC_API_KEY"] = "sk-secret-key-123"

    def boom(_):
        raise RuntimeError("401 invalid x-api-key sk-secret-key-123 traceback")

    monkeypatch.setattr(ai, "_call_claude", boom)
    res = chat(client, "What is a vaccine?")
    assert res.status_code == 200
    data = res.get_json()
    assert data["source"] == "error"
    assert "sk-secret" not in res.get_data(as_text=True)
    assert "traceback" not in res.get_data(as_text=True)


def test_system_prompt_loaded_and_has_safety_rules():
    text = ai.load_system_prompt()
    assert "Never diagnose" in text
    assert "emergency services" in text
    assert not any(l.startswith("# ") for l in text.splitlines())


def test_history_truncated_and_starts_with_user():
    msgs = [{"role": "assistant", "content": "a"}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(30)
    ] + [{"role": "user", "content": "last"}]
    clean, err = validate_chat_payload({"messages": msgs}, 1000, 10)
    assert err is None and len(clean) <= 10
    assert clean[0]["role"] == "user" and clean[-1]["content"] == "last"


# ---------- misc security ----------
def test_security_headers_present(client):
    h = client.get("/").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in h["Content-Security-Policy"]


def test_no_api_key_in_pages(app, client):
    app.config["ANTHROPIC_API_KEY"] = "sk-should-not-leak"
    for path in ["/", "/chat", "/appointment", "/clinic"]:
        assert b"sk-should-not-leak" not in client.get(path).data
