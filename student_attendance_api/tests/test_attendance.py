"""Blueprint §17 test matrix: code validity, membership, duplicates,
timing windows, closed sessions, concurrency, authz, tenant isolation,
token expiry, corrections, rate limiting."""
from datetime import timedelta

import jwt
import pytest

from app.extensions import db
from app.models import AttendanceRecord, AttendanceSession, AuditLog, utcnow
from tests.conftest import create_session, login


def _student_headers(client, email):
    headers, body = login(client, email, "StudentPass1!")
    return headers, body


def _checkin(client, headers, code, session_id=None):
    payload = {"code": code}
    if session_id is not None:
        payload["session_id"] = session_id
    return client.post("/attendance/check-in", json=payload, headers=headers)


# ---------------------------------------------------------------------------
# §17: valid / invalid / expired code
# ---------------------------------------------------------------------------

def test_valid_code_marks_present(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    headers, _ = _student_headers(client, "s1@test.com")
    resp = _checkin(client, headers, session["code"], session["id"])
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "PRESENT"


def test_invalid_code_rejected(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    headers, _ = _student_headers(client, "s1@test.com")
    resp = _checkin(client, headers, "000000", session["id"])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_code"


def test_expired_code_rejected(client, seed, app):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    with app.app_context():
        record = db.session.get(AttendanceSession, session["id"])
        record.code_expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    headers, _ = _student_headers(client, "s1@test.com")
    resp = _checkin(client, headers, session["code"], session["id"])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "code_expired"


# ---------------------------------------------------------------------------
# §17: wrong class/section + cross-institution
# ---------------------------------------------------------------------------

def test_wrong_class_section_rejected(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    headers, _ = _student_headers(client, "s3@test.com")  # section B
    resp = _checkin(client, headers, session["code"], session["id"])
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "wrong_class"


def test_cross_institution_checkin_rejected(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    headers, _ = _student_headers(client, "sb@test.com")  # institution B
    resp = _checkin(client, headers, session["code"], session["id"])
    assert resp.status_code == 404  # tenant isolation: resource invisible


def test_cross_institution_admin_cannot_see_session(client, seed):
    # Teacher B (other tenant) starts a session in their own institution
    _, tb = login(client, "teachb@test.com", "TeachPass1!")
    session_b = create_session(client,
                               {"Authorization":
                                f"Bearer {tb['access_token']}"},
                               seed["section_b"].id, seed["subject_b"].id)
    # Teacher A from institution A must not read it
    _, ta = login(client, "teacher@test.com", "TeachPass1!")
    resp = client.get(f"/teacher/sessions/{session_b['id']}",
                      headers={"Authorization":
                               f"Bearer {ta['access_token']}"})
    assert resp.status_code == 404
    # ... nor close it
    close = client.post(f"/teacher/sessions/{session_b['id']}/close",
                        headers={"Authorization":
                                 f"Bearer {ta['access_token']}"})
    assert close.status_code == 404


# ---------------------------------------------------------------------------
# §17: duplicate submission (app logic + DB constraint)
# ---------------------------------------------------------------------------

def test_duplicate_submission_conflict(client, seed, app):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    headers, _ = _student_headers(client, "s1@test.com")
    first = _checkin(client, headers, session["code"], session["id"])
    assert first.status_code == 201
    # simulate a client retry after network interruption (§17)
    retry = _checkin(client, headers, session["code"], session["id"])
    assert retry.status_code == 409
    assert retry.get_json()["error"] == "already_marked"
    # and confirm only one row exists despite the retry
    with app.app_context():
        count = AttendanceRecord.query.filter_by(
            session_id=session["id"], student_id=seed["s1"].id
        ).count()
    assert count == 1


# ---------------------------------------------------------------------------
# §17: late window + after-cutoff
# ---------------------------------------------------------------------------

def test_late_window_marks_late(client, seed, app):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    with app.app_context():
        record = db.session.get(AttendanceSession, session["id"])
        # class started 11 minutes ago: past 10-min present window,
        # still inside the 10-min late window (§11)
        record.scheduled_start_at = utcnow() - timedelta(minutes=11)
        db.session.commit()
    headers, _ = _student_headers(client, "s1@test.com")
    resp = _checkin(client, headers, session["code"], session["id"])
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "LATE"


def test_after_cutoff_checkin_closes(client, seed, app):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    with app.app_context():
        record = db.session.get(AttendanceSession, session["id"])
        record.scheduled_start_at = utcnow() - timedelta(minutes=30)
        record.code_expires_at = utcnow() + timedelta(seconds=60)
        db.session.commit()
    headers, _ = _student_headers(client, "s1@test.com")
    resp = _checkin(client, headers, session["code"], session["id"])
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "checkin_window_closed"


# ---------------------------------------------------------------------------
# §17: closed session
# ---------------------------------------------------------------------------

def test_closed_session_rejects_checkin(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    teacher_headers = {"Authorization":
                       f"Bearer {teacher_body['access_token']}"}
    session = create_session(client, teacher_headers,
                             seed["section1"].id, seed["subject"].id)
    close = client.post(f"/teacher/sessions/{session['id']}/close",
                        headers=teacher_headers)
    assert close.status_code == 200
    headers, _ = _student_headers(client, "s1@test.com")
    resp = _checkin(client, headers, session["code"], session["id"])
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "session_closed"


# ---------------------------------------------------------------------------
# §17: two students submitting simultaneously
# ---------------------------------------------------------------------------

def test_two_students_submit_together(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    h1, _ = _student_headers(client, "s1@test.com")
    h2, _ = _student_headers(client, "s2@test.com")
    r1 = _checkin(client, h1, session["code"], session["id"])
    r2 = _checkin(client, h2, session["code"], session["id"])
    assert r1.status_code == 201
    assert r2.status_code == 201
    status = client.get(f"/teacher/sessions/{session['id']}",
                        headers={"Authorization":
                                 f"Bearer {teacher_body['access_token']}"})
    assert status.get_json()["present_count"] == 2


# ---------------------------------------------------------------------------
# §17: unauthorized API access + token expiry
# ---------------------------------------------------------------------------

def test_unauthorized_access_rejected(client, seed):
    assert client.get("/attendance/today").status_code == 401
    assert client.get("/student/dashboard").status_code == 401
    assert client.post("/teacher/sessions",
                       json={}).status_code == 401
    assert client.post("/admin/classes",
                       json={}).status_code == 401


def test_garbage_token_rejected(client, seed):
    resp = client.get("/attendance/today",
                      headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401


def test_expired_token_rejected(client, seed, app):
    user = seed["s1"].user
    expired = jwt.encode(
        {"sub": str(user.id), "role": user.role,
         "inst": user.institution_id, "type": "access",
         "exp": utcnow() - timedelta(minutes=5)},
        app.config["SECRET_KEY"], algorithm="HS256",
    )
    resp = client.get("/attendance/today",
                      headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_role_guard_blocks_student_from_admin(client, seed):
    headers, _ = _student_headers(client, "s1@test.com")
    resp = client.post("/admin/classes", json={"name": "Hack"},
                       headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# §17: admin correction requires reason + writes audit
# ---------------------------------------------------------------------------

def test_correction_requires_reason_and_writes_audit(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    headers, _ = _student_headers(client, "s1@test.com")
    checkin = _checkin(client, headers, session["code"], session["id"])
    record_id = checkin.get_json()["record"]["id"]

    _, admin_body = login(client, "admin@test.com", "AdminPass1!")
    admin_headers = {"Authorization":
                     f"Bearer {admin_body['access_token']}"}

    missing_reason = client.post(
        f"/admin/attendance/{record_id}/correct",
        json={"new_status": "LATE"}, headers=admin_headers)
    assert missing_reason.status_code == 400

    ok = client.post(
        f"/admin/attendance/{record_id}/correct",
        json={"new_status": "LATE", "reason": "Student arrived at 09:15"},
        headers=admin_headers)
    assert ok.status_code == 200
    body = ok.get_json()
    assert body["status"] == "LATE"
    assert body["previous_status"] == "PRESENT"
    assert body["is_corrected"] is True

    logs = AuditLog.query.filter_by(entity_id=record_id).all()
    assert len(logs) == 1
    assert logs[0].action == "attendance.correct"
    assert "arrived at 09:15" in logs[0].reason


# ---------------------------------------------------------------------------
# §17: rate limiting on code attempts + login
# ---------------------------------------------------------------------------

def test_rate_limit_on_checkin_attempts(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client,
                             {"Authorization":
                              f"Bearer {teacher_body['access_token']}"},
                             seed["section1"].id, seed["subject"].id)
    headers, _ = _student_headers(client, "s2@test.com")
    last = None
    for _ in range(11):
        last = _checkin(client, headers, "999999", session["id"])
        if last.status_code == 429:
            break
    assert last is not None and last.status_code == 429, \
        "expected the rate limiter to trip"
    assert last.get_json()["error"] == "rate_limit_exceeded"


def test_rate_limit_on_login(client, seed):
    for i in range(11):
        resp = client.post("/auth/login",
                           json={"email": "admin@test.com",
                                 "password": "wrong"})
        if resp.status_code == 429:
            break
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# §17: refresh flow (logout revokes refresh token)
# ---------------------------------------------------------------------------

def test_refresh_rotation_and_logout_revocation(client, seed):
    _, body = login(client, "s1@test.com", "StudentPass1!")
    refresh = body["refresh_token"]

    rotated = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200
    new_refresh = rotated.get_json()["refresh_token"]

    # old refresh token was rotated away → revoked
    reuse = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401

    # logout revokes the current refresh token
    logout = client.post("/auth/logout", json={"refresh_token": new_refresh},
                         headers={"Authorization":
                                  f"Bearer {rotated.get_json()['access_token']}"})
    assert logout.status_code == 200
    after = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


# ---------------------------------------------------------------------------
# §17: network interruption / session visibility
# ---------------------------------------------------------------------------

def test_session_code_rotation(client, seed):
    _, teacher_body = login(client, "teacher@test.com", "TeachPass1!")
    teacher_headers = {"Authorization":
                       f"Bearer {teacher_body['access_token']}"}
    session = create_session(client, teacher_headers,
                             seed["section1"].id, seed["subject"].id)
    resp = client.post(f"/teacher/sessions/{session['id']}/rotate-code",
                       headers=teacher_headers)
    assert resp.status_code == 200
    assert resp.get_json()["code"] != session["code"]
    # old code no longer works
    headers, _ = _student_headers(client, "s1@test.com")
    old = _checkin(client, headers, session["code"], session["id"])
    assert old.status_code == 400
    new = _checkin(client, headers, resp.get_json()["code"], session["id"])
    assert new.status_code == 201
