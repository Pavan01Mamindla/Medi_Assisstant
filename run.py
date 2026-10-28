"""Entry point: `flask --app run run` or `python run.py`."""
from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()  # safe/idempotent; also available as `flask --app run init-db`

if __name__ == "__main__":
    app.run(debug=False)
