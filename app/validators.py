"""Server-side input validation (never trust the browser)."""
import re
from datetime import date, datetime, timedelta

from email_validator import EmailNotValidError, validate_email

_NAME_RE = re.compile(r"^[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ .'\-]*$")
MAX_DAYS_AHEAD = 365


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def validate_appointment(form, today: date | None = None):
    """Return (clean_data, errors). errors maps field name -> message."""
    today = today or date.today()
    errors, data = {}, {}

    name = _clean(form.get("patient_name"))
    if not name:
        errors["patient_name"] = "Please enter your full name."
    elif len(name) < 2 or len(name) > 100:
        errors["patient_name"] = "Name must be between 2 and 100 characters."
    elif not _NAME_RE.match(name):
        errors["patient_name"] = "Name may only contain letters, spaces, apostrophes, hyphens and full stops."
    data["patient_name"] = name

    email = _clean(form.get("email"))
    if not email:
        errors["email"] = "Please enter your contact email."
    else:
        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError:
            errors["email"] = "Please enter a valid email address."
    data["email"] = email

    raw_date = _clean(form.get("preferred_date"))
    parsed = None
    if not raw_date:
        errors["preferred_date"] = "Please choose a preferred date."
    else:
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            errors["preferred_date"] = "Please enter a valid date."
        else:
            if parsed < today:
                errors["preferred_date"] = "The preferred date cannot be in the past."
            elif parsed > today + timedelta(days=MAX_DAYS_AHEAD):
                errors["preferred_date"] = "Please choose a date within the next 12 months."
    data["preferred_date"] = parsed

    reason = _clean(form.get("reason"))
    if not reason:
        errors["reason"] = "Please briefly describe the reason for your visit."
    elif len(reason) < 5:
        errors["reason"] = "Please give a little more detail (at least 5 characters)."
    elif len(reason) > 500:
        errors["reason"] = "Reason must be 500 characters or fewer."
    data["reason"] = reason

    return data, errors


def validate_chat_payload(payload, max_chars: int, max_history: int):
    """Validate the JSON body of /api/chat. Returns (messages, error)."""
    if not isinstance(payload, dict):
        return None, "Invalid request."
    msgs = payload.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None, "Please type a question."

    clean = []
    for m in msgs[-max_history:]:
        if not isinstance(m, dict):
            return None, "Invalid request."
        role, content = m.get("role"), m.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            return None, "Invalid request."
        content = content.strip()
        if not content:
            return None, "Please type a question."
        if len(content) > max_chars:
            return None, f"Messages must be {max_chars} characters or fewer."
        clean.append({"role": role, "content": content})

    # The Anthropic API needs the conversation to start with and end on a user turn.
    while clean and clean[0]["role"] != "user":
        clean.pop(0)
    if not clean or clean[-1]["role"] != "user":
        return None, "Please type a question."
    return clean, None


def validate_status(value) -> str | None:
    from .models import STATUSES
    return value if value in STATUSES else None
