/* PC Admin/Teacher dashboard (blueprint §4/§9/§19). Plain JS + Bootstrap. */
"use strict";

const API = "";  // same-origin Flask API
let tokens = null;
let me = null;
let options = { sections: [], subjects: [], assignments: [], is_admin: false };
let liveSessionId = null;
let pollTimer = null;

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function toast(message, ok = true) {
  const el = document.getElementById("toast");
  const div = document.createElement("div");
  div.className = `toast align-items-center text-bg-${ok ? "success" : "danger"} border-0 show`;
  div.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  el.appendChild(div);
  setTimeout(() => div.remove(), 4000);
}

function showError(id, message) {
  const el = document.getElementById(id);
  if (!message) { el.classList.add("d-none"); return; }
  el.textContent = message;
  el.classList.remove("d-none");
}

async function refreshTokens() {
  if (!tokens || !tokens.refresh_token) return false;
  const resp = await fetch(`${API}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!resp.ok) return false;
  tokens = await resp.json();
  sessionStorage.setItem("tokens", JSON.stringify(tokens));
  return true;
}

async function api(path, options2 = {}) {
  const opts = { ...options2, headers: { ...(options2.headers || {}) } };
  if (tokens) opts.headers["Authorization"] = `Bearer ${tokens.access_token}`;
  if (opts.body && typeof opts.body !== "string") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  let resp = await fetch(`${API}${path}`, opts);
  if (resp.status === 401 && tokens && (await refreshTokens())) {
    opts.headers["Authorization"] = `Bearer ${tokens.access_token}`;
    resp = await fetch(`${API}${path}`, opts);
  }
  const data = resp.status === 204 ? null : await resp.json().catch(() => null);
  return { ok: resp.ok, status: resp.status, data };
}

// ---------------------------------------------------------------------------
// auth
// ---------------------------------------------------------------------------

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("login-error", null);
  const resp = await fetch(`${API}/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: document.getElementById("login-email").value.trim(),
      password: document.getElementById("login-password").value,
    }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    showError("login-error", data.message || "Login failed");
    return;
  }
  tokens = data;
  me = data.user;
  sessionStorage.setItem("tokens", JSON.stringify(tokens));
  enterApp();
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await api("/auth/logout", { method: "POST", body: {} });
  tokens = null; me = null;
  sessionStorage.removeItem("tokens");
  location.reload();
});

function enterApp() {
  sessionStorage.setItem("me", JSON.stringify(me));
  document.getElementById("login-view").classList.add("d-none");
  document.getElementById("app-view").classList.remove("d-none");
  document.getElementById("whoami").textContent =
    `${me.full_name} · ${me.role.replace(/_/g, " ")}`;
  const admin = ["HOD", "INSTITUTION_ADMIN", "SUPER_ADMIN"].includes(me.role);
  if (admin) {
    document.getElementById("tab-people").classList.remove("d-none");
    document.getElementById("tab-academics").classList.remove("d-none");
    document.getElementById("tab-audit").classList.remove("d-none");
  }
  switchTab("sessions");
}

// ---------------------------------------------------------------------------
// tabs
// ---------------------------------------------------------------------------

function switchTab(name) {
  for (const tab of ["sessions", "people", "academics", "reports", "leave", "audit"]) {
    document.getElementById(`tab-${tab}-panel`).classList.toggle("d-none", tab !== name);
  }
  if (name === "sessions") loadSessions();
  if (name === "people") loadPeople();
  if (name === "academics") loadAcademics();
  if (name === "reports") loadReports();
  if (name === "leave") loadLeave();
  if (name === "audit") loadAudit();
}

document.querySelectorAll("[data-tab]").forEach((btn) =>
  btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

// ---------------------------------------------------------------------------
// sessions
// ---------------------------------------------------------------------------

async function loadOptions() {
  const resp = await api("/teacher/options");
  if (resp.ok) {
    options = resp.data;
    const sectionOpts = options.sections.map(
      (s) => `<option value="${s.id}">${s.name}</option>`).join("");
    const subjectOpts = options.subjects.map(
      (s) => `<option value="${s.id}">${s.name}</option>`).join("");
    for (const id of ["start-section", "stu-section", "sec-class",
                      "asg-section", "report-section"]) {
      const el = document.getElementById(id);
      if (el) el.innerHTML = sectionOpts;
    }
    document.getElementById("start-subject").innerHTML = subjectOpts;
    document.getElementById("asg-subject").innerHTML = subjectOpts;
  }
}

async function loadSessions() {
  await loadOptions();
  const resp = await api("/teacher/sessions");
  const rows = (resp.data?.sessions || []).map((s) => `
    <tr>
      <td>${s.id}</td><td>${s.subject || ""}</td>
      <td>${(s.klass || "") + " — " + (s.section || "")}</td>
      <td><span class="badge text-bg-${s.status === "OPEN" ? "success" : "secondary"}">${s.status}</span></td>
      <td>${s.present_count}</td><td>${s.late_count}</td>
      <td class="small">${(s.created_at || "").replace("T", " ").slice(0, 19)}</td>
    </tr>`).join("");
  document.getElementById("sessions-body").innerHTML =
    rows || `<tr><td colspan="7" class="text-secondary">No sessions yet</td></tr>`;
}

document.getElementById("start-btn").addEventListener("click", async () => {
  const body = {
    section_id: parseInt(document.getElementById("start-section").value, 10),
    subject_id: parseInt(document.getElementById("start-subject").value, 10),
  };
  const when = document.getElementById("start-when").value;
  if (when) body.scheduled_start_at = when;
  const resp = await api("/teacher/sessions", { method: "POST", body });
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Session started");
  showLive(resp.data);
  loadSessions();
});

function showLive(session) {
  liveSessionId = session.id;
  document.getElementById("live-card").style.display = "";
  document.getElementById("live-subject").textContent =
    `${session.subject} · ${session.klass} — ${session.section}`;
  document.getElementById("live-code").textContent = session.code || "——————";
  document.getElementById("live-countdown").textContent = session.code_seconds_left;
  document.getElementById("live-present").textContent = session.present_count;
  document.getElementById("live-late").textContent = session.late_count;
  document.getElementById("live-total").textContent = session.total_marked;
  document.getElementById("live-cutoff").textContent =
    (session.checkin_cutoff || "").replace("T", " ").slice(11, 19);
  clearInterval(pollTimer);
  pollTimer = setInterval(pollLive, 3000);
}

async function pollLive() {
  if (!liveSessionId) return;
  const resp = await api(`/teacher/sessions/${liveSessionId}`);
  if (!resp.ok) { clearInterval(pollTimer); return; }
  const s = resp.data;
  document.getElementById("live-countdown").textContent = s.code_seconds_left;
  document.getElementById("live-present").textContent = s.present_count;
  document.getElementById("live-late").textContent = s.late_count;
  document.getElementById("live-total").textContent = s.total_marked;
  if (!s.code_valid && s.status === "OPEN") {
    document.getElementById("live-code").textContent = "expired";
  }
}

document.getElementById("rotate-btn").addEventListener("click", async () => {
  if (!liveSessionId) return;
  const resp = await api(`/teacher/sessions/${liveSessionId}/rotate-code`,
                         { method: "POST", body: {} });
  if (!resp.ok) { toast(resp.data?.message || "Rotate failed", false); return; }
  document.getElementById("live-code").textContent = resp.data.code;
  toast("Code rotated");
});

document.getElementById("close-btn").addEventListener("click", async () => {
  if (!liveSessionId) return;
  const resp = await api(`/teacher/sessions/${liveSessionId}/close`,
                         { method: "POST", body: {} });
  if (!resp.ok) { toast(resp.data?.message || "Close failed", false); return; }
  clearInterval(pollTimer);
  toast("Session closed");
  loadSessions();
});

// ---------------------------------------------------------------------------
// people
// ---------------------------------------------------------------------------

async function loadPeople() {
  await loadOptions();
  const students = await api("/admin/students");
  document.getElementById("students-body").innerHTML =
    (students.data?.students || []).map((s) => `
      <tr><td>${s.roll_no}</td><td>${s.full_name}</td><td>${s.email}</td>
      <td>${s.class}</td><td>${s.section}</td></tr>`).join("") ||
    `<tr><td colspan="5" class="text-secondary">None yet</td></tr>`;
  const teachers = await api("/admin/teachers");
  document.getElementById("teachers-body").innerHTML =
    (teachers.data?.teachers || []).map((t) => `
      <tr><td>${t.employee_no || ""}</td><td>${t.full_name}</td><td>${t.email}</td></tr>`).join("") ||
    `<tr><td colspan="3" class="text-secondary">None yet</td></tr>`;
  const assignmentTeachers = await api("/admin/teachers");
  document.getElementById("asg-teacher").innerHTML =
    (assignmentTeachers.data?.teachers || []).map(
      (t) => `<option value="${t.id}">${t.full_name}</option>`).join("");
}

document.getElementById("add-student").addEventListener("click", async () => {
  const resp = await api("/admin/students", { method: "POST", body: {
    email: document.getElementById("stu-email").value.trim(),
    full_name: document.getElementById("stu-name").value.trim(),
    password: document.getElementById("stu-pass").value,
    roll_no: document.getElementById("stu-roll").value.trim(),
    section_id: parseInt(document.getElementById("stu-section").value, 10),
  }});
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Student created");
  loadPeople();
});

document.getElementById("add-teacher").addEventListener("click", async () => {
  const resp = await api("/admin/teachers", { method: "POST", body: {
    email: document.getElementById("tch-email").value.trim(),
    full_name: document.getElementById("tch-name").value.trim(),
    password: document.getElementById("tch-pass").value,
    employee_no: document.getElementById("tch-no").value.trim(),
  }});
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Teacher created");
  loadPeople();
});

// ---------------------------------------------------------------------------
// academics
// ---------------------------------------------------------------------------

async function loadAcademics() {
  await loadOptions();
  const classes = await api("/admin/classes");
  document.getElementById("classes-body").innerHTML =
    (classes.data?.classes || []).map((k) => `
      <tr><td>${k.name}</td><td>${k.program}</td>
      <td>${(k.sections || []).map((s) => s.name).join(", ") || "—"}</td></tr>`).join("") ||
    `<tr><td colspan="3" class="text-secondary">None yet</td></tr>`;
  document.getElementById("sec-class").innerHTML =
    (classes.data?.classes || []).map(
      (k) => `<option value="${k.id}">${k.name}</option>`).join("");

  const assignments = await api("/admin/assignments");
  const bySubject = new Map(options.subjects.map((s) => [s.id, s]));
  const assignedKeys = new Set();
  const rows = (assignments.data?.assignments || []).map((a) => {
    assignedKeys.add(`${a.subject_id}:${a.section_id}`);
    return `<tr><td>${a.subject}</td><td>${bySubject.get(a.subject_id)?.code || ""}</td>
      <td>${a.section}</td><td>${a.teacher}</td>
      <td><button class="btn btn-sm btn-outline-danger" disabled>×</button></td></tr>`;
  }).join("");
  const sectionById = new Map(options.sections.map((s) => [s.id, s.name]));
  for (const s of options.subjects) {
    for (const sec of options.sections) {
      if (!assignedKeys.has(`${s.id}:${sec.id}`)) {
        rows += `<tr class="text-secondary"><td>${s.name}</td><td>${s.code}</td>
          <td>${sec.name}</td><td colspan="2">unassigned</td></tr>`;
      }
    }
  }
  document.getElementById("subjects-body").innerHTML = rows ||
    `<tr><td colspan="5" class="text-secondary">None yet</td></tr>`;
}

document.getElementById("add-class").addEventListener("click", async () => {
  const resp = await api("/admin/classes", { method: "POST", body: {
    name: document.getElementById("cls-name").value.trim(),
    program: { name: document.getElementById("cls-prog").value.trim() || "General" },
  }});
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Class created");
  loadAcademics();
});

document.getElementById("add-section").addEventListener("click", async () => {
  const resp = await api("/admin/sections", { method: "POST", body: {
    name: document.getElementById("sec-name").value.trim(),
    class_id: parseInt(document.getElementById("sec-class").value, 10),
  }});
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Section created");
  loadAcademics();
});

document.getElementById("add-subject").addEventListener("click", async () => {
  const resp = await api("/admin/subjects", { method: "POST", body: {
    name: document.getElementById("sub-name").value.trim(),
  }});
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Subject created");
  loadAcademics();
});

document.getElementById("add-assignment").addEventListener("click", async () => {
  const resp = await api("/admin/assignments", { method: "POST", body: {
    teacher_id: parseInt(document.getElementById("asg-teacher").value, 10),
    subject_id: parseInt(document.getElementById("asg-subject").value, 10),
    section_id: parseInt(document.getElementById("asg-section").value, 10),
  }});
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Assignment created");
  loadAcademics();
});

// ---------------------------------------------------------------------------
// reports
// ---------------------------------------------------------------------------

function today() { return new Date().toISOString().slice(0, 10); }

async function loadReports() {
  await loadOptions();
  const dateInput = document.getElementById("report-date");
  if (!dateInput.value) dateInput.value = today();
  const daily = await api(`/reports/attendance?date=${dateInput.value}`);
  document.getElementById("report-body").innerHTML =
    (daily.data?.sessions || []).map((s) => `
      <tr><td>${s.subject}</td><td>${s.section}</td><td>${s.status}</td>
      <td>${s.enrolled}</td><td class="text-success">${s.present}</td>
      <td class="text-warning">${s.late}</td><td>${s.not_marked}</td></tr>`).join("") ||
    `<tr><td colspan="7" class="text-secondary">No sessions for this date</td></tr>`;
}

document.getElementById("report-refresh").addEventListener("click", loadReports);

document.getElementById("class-report-btn").addEventListener("click", async () => {
  const sectionId = document.getElementById("report-section").value;
  const resp = await api(`/reports/class/${sectionId}`);
  const body = document.getElementById("class-report-body");
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  body.innerHTML = (resp.data?.students || []).map((s) => `
    <tr>
      <td>${s.roll_no}</td><td>${s.full_name}</td>
      <td class="text-success">${s.present}</td><td class="text-warning">${s.late}</td>
      <td>${s.missed}</td><td>${s.percentage}%</td>
      <td><button class="btn btn-sm btn-outline-secondary"
            onclick="showStudentRecords(${s.student_id})">Records</button></td>
    </tr>`).join("");
});

window.showStudentRecords = async function (studentId) {
  const resp = await api(`/reports/student/${studentId}`);
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  const lines = (resp.data.records || []).map((r) => `
    <li class="list-group-item d-flex justify-content-between align-items-center">
      ${r.subject} · ${r.recorded_at.replace("T", " ").slice(0, 16)}
      ${r.is_corrected ? '<span class="badge text-bg-secondary">corrected</span>' : ""}
      <span class="badge text-bg-${r.status === "PRESENT" ? "success" : "warning"}">${r.status}</span>
      <button class="btn btn-sm btn-outline-primary"
        onclick="correctRecord(${r.id}, '${r.status}')">Correct</button>
    </li>`).join("");
  alert(`${resp.data.student.full_name} (${resp.data.student.roll_no})\n\n` +
        (lines ? `<ul class="list-group">${lines}</ul>` : "No records yet"));
};

window.correctRecord = async function (recordId, current) {
  const target = current === "PRESENT" ? "LATE" : "PRESENT";
  const reason = prompt(`Correct ${current} → ${target}. Reason (required):`);
  if (!reason) return;
  const resp = await api(`/admin/attendance/${recordId}/correct`, {
    method: "POST", body: { new_status: target, reason },
  });
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast("Correction saved to audit log");
};

// ---------------------------------------------------------------------------
// leave
// ---------------------------------------------------------------------------

async function loadLeave() {
  const resp = await api("/leave/requests");
  const staff = me.role !== "STUDENT";
  document.getElementById("leave-body").innerHTML =
    (resp.data?.requests || []).map((l) => `
      <tr>
        <td>${l.student || ""} ${l.roll_no ? `(${l.roll_no})` : ""}</td>
        <td>${l.from_date}</td><td>${l.to_date}</td><td>${l.reason}</td>
        <td><span class="badge text-bg-${l.status === "APPROVED" ? "success" : l.status === "REJECTED" ? "danger" : "secondary"}">${l.status}</span></td>
        <td>${staff && l.status === "PENDING" ? `
          <button class="btn btn-sm btn-success" onclick="reviewLeave(${l.id}, 'APPROVED')">✓</button>
          <button class="btn btn-sm btn-outline-danger" onclick="reviewLeave(${l.id}, 'REJECTED')">✗</button>` : ""}</td>
      </tr>`).join("") ||
    `<tr><td colspan="6" class="text-secondary">No leave requests</td></tr>`;
}

window.reviewLeave = async function (id, decision) {
  const resp = await api(`/leave/requests/${id}/review`, {
    method: "POST", body: { decision },
  });
  if (!resp.ok) { toast(resp.data?.message || "Failed", false); return; }
  toast(`Leave ${decision.toLowerCase()}`);
  loadLeave();
};

// ---------------------------------------------------------------------------
// audit
// ---------------------------------------------------------------------------

async function loadAudit() {
  const resp = await api("/admin/audit-logs");
  document.getElementById("audit-body").innerHTML =
    (resp.data?.logs || []).map((l) => `
      <tr><td class="small">${l.created_at.replace("T", " ").slice(0, 19)}</td>
      <td>${l.actor || ""}</td><td>${l.action}</td>
      <td>${l.entity_type}#${l.entity_id}</td><td>${l.reason || ""}</td></tr>`).join("") ||
    `<tr><td colspan="5" class="text-secondary">Empty</td></tr>`;
}

// ---------------------------------------------------------------------------
// boot: restore session
// ---------------------------------------------------------------------------

(async function boot() {
  const storedTokens = sessionStorage.getItem("tokens");
  const storedMe = sessionStorage.getItem("me");
  if (!storedTokens || !storedMe) return;
  tokens = JSON.parse(storedTokens);
  me = JSON.parse(storedMe);
  // probe that the access/refresh pair is still valid
  const probe = await api("/teacher/options");
  if (probe.ok) {
    enterApp();
  } else {
    tokens = null; me = null;
    sessionStorage.clear();
  }
})();
