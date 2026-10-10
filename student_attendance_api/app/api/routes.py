"""API root/health endpoints (§13 API base)."""
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify

bp = Blueprint("api", __name__)


@bp.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "student-attendance-api",
        "time": datetime.now(timezone.utc).isoformat(),
    })


@bp.get("/api/meta")
def meta():
    """Public metadata: timing policy + APK download target (§19/§20)."""
    return jsonify({
        "attendance": {
            "code_length": 6,
            "note": "Server time is authoritative for all attendance marks.",
        },
        "apk_url": os.environ.get("APK_DOWNLOAD_URL", ""),
        "version": os.environ.get("APP_VERSION", ""),
        "support_email": os.environ.get("SUPPORT_EMAIL", ""),
    })
