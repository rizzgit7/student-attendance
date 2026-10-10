"""In-process fixed-window rate limiter (blueprint §12/§16).

Limits attempts per key (login per email+IP, code attempts per student).
Single-process only — replace with a shared store (Redis) when running
multiple workers.
"""
import time
from collections import defaultdict
from functools import wraps

from flask import current_app, g, jsonify, request

_BUCKETS: dict[str, list[float]] = defaultdict(list)


def hit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Record an attempt; returns False when the limit is exceeded."""
    now = time.monotonic()
    window = [t for t in _BUCKETS[key] if now - t < window_seconds]
    if len(window) >= limit:
        _BUCKETS[key] = window
        return False
    window.append(now)
    _BUCKETS[key] = window
    return True


def reset() -> None:
    """Clear all buckets (used by tests)."""
    _BUCKETS.clear()


def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "?")


def rate_limit(bucket: str, config_key: str):
    """Decorator enforcing the configured per-minute limit per authenticated
    user (or per client IP when there is no user yet)."""

    def wrap(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            limit = current_app.config.get(config_key, 10)
            user = getattr(g, "user", None)
            key = f"{bucket}:{user.id if user else client_ip()}"
            if not hit(key, limit):
                return jsonify(
                    {"error": "rate_limit_exceeded",
                     "message": "Too many attempts. Try again later."}
                ), 429
            return fn(*args, **kwargs)

        return inner

    return wrap
