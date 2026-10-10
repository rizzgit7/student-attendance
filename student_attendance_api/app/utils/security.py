"""JWT access/refresh token lifecycle (blueprint §16).

Access tokens are short-lived (default 15 min), refresh tokens long-lived
(default 7 days). Logout invalidates refresh tokens via an in-memory jti
denylist — for multi-process deployments swap in a shared store (Redis).
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app

# Refresh tokens seen after logout (jti -> expiry)
_REVOKED_REFRESH_JTIS: dict[str, datetime] = {}


def _now():
    return datetime.now(timezone.utc)


def issue_tokens(user):
    now = _now()
    access_exp = now + timedelta(
        seconds=current_app.config["JWT_ACCESS_SECONDS"]
    )
    refresh_exp = now + timedelta(
        seconds=current_app.config["JWT_REFRESH_SECONDS"]
    )
    base = {"sub": str(user.id), "role": user.role,
            "inst": user.institution_id}
    access = jwt.encode(
        {**base, "type": "access", "iat": now, "exp": access_exp},
        current_app.config["SECRET_KEY"], algorithm="HS256",
    )
    refresh = jwt.encode(
        {**base, "type": "refresh", "iat": now, "exp": refresh_exp,
         "jti": uuid.uuid4().hex},
        current_app.config["SECRET_KEY"], algorithm="HS256",
    )
    return {"access_token": access, "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": current_app.config["JWT_ACCESS_SECONDS"]}


def decode_token(token, expected_type="access"):
    """Decode and validate a token. Raises jwt exceptions on failure."""
    payload = jwt.decode(
        token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    if expected_type == "refresh" and payload.get("jti") in _REVOKED_REFRESH_JTIS:
        raise jwt.InvalidTokenError("token revoked")
    return payload


def revoke_refresh(jti, exp_timestamp):
    if jti:
        _REVOKED_REFRESH_JTIS[jti] = datetime.fromtimestamp(
            exp_timestamp, tz=timezone.utc
        )
        # opportunistically drop expired entries
        now = _now()
        for key, expiry in list(_REVOKED_REFRESH_JTIS.items()):
            if expiry < now:
                _REVOKED_REFRESH_JTIS.pop(key, None)


def generate_attendance_code():
    """Cryptographically random 6-digit code (blueprint §10)."""
    import secrets
    return f"{secrets.randbelow(1_000_000):06d}"
