"""MediAssist AI - application factory."""
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Please sign in to view the staff dashboard."
login_manager.login_message_category = "info"


def _configure_logging(app: Flask) -> None:
    app.logger.setLevel(logging.INFO)
    if app.testing:
        return
    os.makedirs("logs", exist_ok=True)
    handler = RotatingFileHandler("logs/mediassist.log", maxBytes=512_000, backupCount=3)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    app.logger.addHandler(handler)


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    _configure_logging(app)
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from .models import AdminUser  # noqa: F401  (registers models)
    from .routes import bp
    from .cli import register_cli

    app.register_blueprint(bp)
    register_cli(app)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; frame-ancestors 'none'",
        )
        return resp

    def _wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(CSRFError)
    def csrf_error(err):
        if _wants_json():
            return jsonify(error="Your session expired. Please refresh the page and try again."), 400
        return render_template("error.html", code=400,
                               message="Your form session expired. Please go back, refresh the page and try again."), 400

    @app.errorhandler(404)
    def not_found(err):
        if _wants_json():
            return jsonify(error="Not found."), 404
        return render_template("error.html", code=404, message="That page could not be found."), 404

    @app.errorhandler(413)
    def too_large(err):
        if _wants_json():
            return jsonify(error="Request too large."), 413
        return render_template("error.html", code=413, message="That request was too large."), 413

    @app.errorhandler(500)
    def server_error(err):
        app.logger.exception("Unhandled server error")
        if _wants_json():
            return jsonify(error="Something went wrong on our side. Please try again."), 500
        return render_template("error.html", code=500,
                               message="Something went wrong on our side. Please try again later."), 500

    return app
