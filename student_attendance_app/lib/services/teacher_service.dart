// Teacher-facing API calls (§9/§13).
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../models/models.dart';

final teacherServiceProvider = Provider<TeacherService>((ref) =>
    TeacherService(ref.watch(apiClientProvider)));

class TeacherService {
  TeacherService(this._client);
  final ApiClient _client;

  /// Pick-lists plus this staff member's assignments: the UI must only offer
  /// subject/section pairs the API will accept (anything else is a 403).
  Future<StaffOptions> options() =>
      guardApi(() async {
        final resp = await _client.dio.get('/teacher/options');
        return StaffOptions.fromJson(resp.data as Map<String, dynamic>);
      });

  /// POST /teacher/sessions — returns the session incl. the 6-digit code.
  Future<TeacherSession> startSession({
    required int sectionId,
    required int subjectId,
    DateTime? scheduledStart,
  }) =>
      guardApi(() async {
        final resp = await _client.dio.post('/teacher/sessions', data: {
          'section_id': sectionId,
          'subject_id': subjectId,
          if (scheduledStart != null)
            'scheduled_start_at': scheduledStart.toUtc().toIso8601String(),
        });
        return TeacherSession.fromJson(resp.data as Map<String, dynamic>);
      });

  Future<TeacherSession> session(int id) =>
      guardApi(() async {
        final resp = await _client.dio.get('/teacher/sessions/$id');
        return TeacherSession.fromJson(resp.data as Map<String, dynamic>);
      });

  Future<List<TeacherSession>> history() =>
      guardApi(() async {
        final resp = await _client.dio.get('/teacher/sessions');
        return (resp.data['sessions'] as List)
            .map((e) => TeacherSession.fromJson(e as Map<String, dynamic>))
            .toList();
      });

  Future<TeacherSession> close(int id) =>
      guardApi(() async {
        final resp = await _client.dio.post('/teacher/sessions/$id/close',
            data: <String, dynamic>{});
        return TeacherSession.fromJson(resp.data as Map<String, dynamic>);
      });

  /// Codes rotate every ~30–60 s (§10); teacher can force a fresh one.
  Future<TeacherSession> rotateCode(int id) =>
      guardApi(() async {
        final resp = await _client.dio.post('/teacher/sessions/$id/rotate-code',
            data: <String, dynamic>{});
        return TeacherSession.fromJson(resp.data as Map<String, dynamic>);
      });
}
