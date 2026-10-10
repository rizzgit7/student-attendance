"""Auth endpoints (blueprint §13): login / refresh / logout."""
from flask import Blueprint, g, jsonify, request

from app.utils import api_error, require_auth
from app.utils.ratelimit import client_ip, hit
from app.utils.security import decode_token, issue_tokens, revoke_refresh

import jwt

bp = Blueprint("auth", __name__)


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return api_error(400, "validation_error", "email and password required")

    # Rate limiting on login attempts (§12/§16)
    from flask import current_app
    from app.models import User
    if not hit(f"login:{email}:{client_ip()}",
               current_app.config["RATELIMIT_LOGIN_PER_MINUTE"]):
        return api_error(429, "rate_limit_exceeded",
                         "Too many login attempts. Try again later.")

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password) or not user.is_active:
        return api_error(401, "invalid_credentials", "Invalid email or password")

    from app.models import Teacher
    teacher = Teacher.query.filter_by(user_id=user.id).first()
    return jsonify({
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "institution_id": user.institution_id,
            "teacher_id": teacher.id if teacher else None,
        },
        **issue_tokens(user),
    })


@bp.post("/auth/refresh")
def refresh():
    data = request.get_json(silent=True) or {}
    token = data.get("refresh_token")
    if not token:
        return api_error(400, "validation_error", "refresh_token required")
    try:
        payload = decode_token(token, expected_type="refresh")
    except jwt.PyJWTError:
        return api_error(401, "invalid_token", "Refresh token invalid or expired")

    from app.models import User
    from app.extensions import db
    user = db.session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        return api_error(401, "invalid_token", "User no longer active")
    # Rotate: revoke the refresh token that was just used
    revoke_refresh(payload.get("jti"), payload.get("exp", 0))
    return jsonify(issue_tokens(user))


@bp.post("/auth/logout")
@require_auth
def logout():
    data = request.get_json(silent=True) or {}
    token = data.get("refresh_token")
    if token:
        try:
            payload = decode_token(token, expected_type="refresh")
            revoke_refresh(payload.get("jti"), payload.get("exp", 0))
        except jwt.PyJWTError:
            pass
    return jsonify({"message": "logged out"})
