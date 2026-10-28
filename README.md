# MediAssist AI: Healthcare Appointment & Patient Support Assistant

A demo web app built for an AI Skills & Prompt Engineering assessment. Patients can chat with an AI assistant (Claude), read clinic information and submit appointment **requests**; clinic staff review requests on a login-protected dashboard.

> **Demo project.** All clinic details are fictional. Do not enter real patient data. This is not medical advice and not a substitute for a qualified healthcare professional.

## Features

- **Home, Chat, Appointment, Clinic info, Staff dashboard**, responsive and accessible (labels, contrast, skip link, focus states, loading and empty states).
- **AI chatbot** using the official Anthropic Python SDK. The system prompt lives in `prompts/system_prompt.txt`, separate from the code.
- **Clearly labelled demo mode** when no API key is set: predefined sample responses, tagged in the UI as "not AI-generated".
- **Safety layers**
  1. Prompt rules: no diagnosis, no prescribing or medication changes, in-scope topics only, emergency guidance, not-a-substitute reminder.
  2. Server-side emergency keyword pre-check that returns a fixed "contact local emergency services" message without calling the model. This is a simple safety net, not a complete clinical triage system.
  3. API failures return a generic message; details are logged server-side only.
- **Appointment requests**: server-side validation, saved via SQLAlchemy; success page states it is a request, not a confirmed appointment.
- **Dashboard**: login (hashed passwords), search, status filter, status updates (Pending / Approved / Cancelled).
- **Security basics**: CSRF protection on forms and the chat API, parameterised queries, output escaping, secure cookie flags, request-size limit, security headers (CSP, nosniff, frame deny), open-redirect protection, secrets only in environment variables.

## Project structure

```
mediassist/
├── app/
│   ├── __init__.py        # app factory, error handlers, security headers
│   ├── models.py          # Appointment, AdminUser
│   ├── routes.py          # pages, chat API, dashboard
│   ├── ai.py              # emergency check, Claude call, demo mode
│   ├── validators.py      # server-side validation
│   ├── cli.py             # init-db, create-admin commands
│   ├── templates/  static/
├── prompts/system_prompt.txt
├── tests/                 # pytest suite
├── config.py  run.py  requirements.txt  .env.example  .gitignore
├── PROMPT_LOG.md          # template for your AI-usage documentation
└── README.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows: copy .env.example .env
```

Edit `.env`:

- `SECRET_KEY`: generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `ANTHROPIC_API_KEY`: your key from the Anthropic Console. **Leave empty for demo mode.**
- `ANTHROPIC_MODEL`: defaults to `claude-sonnet-5-5`; change if you prefer another model.

### Initialise the database and create a staff user

```bash
flask --app run init-db
flask --app run create-admin        # prompts for username and password (min 10 chars)
```

Tables are also created automatically on first start. The SQLite file (`instance/mediassist.db`) is git-ignored.

### Run

```bash
flask --app run run                 # http://127.0.0.1:5000
```

### Test

```bash
python -m pytest -q
```

Tests cover page loads, form validation, persistence, SQL-injection and XSS handling, authentication, dashboard filtering and status updates, CSRF enforcement, chat validation, emergency handling, demo-mode labelling, API-failure handling without leaking secrets, and security headers. Live Claude calls are mocked, so tests need no API key or network.

## Never commit secrets

`.env`, databases and logs are in `.gitignore`. Only `.env.example` (no real values) is committed. If a key is ever pushed to GitHub, revoke it in the Anthropic Console immediately; deleting the commit is not enough.

## Limitations & hardening needed before real-world use

This is an assessment demo. Before any real deployment you would need, at minimum:

- Stronger authentication: rate limiting / lockout, MFA, password reset, role-based access, audit logs.
- HTTPS everywhere with `SESSION_COOKIE_SECURE=1`, a production WSGI server (e.g. gunicorn) behind a reverse proxy; never `debug=True`.
- Rate limiting on `/api/chat` to control abuse and API cost.
- A production database and backups, data-retention policy, and compliance review (e.g. HIPAA / GDPR / local health-data law). This demo stores only name, email, date and a short reason, and should not be used for real patients.
- Clinical review of the system prompt and emergency handling; the keyword pre-check will miss phrasings and is not a medical triage tool.
- Email notifications and a way to actually confirm appointments to patients.

## Prompt engineering documentation

See `PROMPT_LOG.md`, a template to fill in with your *real* prompts, changes and test runs.
