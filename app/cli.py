"""Flask CLI commands: init-db and create-admin."""
import os

import click

from . import db
from .models import AdminUser


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create database tables."""
        db.create_all()
        click.echo("Database initialised.")

    @app.cli.command("create-admin")
    @click.option("--username", default=lambda: os.environ.get("ADMIN_USERNAME", ""))
    def create_admin(username):
        """Create (or reset the password of) a staff dashboard user."""
        db.create_all()
        username = (username or click.prompt("Username")).strip()
        password = os.environ.get("ADMIN_PASSWORD") or click.prompt(
            "Password (min 10 chars)", hide_input=True, confirmation_prompt=True
        )
        if not username or len(username) > 50:
            raise click.ClickException("Username must be 1-50 characters.")
        if len(password) < 10:
            raise click.ClickException("Password must be at least 10 characters.")
        user = AdminUser.query.filter_by(username=username).first() or AdminUser(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{username}' saved.")
