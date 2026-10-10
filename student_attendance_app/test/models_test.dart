import 'package:flutter_test/flutter_test.dart';
import 'package:student_attendance_app/models/models.dart';

void main() {
  test('TeacherSession parses API payload', () {
    final session = TeacherSession.fromJson({
      'id': 7,
      'subject': 'Mathematics',
      'section': 'A',
      'klass': 'Year 1',
      'status': 'OPEN',
      'present_count': 3,
      'late_count': 1,
      'code': '123456',
      'code_seconds_left': 42,
      'code_valid': true,
      'checkin_cutoff': '2026-10-10T09:20:00+00:00',
    });
    expect(session.id, 7);
    expect(session.code, '123456');
    expect(session.codeSecondsLeft, 42);
    expect(session.presentCount + session.lateCount, 4);
  });

  test('UserSession flags staff roles', () {
    final teacher = UserSession.fromJson({
      'id': 1,
      'email': 't@x.com',
      'full_name': 'T',
      'role': 'TEACHER',
      'institution_id': 1,
      'teacher_id': 2,
    });
    final student = UserSession.fromJson({
      'id': 2,
      'email': 's@x.com',
      'full_name': 'S',
      'role': 'STUDENT',
      'institution_id': 1,
      'teacher_id': null,
    });
    expect(teacher.isStaff, isTrue);
    expect(student.isStaff, isFalse);
  });
}
