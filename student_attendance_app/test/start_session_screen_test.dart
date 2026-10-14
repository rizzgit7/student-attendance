// The start-session screen must never offer a class/subject combination the
// API rejects with 403, and must explain the empty case instead of throwing.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_attendance_app/features/teacher/start_session_screen.dart';
import 'package:student_attendance_app/features/teacher/teacher_home_screen.dart';
import 'package:student_attendance_app/models/models.dart';

const _assignedAndUnassigned = {
  'assignments': [
    {'section_id': 1, 'subject_id': 1},
    {'section_id': 1, 'subject_id': 2},
  ],
  'is_admin': false,
  'sections': [
    {'class_id': 1, 'id': 1, 'name': 'Year 1 — A'},
    {'class_id': 3, 'id': 3, 'name': '3 — 5th sem'},
  ],
  'subjects': [
    {'code': 'MATH101', 'id': 1, 'name': 'Mathematics'},
    {'code': 'INTERNET O', 'id': 5, 'name': 'Internet of things'},
  ],
};

Future<void> pumpScreen(WidgetTester tester, Map<String, dynamic> payload,
    {int? sectionId}) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [
      staffOptionsProvider
          .overrideWith((_) async => StaffOptions.fromJson(payload)),
    ],
    child: MaterialApp(
        home: StartSessionScreen(sectionId: sectionId)),
  ));
  await tester.pumpAndSettle();
}

/// Opens the dropdown at [index] and taps its first menu entry.
Future<void> pickFirst(WidgetTester tester, int index, String label) async {
  await tester.tap(find.byType(DropdownButtonFormField<int>).at(index));
  await tester.pumpAndSettle();
  // The open menu is the last match; the button row repeats the value.
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('class dropdown only lists assigned sections', (tester) async {
    await pumpScreen(tester, _assignedAndUnassigned);

    await tester.tap(find.byType(DropdownButtonFormField<int>).first);
    await tester.pumpAndSettle();

    expect(find.text('Year 1 — A'), findsWidgets);
    expect(find.text('3 — 5th sem'), findsNothing,
        reason: 'an unassigned class can only fail with a 403');
  });

  testWidgets('subject dropdown follows the chosen class', (tester) async {
    await pumpScreen(tester, _assignedAndUnassigned);
    await pickFirst(tester, 0, 'Year 1 — A');

    await tester.tap(find.byType(DropdownButtonFormField<int>).last);
    await tester.pumpAndSettle();

    expect(find.text('Mathematics'), findsWidgets);
    expect(find.text('Internet of things'), findsNothing,
        reason: 'the new subject is not assigned to this class yet');
  });

  testWidgets('unassigned class is dropped from a pre-set selection',
      (tester) async {
    await pumpScreen(tester, _assignedAndUnassigned, sectionId: 3);

    expect(find.text('3 — 5th sem'), findsNothing,
        reason: 'a stale deep link must not keep an unassignable class');
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
  });

  testWidgets('teacher with no assignments gets an explanation, not a crash',
      (tester) async {
    await pumpScreen(tester, {
      ..._assignedAndUnassigned,
      'assignments': <Map<String, int>>[],
    });

    expect(find.textContaining('No class or subject is assigned to you yet'),
        findsOneWidget);
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull, reason: 'nothing can be started yet');
  });
}
