// The live session screen must show WHO is present, not just counts.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_attendance_app/core/api_client.dart';
import 'package:student_attendance_app/core/token_storage.dart';
import 'package:student_attendance_app/features/teacher/live_session_screen.dart';
import 'package:student_attendance_app/models/models.dart';
import 'package:student_attendance_app/services/teacher_service.dart';

class _FakeTeacherService extends TeacherService {
  _FakeTeacherService(this._session) : super(ApiClient(TokenStorage()));

  final TeacherSession _session;

  @override
  Future<TeacherSession> session(int id) async => _session;
}

TeacherSession _sessionWithRoster() => TeacherSession(
      id: 1,
      subject: 'Mathematics',
      section: 'A',
      klass: 'Year 1',
      status: 'OPEN',
      presentCount: 1,
      lateCount: 0,
      code: '123456',
      codeSecondsLeft: 40,
      codeValid: true,
      checkinCutoff: DateTime.parse('2026-10-14T09:20:00+00:00'),
      roster: const [
        RosterEntry(
          studentId: 1,
          rollNo: 'D001',
          fullName: 'Ada Lovelace',
          status: 'PRESENT',
          recordedAt: null,
          isCorrected: false,
        ),
        RosterEntry(
          studentId: 2,
          rollNo: 'D002',
          fullName: 'Alan Turing',
          status: 'NOT_MARKED',
          recordedAt: null,
          isCorrected: false,
        ),
      ],
    );

void main() {
  test('TeacherSession keeps the roster and defaults to empty', () {
    final withRoster = TeacherSession.fromJson({
      'id': 1,
      'subject': 'Mathematics',
      'section': 'A',
      'klass': 'Year 1',
      'status': 'OPEN',
      'present_count': 1,
      'late_count': 0,
      'code_seconds_left': 30,
      'code_valid': true,
      'checkin_cutoff': '2026-10-14T09:20:00+00:00',
      'roster': [
        {
          'student_id': 7,
          'roll_no': 'D007',
          'full_name': 'Grace Hopper',
          'status': 'LATE',
          'recorded_at': '2026-10-14T09:05:00+00:00',
          'is_corrected': true,
        },
        {
          'student_id': 8,
          'roll_no': 'D008',
          'full_name': 'Edsger Dijkstra',
          'status': 'NOT_MARKED',
          'recorded_at': null,
          'is_corrected': false,
        },
      ],
    });
    expect(withRoster.roster, hasLength(2));
    expect(withRoster.roster.first.marked, isTrue);
    expect(withRoster.roster.first.recordedAt, isNotNull);
    expect(withRoster.roster.last.marked, isFalse);
    expect(withRoster.roster.last.recordedAt, isNull);

    // history/close payloads carry no roster — the field must not break them
    final bare = TeacherSession.fromJson({
      'id': 2,
      'subject': 'Physics',
      'section': 'B',
      'klass': 'Year 2',
      'status': 'CLOSED',
      'present_count': 0,
      'late_count': 0,
      'code_seconds_left': 0,
      'code_valid': false,
      'checkin_cutoff': '2026-10-14T09:20:00+00:00',
    });
    expect(bare.roster, isEmpty);
  });

  testWidgets('live session lists every student with their status',
      (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        teacherServiceProvider
            .overrideWithValue(_FakeTeacherService(_sessionWithRoster())),
      ],
      child: const MaterialApp(home: LiveSessionScreen(sessionId: 1)),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Roll call'), findsOneWidget);
    expect(find.textContaining('1 of 2 checked in'), findsOneWidget);
    expect(find.text('D001'), findsOneWidget);
    expect(find.text('Ada Lovelace'), findsOneWidget);
    expect(find.text('D002'), findsOneWidget);
    expect(find.text('Alan Turing'), findsOneWidget);
    expect(find.text('Not marked'), findsOneWidget);

    // the status belongs to the student's own row, not just the tallies
    final adaRow =
        find.ancestor(of: find.text('Ada Lovelace'), matching: find.byType(ListTile));
    expect(
        find.descendant(of: adaRow, matching: find.text('Present')),
        findsOneWidget);
    final alanRow =
        find.ancestor(of: find.text('Alan Turing'), matching: find.byType(ListTile));
    expect(
        find.descendant(of: alanRow, matching: find.text('Not marked')),
        findsOneWidget);
    expect(find.text('1'), findsWidgets); // present count still shown

    // Unmount so the 3-second poll timer is cancelled before the test ends.
    await tester.pumpWidget(const SizedBox());
    await tester.pumpAndSettle();
  });
}
