// Student-facing API calls (§8/§13).
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../models/models.dart';

final attendanceServiceProvider = Provider<AttendanceService>((ref) =>
    AttendanceService(ref.watch(apiClientProvider)));

class AttendanceService {
  AttendanceService(this._client);
  final ApiClient _client;

  /// POST /attendance/check-in (§10 algorithm runs server-side).
  Future<AttendanceRecord> checkIn(String code, {int? sessionId}) async {
    final resp = await _client.dio.post('/attendance/check-in', data: {
      'code': code,
      if (sessionId != null) 'session_id': sessionId,
    });
    final record = resp.data['record'] as Map<String, dynamic>;
    return AttendanceRecord.fromJson(record);
  }

  Future<Dashboard> dashboard() async {
    final resp = await _client.dio.get('/student/dashboard');
    return Dashboard.fromJson(resp.data as Map<String, dynamic>);
  }

  Future<List<AttendanceRecord>> history({int page = 1}) async {
    final resp = await _client.dio
        .get('/attendance/history', queryParameters: {'page': page});
    return (resp.data['records'] as List)
        .map((e) => AttendanceRecord.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<AttendanceRecord>> today() async {
    final resp = await _client.dio.get('/attendance/today');
    return (resp.data['records'] as List)
        .map((e) => AttendanceRecord.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Subject-wise attendance + overall percentage (§8).
  Future<List<SubjectSummary>> summary() async {
    final resp = await _client.dio.get('/attendance/summary');
    return (resp.data['subjects'] as List)
        .map((e) => SubjectSummary.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /leave/requests (§13).
  Future<void> requestLeave({
    required String fromDate,
    required String toDate,
    required String reason,
  }) async {
    await _client.dio.post('/leave/requests', data: {
      'from_date': fromDate,
      'to_date': toDate,
      'reason': reason,
    });
  }

  Future<List<LeaveRequest>> myLeaves() async {
    final resp = await _client.dio.get('/leave/requests');
    return (resp.data['requests'] as List)
        .map((e) => LeaveRequest.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
