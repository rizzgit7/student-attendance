// Data models mirroring the Flask API responses (§13).
class UserSession {
  const UserSession({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    required this.institutionId,
    this.teacherId,
  });

  final int id;
  final String email;
  final String fullName;
  final String role;
  final int institutionId;
  final int? teacherId;

  bool get isStaff =>
      role == 'TEACHER' || role == 'HOD' ||
      role == 'INSTITUTION_ADMIN' || role == 'SUPER_ADMIN';

  factory UserSession.fromJson(Map<String, dynamic> json) => UserSession(
        id: json['id'] as int,
        email: json['email'] as String,
        fullName: json['full_name'] as String,
        role: json['role'] as String,
        institutionId: json['institution_id'] as int,
        teacherId: json['teacher_id'] as int?,
      );
}

class LoginResult {
  const LoginResult({required this.user, required this.accessToken,
    required this.refreshToken});

  final UserSession user;
  final String accessToken;
  final String refreshToken;

  factory LoginResult.fromJson(Map<String, dynamic> json) => LoginResult(
        user: UserSession.fromJson(json['user'] as Map<String, dynamic>),
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
      );
}

class AttendanceRecord {
  const AttendanceRecord({
    required this.id,
    required this.sessionId,
    required this.subject,
    required this.status,
    required this.recordedAt,
    required this.isCorrected,
  });

  final int id;
  final int sessionId;
  final String subject;
  final String status; // PRESENT | LATE
  final DateTime recordedAt;
  final bool isCorrected;

  factory AttendanceRecord.fromJson(Map<String, dynamic> json) =>
      AttendanceRecord(
        id: json['id'] as int,
        sessionId: json['session_id'] as int,
        subject: (json['subject'] ?? '—') as String,
        status: json['status'] as String,
        recordedAt: DateTime.parse(json['recorded_at'] as String),
        isCorrected: (json['is_corrected'] ?? false) as bool,
      );
}

class TodayClass {
  const TodayClass({
    required this.sessionId,
    required this.subject,
    required this.scheduledStart,
    required this.status,
    required this.marked,
    this.myStatus,
  });

  final int sessionId;
  final String subject;
  final DateTime scheduledStart;
  final String status;
  final bool marked;
  final String? myStatus;

  factory TodayClass.fromJson(Map<String, dynamic> json) => TodayClass(
        sessionId: json['session_id'] as int,
        subject: json['subject'] as String,
        scheduledStart:
            DateTime.parse(json['scheduled_start_at'] as String),
        status: json['status'] as String,
        marked: (json['marked'] ?? false) as bool,
        myStatus: json['my_status'] as String?,
      );
}

class Dashboard {
  const Dashboard({required this.classes, required this.percentage,
    required this.pendingLeaves});

  final List<TodayClass> classes;
  final double percentage;
  final int pendingLeaves;

  factory Dashboard.fromJson(Map<String, dynamic> json) => Dashboard(
        classes: (json['classes'] as List)
            .map((e) => TodayClass.fromJson(e as Map<String, dynamic>))
            .toList(),
        percentage: ((json['attendance'] as Map<String, dynamic>)
                ['percentage'] as num)
            .toDouble(),
        pendingLeaves: (json['pending_leaves'] as num?)?.toInt() ?? 0,
      );
}

class SubjectSummary {
  const SubjectSummary({required this.subject, required this.percentage,
    required this.total, required this.attended});

  final String subject;
  final double percentage;
  final int total;
  final int attended;

  factory SubjectSummary.fromJson(Map<String, dynamic> json) =>
      SubjectSummary(
        subject: json['subject'] as String,
        percentage: (json['percentage'] as num).toDouble(),
        total: json['total'] as int,
        attended: (json['present'] as int) + (json['late'] as int),
      );
}

class TeacherSession {
  const TeacherSession({
    required this.id,
    required this.subject,
    required this.section,
    required this.klass,
    required this.status,
    required this.presentCount,
    required this.lateCount,
    this.code,
    required this.codeSecondsLeft,
    required this.codeValid,
    required this.checkinCutoff,
    this.roster = const [],
  });

  final int id;
  final String subject;
  final String section;
  final String klass;
  final String status;
  final int presentCount;
  final int lateCount;
  final String? code;
  final int codeSecondsLeft;
  final bool codeValid;
  final DateTime checkinCutoff;

  /// Everyone enrolled in the class with their mark — only the live
  /// session endpoint sends it, so the teacher sees who is actually here.
  final List<RosterEntry> roster;

  factory TeacherSession.fromJson(Map<String, dynamic> json) =>
      TeacherSession(
        id: json['id'] as int,
        subject: (json['subject'] ?? '—') as String,
        section: (json['section'] ?? '—') as String,
        klass: (json['klass'] ?? '—') as String,
        status: json['status'] as String,
        presentCount: json['present_count'] as int,
        lateCount: json['late_count'] as int,
        code: json['code'] as String?,
        codeSecondsLeft: (json['code_seconds_left'] as num?)?.toInt() ?? 0,
        codeValid: (json['code_valid'] ?? false) as bool,
        checkinCutoff: DateTime.parse(json['checkin_cutoff'] as String),
        roster: (json['roster'] as List?)
                ?.map((e) => RosterEntry.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
      );
}

/// One student in a session's roll call.
class RosterEntry {
  const RosterEntry({
    required this.studentId,
    required this.rollNo,
    required this.fullName,
    required this.status,
    this.recordedAt,
    required this.isCorrected,
  });

  final int studentId;
  final String rollNo;
  final String? fullName;
  final String status; // PRESENT | LATE | NOT_MARKED
  final DateTime? recordedAt;
  final bool isCorrected;

  bool get marked => status != 'NOT_MARKED';

  factory RosterEntry.fromJson(Map<String, dynamic> json) => RosterEntry(
        studentId: json['student_id'] as int,
        rollNo: (json['roll_no'] ?? '') as String,
        fullName: json['full_name'] as String?,
        status: (json['status'] ?? 'NOT_MARKED') as String,
        recordedAt: json['recorded_at'] == null
            ? null
            : DateTime.parse(json['recorded_at'] as String),
        isCorrected: (json['is_corrected'] ?? false) as bool,
      );
}

class Labeled {
  const Labeled({required this.id, required this.name});
  final int id;
  final String name;

  factory Labeled.fromJson(Map<String, dynamic> json) => Labeled(
        id: json['id'] as int,
        name: json['name'] as String,
      );
}

/// GET /teacher/options — pick-lists plus the signed-in staff's assignments.
///
/// The API rejects a session with 403 unless the teacher is assigned to that
/// exact subject+section, so the UI must only offer combinations in here.
class StaffOptions {
  const StaffOptions({
    required this.sections,
    required this.subjects,
    required this.assignments,
    required this.isAdmin,
  });

  final List<Labeled> sections;
  final List<Labeled> subjects;
  final List<AssignedPair> assignments;
  final bool isAdmin;

  /// Admins bypass the assignment check, teachers do not.
  List<Labeled> get teachableSections => isAdmin
      ? sections
      : sections
          .where((s) => assignments.any((a) => a.sectionId == s.id))
          .toList();

  /// Subjects that may be started for [sectionId]. Without a section the
  /// full set the staff member is assigned to is returned.
  List<Labeled> subjectsFor(int? sectionId) {
    if (isAdmin) return subjects;
    if (sectionId == null) {
      return subjects
          .where((s) => assignments.any((a) => a.subjectId == s.id))
          .toList();
    }
    return subjects
        .where((s) => assignments
            .any((a) => a.subjectId == s.id && a.sectionId == sectionId))
        .toList();
  }

  factory StaffOptions.fromJson(Map<String, dynamic> json) => StaffOptions(
        sections: (json['sections'] as List)
            .map((e) => Labeled.fromJson(e as Map<String, dynamic>))
            .toList(),
        subjects: (json['subjects'] as List)
            .map((e) => Labeled.fromJson(e as Map<String, dynamic>))
            .toList(),
        assignments: (json['assignments'] as List)
            .map((e) => AssignedPair.fromJson(e as Map<String, dynamic>))
            .toList(),
        isAdmin: (json['is_admin'] ?? false) as bool,
      );
}

/// Teacher → subject ↔ section binding (§6).
class AssignedPair {
  const AssignedPair({required this.subjectId, required this.sectionId});
  final int subjectId;
  final int sectionId;

  factory AssignedPair.fromJson(Map<String, dynamic> json) => AssignedPair(
        subjectId: json['subject_id'] as int,
        sectionId: json['section_id'] as int,
      );
}

class LeaveRequest {
  const LeaveRequest({
    required this.id,
    required this.fromDate,
    required this.toDate,
    required this.reason,
    required this.status,
    this.student,
  });

  final int id;
  final String fromDate;
  final String toDate;
  final String reason;
  final String status;
  final String? student;

  factory LeaveRequest.fromJson(Map<String, dynamic> json) => LeaveRequest(
        id: json['id'] as int,
        fromDate: json['from_date'] as String,
        toDate: json['to_date'] as String,
        reason: json['reason'] as String,
        status: json['status'] as String,
        student: json['student'] as String?,
      );
}
