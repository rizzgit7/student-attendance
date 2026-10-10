# Student Attendance — Commercial Product (V1)

Built from the **Student Attendance Final End-to-End Blueprint** (7-page PDF).
Teacher generates a short-lived 6-digit code; students enter it in the Android
app; the backend records PRESENT/LATE with a server timestamp.

```
student attendance/
├── student_attendance_api/     Flask REST API + PostgreSQL/SQLite + PC dashboard + launch page
├── student_attendance_app/     Flutter Android app (student + teacher)
└── README.md                   ← this file
```

## Quick start (API + dashboard + launch page)

```bash
cd student_attendance_api
pip install -r requirements.txt
cp .env.example .env            # set SECRET_KEY + DATABASE_URL (PostgreSQL in prod)
python scripts/seed.py          # optional demo institution
python run.py                   # http://127.0.0.1:5000
```

- Launch page: `http://127.0.0.1:5000/` (§19)
- PC dashboard: `http://127.0.0.1:5000/dashboard`
- Demo logins (after seeding): `admin@demo.local`, `teacher@demo.local`,
  `student1..3@demo.local` — password `ChangeMe123!`

Migrations: `python -m flask db upgrade` (Flask-Migrate/Alembic, §15).
Tests: `python -m pytest tests -q` — 31 tests covering the §17 matrix.

## Mobile app

See [student_attendance_app/README.md](student_attendance_app/README.md).
Requires the Flutter SDK (`flutter create .` generates platform folders,
then `flutter run --dart-define=BASE_URL=...`).

## Design highlights (blueprint traceability)

| Blueprint | Where |
|---|---|
| §6 academic data model | `app/models/__init__.py` (Institution → Year → Program → Class → Section → Subject → Assignment) |
| §7 tables (18) | `app/models/__init__.py` |
| §10 session algorithm | `app/teacher/routes.py` (code gen/rotation) + `app/attendance/routes.py` (check-in) + `app/utils/timing.py` |
| §11 timing policy | Institution-configurable windows; `utils/timing.py`; server time authoritative |
| §12 anti-proxy controls | auth + membership + short-lived code + server timestamp + duplicate constraint + rate limiting |
| §13 API | all endpoints registered (see `flask routes` equivalent in `app/`) |
| §16 security | JWT access/refresh + rotation/revocation, pbkdf2 hashing, role guards, tenant isolation, audit logs, env-only secrets |
| §17 testing | `tests/test_attendance.py`, `tests/test_api.py` |
| §19 launch page | `launch/` (Download APK + Admin Login + support/privacy/terms) |

## Deploy to Vercel (recommended zero-cost launch, §2/§19)

The repo root is a ready-to-import Vercel project:

| Path | Role |
|---|---|
| `vercel.json` | rewrites `/auth`, `/attendance`, `/student`, `/teacher`, `/admin`, `/reports`, `/leave`, `/api/*` → Python serverless function |
| `api/index.py` | Flask app as a WSGI serverless function (auto-creates schema on first request) |
| `public/` | static launch page (`/`), dashboard (`/dashboard`), `/privacy`, `/terms` |
| `requirements.txt` | installed by Vercel for the Python function |

Steps:

1. Push this folder to GitHub (or use `vercel --prod` with the CLI from here).
2. In Vercel: **Add New → Project → Import** the repo. Framework preset: **Other**.
3. Set environment variables (Project → Settings → Environment Variables):
   - `SECRET_KEY` — long random string (required)
   - `DATABASE_URL` — managed PostgreSQL connection string (required; Vercel's disk is ephemeral). Free option: **Tiger Cloud** — 2 free Postgres services, 750 MB each, no credit card ([create one](https://console.cloud.tigerdata.com/signup)).
   - `APK_DOWNLOAD_URL`, `APP_VERSION`, `SUPPORT_EMAIL` — optional, shown on the launch page.
4. Deploy. First request creates the schema automatically; for later schema
   changes run `python -m flask db upgrade` against the production DB from a
   machine with network access.
5. After editing `student_attendance_api/launch/` or `dashboard/`, run
   `python sync_web.py` to refresh `public/` before redeploying.

Notes for Vercel:
- If `DATABASE_URL` is unset the function boots on ephemeral `/tmp` SQLite and
  logs a warning — fine for a smoke test, useless for real data.
- Rate limiting and the refresh-token denylist are per-function-instance in V1;
  move them to Redis (e.g. Vercel KV) before scaling out.
- The Android APK is *hosted* (link from the launch page), not deployed to
  Vercel — build it with the Flutter SDK and upload to object storage.

### Other hosting (§2)

- Launch page/dashboard: any static host.
- API: any Python host (gunicorn) + managed PostgreSQL (`DATABASE_URL`).
