"""Development entrypoint.

Run:            python run.py            (serves on :5000, dev)
Migrations:     flask --app run db init / db migrate / db upgrade
"""
from app import create_app
from app.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        # Convenience for first run; production uses Flask-Migrate (§15).
        db.create_all()
    app.run(host="127.0.0.1", port=5000, debug=True)
