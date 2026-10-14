// The teacher pick-lists must only offer combinations the API accepts:
// POST /teacher/sessions answers 403 for an unassigned subject/section.
//
// The payload below is a verbatim capture of GET /teacher/options for the
// production teacher account, where only Mathematics and Physics in
// "Year 1 — A" are assigned.
import 'package:flutter_test/flutter_test.dart';
import 'package:student_attendance_app/models/models.dart';

void main() {
  const productionPayload = {
    'assignments': [
      {'section_id': 1, 'subject_id': 1},
      {'section_id': 1, 'subject_id': 2},
    ],
    'is_admin': false,
    'sections': [
      {'class_id': 1, 'id': 1, 'name': 'Year 1 — A'},
      {'class_id': 3, 'id': 2, 'name': '3 — 5th sem'},
      {'class_id': 3, 'id': 3, 'name': '3 — 5th sem'},
    ],
    'subjects': [
      {'code': 'MATH101', 'id': 1, 'name': 'Mathematics'},
      {'code': 'PHY101', 'id': 2, 'name': 'Physics'},
      {'code': 'INTERNET O', 'id': 5, 'name': 'Internet of things'},
      {'code': 'CYBER SECU', 'id': 8, 'name': 'Cyber security'},
    ],
  };

  test('teacher only sees sections they are assigned to', () {
    final options = StaffOptions.fromJson(productionPayload);
    expect(options.isAdmin, isFalse);
    expect(
      options.teachableSections.map((s) => s.id),
      [1],
      reason: 'unassigned sections would only produce a 403',
    );
  });

  test('teacher only sees subjects assigned to the chosen section', () {
    final options = StaffOptions.fromJson(productionPayload);
    expect(options.subjectsFor(1).map((s) => s.name),
        ['Mathematics', 'Physics']);
    expect(options.subjectsFor(3), isEmpty,
        reason: 'the new class has no assignments yet');
    expect(options.subjectsFor(null).map((s) => s.name),
        ['Mathematics', 'Physics'],
        reason: 'unassigned subjects must not be offered either');
  });

  test('admins keep the full pick-lists', () {
    final options = StaffOptions.fromJson({...productionPayload,
      'is_admin': true});
    expect(options.teachableSections, hasLength(3));
    expect(options.subjectsFor(3), hasLength(4));
  });
}
