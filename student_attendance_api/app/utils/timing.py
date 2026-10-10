"""Attendance timing policy (blueprint §10–§11).

Server time is authoritative; values are institution-configurable:
  0 .. present_window   -> PRESENT
  .. + late_window      -> LATE
  after cutoff          -> self check-in closed
"""
from datetime import timezone

from app.models import (
    AttendanceSession, MarkStatus, SessionStatus, as_utc, utcnow,
)


class CheckinError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def effective_now(now=None):
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now


def classify(scheduled_start, institution, now=None):
    """Return PRESENT / LATE / None (None = after cutoff, closed)."""
    now = effective_now(now)
    scheduled_start = as_utc(scheduled_start)
    from datetime import timedelta
    present_until = scheduled_start + timedelta(
        minutes=institution.present_window_minutes
    )
    late_until = present_until + timedelta(
        minutes=institution.late_window_minutes
    )
    if now <= present_until:
        return MarkStatus.PRESENT
    if now <= late_until:
        return MarkStatus.LATE
    return None


def session_open(session: AttendanceSession, now=None):
    if session.status != SessionStatus.OPEN:
        raise CheckinError("session_closed",
                           "This attendance session is closed.", 409)
    inst = session.institution
    if effective_now(now) > as_utc(
        inst.checkin_cutoff(as_utc(session.scheduled_start_at))
    ):
        raise CheckinError("checkin_window_closed",
                           "The check-in window for this session has passed.",
                           409)
