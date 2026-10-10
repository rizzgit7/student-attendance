"""Vercel serverless entrypoint (WSGI) for the Flask API (blueprint §2/§19).

vercel.json rewrites /auth, /attendance, /student, /teacher, /admin,
/reports, /leave and /api/* into this function; the launch page, dashboard,
privacy and terms pages are served as static files from public/.

Required Vercel environment variables:
  SECRET_KEY       long random string (required)
  DATABASE_URL     managed PostgreSQL URL (required for persistence —
                   Vercel's filesystem is ephemeral)
Optional:
  APK_DOWNLOAD_URL signed APK location shown on the launch page
  APP_VERSION, SUPPORT_EMAIL, JWT_*, RATELIMIT_*
"""
import os
import sys

_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "student_attendance_api",
)
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

if not os.environ.get("DATABASE_URL"):
    # Ephemeral fallback so the function still boots without configuration;
    # configure managed PostgreSQL in Vercel before serving real traffic.
    os.environ["DATABASE_URL"] = "sqlite:////tmp/attendance.db"
    print(
        "WARNING: DATABASE_URL is not set — using ephemeral SQLite in /tmp. "
        "Data will be lost between deployments.",
        file=sys.stderr,
    )

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

app = create_app()

# Vercel has no build step for schema management and /tmp starts empty on
# cold starts; create tables idempotently on the first request. For a real
# production database prefer running `flask db upgrade` from a machine with
# network access to the database (blueprint §15).
_schema_ready = False


@app.before_request
def _ensure_schema():
    global _schema_ready
    if _schema_ready:
        return None
    with app.app_context():
        db.create_all()
    _schema_ready = True
    return None
