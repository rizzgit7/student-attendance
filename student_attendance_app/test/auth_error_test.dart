import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_attendance_app/core/api_client.dart';
import 'package:student_attendance_app/core/errors.dart';
import 'package:student_attendance_app/core/token_storage.dart';
import 'package:student_attendance_app/services/auth_service.dart';

/// In-memory token store: the real one needs platform channels, which do not
/// exist in the test sandbox (and would mask the code under test).
class _FakeTokenStorage extends TokenStorage {
  String? access;
  String? refresh;

  @override
  Future<String?> accessToken() async => access;

  @override
  Future<String?> refreshToken() async => refresh;

  @override
  Future<String?> userJson() async => null;

  @override
  Future<void> saveSession({
    required String accessToken,
    required String refreshToken,
    String? userJson,
  }) async {
    access = accessToken;
    refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    access = null;
    refresh = null;
  }
}

/// Returns exactly what the live API answers for bad credentials.
class _Fake401Adapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(RequestOptions options,
      [Stream<List<int>>? requestStream, Future<void>? cancelFuture]) async {
    return ResponseBody.fromString(
      jsonEncode({
        'error': 'invalid_credentials',
        'message': 'Invalid email or password',
      }),
      401,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('failed login shows the API message, not a DioException dump', () async {
    final storage = _FakeTokenStorage();
    final client = ApiClient(storage);
    client.dio.httpClientAdapter = _Fake401Adapter();

    final controller = AuthController(client, storage);

    Object? thrown;
    try {
      await controller.login('rizwancr7869@gmail.com', 'wrong');
    } catch (e) {
      thrown = e;
    }

    expect(thrown, isA<AppException>(),
        reason: 'login must convert Dio errors to AppException');
    final app = thrown as AppException;
    expect(app.statusCode, 401, reason: 'the 401 response must survive');
    expect(app.code, 'invalid_credentials');
    expect(app.message, 'Invalid email or password');

    // The login screen prints e.toString() verbatim.
    expect(app.toString(), 'Invalid email or password');
    expect(app.toString(), isNot(contains('DioException')));

    client.close();
  });

  test('a broken token store still surfaces the API message', () async {
    // Simulates secure storage failing on a real device: the interceptor
    // must not swallow the original 401.
    final storage = _ThrowingTokenStorage();
    final client = ApiClient(storage);
    client.dio.httpClientAdapter = _Fake401Adapter();

    final controller = AuthController(client, storage);

    Object? thrown;
    try {
      await controller.login('someone@example.com', 'wrong');
    } catch (e) {
      thrown = e;
    }

    expect(thrown, isA<AppException>());
    final broken = thrown as AppException;
    expect(broken.message, 'Invalid email or password');
    expect(broken.statusCode, 401);

    client.close();
  });
}

/// Token storage whose platform channel always fails.
class _ThrowingTokenStorage extends TokenStorage {
  Never _boom() =>
      throw Exception('FlutterSecureStorage platform channel unavailable');

  @override
  Future<String?> accessToken() async => _boom();

  @override
  Future<String?> refreshToken() async => _boom();

  @override
  Future<String?> userJson() async => _boom();

  @override
  Future<void> saveSession({
    required String accessToken,
    required String refreshToken,
    String? userJson,
  }) async =>
      _boom();

  @override
  Future<void> clear() async => _boom();
}
