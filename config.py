"""Application configuration. All secrets come from environment variables."""
import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY", "").strip()
    if not key or key == "change-me":
        # Fall back to a random per-process key so the app never runs with a
        # known default. Sessions will reset on restart; set SECRET_KEY in .env.
        logger.warning("SECRET_KEY not set; using a temporary random key.")
        return secrets.token_hex(32)
    return key


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///mediassist.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    ANTHROPIC_TIMEOUT = 30  # seconds
    ANTHROPIC_MAX_TOKENS = 600

    # Session / cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 2  # 2 hours

    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 64 * 1024  # reject oversized request bodies

    # Chat limits
    CHAT_MAX_MESSAGE_CHARS = 1000
    CHAT_MAX_HISTORY = 10


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    ANTHROPIC_API_KEY = ""
    SECRET_KEY = "test-secret-key"
