"""Shared helpers: auth decorators, role guards, error responses."""
import functools

import jwt
from flask import g, jsonify, request

from app.models import User

from .security import decode_token
from .ratelimit import rate_limit as rate_limit_guard  # re-export (§12)


def api_error(status, code, message):
    return jsonify({"error": code, "message": message}), status


def get_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None


def load_user():
    """Populate g.user from the access token; returns None if absent/invalid."""
    token = get_token()
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.PyJWTError:
        return None
    from app.extensions import db
    user = db.session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        return None
    g.user = user
    g.token_payload = payload
    return user


def require_auth(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if load_user() is None:
            return api_error(401, "unauthorized", "Valid access token required.")
        return fn(*args, **kwargs)

    return inner


def require_role(*roles):
    """Role-based authorization (blueprint §16)."""

    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            if load_user() is None:
                return api_error(401, "unauthorized",
                                 "Valid access token required.")
            if g.user.role not in roles:
                return api_error(403, "forbidden",
                                 "Insufficient role for this action.")
            return fn(*args, **kwargs)

        return inner

    return wrap


# Staff roles allowed on teacher endpoints
STAFF_ROLES = ("TEACHER", "HOD", "INSTITUTION_ADMIN", "SUPER_ADMIN")
# Admin roles allowed on admin endpoints
ADMIN_ROLES = ("HOD", "INSTITUTION_ADMIN", "SUPER_ADMIN")


def jsonify_validation(err):
    return api_error(400, "validation_error", str(err))
