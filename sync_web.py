"""Sync the web sources into public/ for Vercel's static file serving.

Run after editing anything in student_attendance_api/launch/ or
student_attendance_api/dashboard/:

    python sync_web.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / "student_attendance_api"
PUBLIC = ROOT / "public"
PUBLIC.mkdir(exist_ok=True)

# launch/ → public/ root
for name in ("index.html", "privacy.html", "terms.html"):
    shutil.copy2(API / "launch" / name, PUBLIC / name)

# dashboard/ → public/dashboard/ + /static (index.html references /static/*)
(PUBLIC / "dashboard").mkdir(exist_ok=True)
(PUBLIC / "static").mkdir(exist_ok=True)
shutil.copy2(API / "dashboard" / "index.html", PUBLIC / "dashboard" / "index.html")
for name in ("app.js", "dashboard.css"):
    shutil.copy2(API / "dashboard" / name, PUBLIC / "static" / name)

print(f"Synced web assets into {PUBLIC}")
for path in sorted(PUBLIC.rglob("*")):
    if path.is_file():
        print("  ", path.relative_to(PUBLIC))
