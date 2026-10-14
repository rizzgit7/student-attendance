"""End-to-end tests for master data, dashboards, leave and reports
(blueprint §8, §9, §13)."""
from tests.conftest import create_session, login


def _headers(body):
    return {"Authorization": f"Bearer {body['access_token']}"}


# ---------------------------------------------------------------------------
# Admin master data (§13)
# ---------------------------------------------------------------------------

def test_admin_creates_class_section_subject_student(client, seed):
    _, admin = login(client, "admin@test.com", "AdminPass1!")
    h = _headers(admin)

    klass = client.post("/admin/classes",
                        json={"name": "Year 2",
                              "program": {"name": "BSc", "code": "BSC2"}},
                        headers=h)
    assert klass.status_code == 201
    section = client.post("/admin/sections",
                          json={"name": "A",
                                "class_id": klass.get_json()["id"]},
                          headers=h)
    assert section.status_code == 201
    subject = client.post("/admin/subjects", json={"name": "Physics"},
                          headers=h)
    assert subject.status_code == 201
    student = client.post("/admin/students", json={
        "email": "new@student.com", "password": "StrongPass1!",
        "full_name": "New Student", "roll_no": "R999",
        "section_id": section.get_json()["id"],
    }, headers=h)
    assert student.status_code == 201

    # the new student can log in immediately and see their classes
    _, sb = login(client, "new@student.com", "StrongPass1!")
    classes = client.get("/student/classes", headers=_headers(sb))
    assert classes.status_code == 200
    body = classes.get_json()
    assert body["section"]["name"] == "A"
    assert body["roll_no"] == "R999"


def test_admin_creates_teacher_and_assignment(client, seed):
    _, admin = login(client, "admin@test.com", "AdminPass1!")
    h = _headers(admin)
    teacher = client.post("/admin/teachers", json={
        "email": "t2@test.com", "password": "StrongPass1!",
        "full_name": "Second Teacher", "employee_no": "T002",
    }, headers=h)
    assert teacher.status_code == 201
    assignment = client.post("/admin/assignments", json={
        "teacher_id": teacher.get_json()["teacher_id"],
        "subject_id": seed["subject"].id,
        "section_id": seed["section2"].id,
    }, headers=h)
    assert assignment.status_code == 201

    # unassigned teacher cannot start a session for section2 + other subject
    _, t2 = login(client, "t2@test.com", "StrongPass1!")
    forbidden = client.post("/teacher/sessions", json={
        "section_id": seed["section2"].id,
        "subject_id": seed["subject"].id,
    }, headers=_headers(t2))  # assignment exists for section2 -> allowed
    assert forbidden.status_code == 201

    wrong = client.post("/teacher/sessions", json={
        "section_id": seed["section1"].id,  # assigned to first teacher
        "subject_id": seed["subject"].id,
    }, headers=_headers(t2))
    assert wrong.status_code == 403


def test_duplicate_email_rejected(client, seed):
    _, admin = login(client, "admin@test.com", "AdminPass1!")
    resp = client.post("/admin/students", json={
        "email": "s1@test.com", "password": "x", "full_name": "Dup",
        "roll_no": "R777", "section_id": seed["section1"].id,
    }, headers=_headers(admin))
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Student dashboard (§8)
# ---------------------------------------------------------------------------

def test_student_dashboard_and_history(client, seed):
    _, teacher = login(client, "teacher@test.com", "TeachPass1!")
    session = create_session(client, _headers(teacher),
                             seed["section1"].id, seed["subject"].id)
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    h = _headers(s1)

    dash = client.get("/student/dashboard", headers=h)
    assert dash.status_code == 200
    assert len(dash.get_json()["classes"]) == 1
    assert dash.get_json()["classes"][0]["session_id"] == session["id"]

    checkin = client.post("/attendance/check-in",
                          json={"code": session["code"],
                                "session_id": session["id"]},
                          headers=h)
    assert checkin.status_code == 201

    today = client.get("/attendance/today", headers=h)
    assert today.status_code == 200
    assert len(today.get_json()["records"]) == 1

    history = client.get("/attendance/history", headers=h)
    assert history.status_code == 200
    assert history.get_json()["total"] == 1

    summary = client.get("/attendance/summary", headers=h)
    assert summary.status_code == 200
    assert summary.get_json()["overall"]["percentage"] == 100.0
    assert summary.get_json()["subjects"][0]["subject"] == "Mathematics"


def test_student_in_other_section_sees_no_classes(client, seed):
    _, s3 = login(client, "s3@test.com", "StudentPass1!")
    dash = client.get("/student/dashboard", headers=_headers(s3))
    assert dash.status_code == 200
    assert dash.get_json()["classes"] == []


# ---------------------------------------------------------------------------
# Teacher dashboard (§9)
# ---------------------------------------------------------------------------

def test_teacher_session_history_and_counts(client, seed):
    _, teacher = login(client, "teacher@test.com", "TeachPass1!")
    h = _headers(teacher)
    session = create_session(client, h,
                             seed["section1"].id, seed["subject"].id)
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    client.post("/attendance/check-in",
                json={"code": session["code"], "session_id": session["id"]},
                headers=_headers(s1))

    view = client.get(f"/teacher/sessions/{session['id']}", headers=h)
    assert view.status_code == 200
    body = view.get_json()
    assert body["present_count"] == 1
    assert body["total_marked"] == 1
    assert body["code"] == session["code"]
    assert body["status"] == "OPEN"

    history = client.get("/teacher/sessions", headers=h)
    assert history.status_code == 200
    assert len(history.get_json()["sessions"]) == 1

    closed = client.post(f"/teacher/sessions/{session['id']}/close",
                         headers=h)
    assert closed.status_code == 200
    again = client.post(f"/teacher/sessions/{session['id']}/close",
                        headers=h)
    assert again.status_code == 409


def test_unassigned_teacher_cannot_open_session(client, seed):
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    resp = client.post("/teacher/sessions", json={
        "section_id": seed["section1"].id,
        "subject_id": seed["subject"].id,
    }, headers=_headers(s1))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Leave workflow (§13)
# ---------------------------------------------------------------------------

def test_leave_request_flow(client, seed):
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    h = _headers(s1)
    created = client.post("/leave/requests", json={
        "from_date": "2026-10-12", "to_date": "2026-10-13",
        "reason": "Family event",
    }, headers=h)
    assert created.status_code == 201
    leave_id = created.get_json()["id"]

    mine = client.get("/leave/requests", headers=h)
    assert mine.status_code == 200
    assert len(mine.get_json()["requests"]) == 1

    _, admin = login(client, "admin@test.com", "AdminPass1!")
    seen = client.get("/leave/requests", headers=_headers(admin))
    assert len(seen.get_json()["requests"]) == 1

    approved = client.post(f"/leave/requests/{leave_id}/review",
                           json={"decision": "APPROVED"},
                           headers=_headers(admin))
    assert approved.status_code == 200
    assert approved.get_json()["status"] == "APPROVED"

    # reviewing twice is rejected
    second = client.post(f"/leave/requests/{leave_id}/review",
                         json={"decision": "REJECTED"},
                         headers=_headers(admin))
    assert second.status_code == 409


def test_leave_validation(client, seed):
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    bad = client.post("/leave/requests", json={
        "from_date": "2026-10-13", "to_date": "2026-10-12",
        "reason": "backwards",
    }, headers=_headers(s1))
    assert bad.status_code == 400


# ---------------------------------------------------------------------------
# Reports (§13 GET /reports/*)
# ---------------------------------------------------------------------------

def test_reports_endpoints(client, seed):
    _, teacher = login(client, "teacher@test.com", "TeachPass1!")
    h = _headers(teacher)
    session = create_session(client, h,
                             seed["section1"].id, seed["subject"].id)
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    client.post("/attendance/check-in",
                json={"code": session["code"], "session_id": session["id"]},
                headers=_headers(s1))
    _, admin = login(client, "admin@test.com", "AdminPass1!")
    ah = _headers(admin)

    daily = client.get("/reports/attendance", headers=ah)
    assert daily.status_code == 200
    assert daily.get_json()["totals"]["present"] == 1

    klass = client.get(f"/reports/class/{seed['section1'].id}", headers=ah)
    assert klass.status_code == 200
    rows = klass.get_json()["students"]
    assert len(rows) == 2
    s1_row = next(r for r in rows if r["roll_no"] == "R001")
    assert s1_row["present"] == 1
    assert s1_row["percentage"] == 100.0

    student = client.get(f"/reports/student/{seed['s1'].id}", headers=ah)
    assert student.status_code == 200
    assert student.get_json()["total_marked"] == 1

    # students cannot pull reports
    _, s1b = login(client, "s1@test.com", "StudentPass1!")
    denied = client.get("/reports/attendance", headers=_headers(s1b))
    assert denied.status_code == 403


def test_cross_tenant_report_denied(client, seed):
    _, admin = login(client, "admin@test.com", "AdminPass1!")
    resp = client.get(f"/reports/class/{seed['section_b'].id}",
                      headers=_headers(admin))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Live session roll call (who is actually in the room)
# ---------------------------------------------------------------------------

def test_live_session_returns_full_roll_call(client, seed):
    _, teacher = login(client, "teacher@test.com", "TeachPass1!")
    h = _headers(teacher)
    session = create_session(client, h,
                             seed["section1"].id, seed["subject"].id)
    # the start response carries the roll call too, so no first poll is needed
    assert "roster" in session
    assert [r["roll_no"] for r in session["roster"]] == ["R001", "R002"]
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    client.post("/attendance/check-in",
                json={"code": session["code"], "session_id": session["id"]},
                headers=_headers(s1))

    view = client.get(f"/teacher/sessions/{session['id']}", headers=h)
    assert view.status_code == 200
    roster = view.get_json()["roster"]

    # every enrolled student, ordered by roll number, absentees included
    assert [r["roll_no"] for r in roster] == ["R001", "R002"]
    by_roll = {r["roll_no"]: r for r in roster}
    assert by_roll["R001"]["full_name"] == "Student 1"
    assert by_roll["R001"]["status"] == "PRESENT"
    assert by_roll["R001"]["recorded_at"]
    assert by_roll["R002"]["status"] == "NOT_MARKED"
    assert by_roll["R002"]["recorded_at"] is None
    # counts and roster must agree
    marked = sum(1 for r in roster if r["status"] != "NOT_MARKED")
    assert marked == view.get_json()["total_marked"]


def test_roll_call_stays_off_history_and_is_staff_only(client, seed):
    _, teacher = login(client, "teacher@test.com", "TeachPass1!")
    h = _headers(teacher)
    session = create_session(client, h,
                             seed["section1"].id, seed["subject"].id)

    # the 100-row history must not carry a roster per session
    history = client.get("/teacher/sessions", headers=h)
    assert history.status_code == 200
    assert "roster" not in history.get_json()["sessions"][0]

    # students may not read the class roll call
    _, s1 = login(client, "s1@test.com", "StudentPass1!")
    denied = client.get(f"/teacher/sessions/{session['id']}",
                        headers=_headers(s1))
    assert denied.status_code == 403
