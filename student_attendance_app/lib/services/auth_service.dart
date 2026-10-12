// Authentication service + Riverpod state (§8 screens: login, logout).
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/token_storage.dart';
import '../models/models.dart';

final authProvider =
    StateNotifierProvider<AuthController, AsyncValue<UserSession?>>((ref) {
  return AuthController(ref.watch(apiClientProvider),
      ref.watch(tokenStorageProvider));
});

class AuthController extends StateNotifier<AsyncValue<UserSession?>> {
  AuthController(this._client, this._storage)
      : super(const AsyncValue.loading()) {
    _restore();
  }

  final ApiClient _client;
  final TokenStorage _storage;

  Future<void> _restore() async {
    try {
      final token = await _storage.accessToken();
      final raw = await _storage.userJson();
      if (token != null && raw != null) {
        state = AsyncValue.data(
            UserSession.fromJson(jsonDecode(raw) as Map<String, dynamic>));
        return;
      }
    } catch (_) {
      // Unreadable storage must not strand the app on a loading spinner:
      // fall through and start signed out.
    }
    state = const AsyncValue.data(null);
  }

  Future<void> login(String email, String password) async {
    state = const AsyncValue.loading();
    try {
      final resp = await _client.dio.post('/auth/login', data: {
        'email': email.trim().toLowerCase(),
        'password': password,
      });
      final result = LoginResult.fromJson(resp.data as Map<String, dynamic>);
      await _storage.saveSession(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        userJson: jsonEncode({
          'id': result.user.id,
          'email': result.user.email,
          'full_name': result.user.fullName,
          'role': result.user.role,
          'institution_id': result.user.institutionId,
          'teacher_id': result.user.teacherId,
        }),
      );
      state = AsyncValue.data(result.user);
    } catch (e) {
      state = const AsyncValue.data(null);
      // Surface the API's message ("Invalid email or password") instead of
      // leaking a raw DioException dump into the UI.
      throw ApiClient.toAppException(e);
    }
  }

  Future<void> logout() async {
    try {
      await _client.dio.post('/auth/logout', data: {});
    } catch (_) {
      // logout is best-effort; local session is cleared regardless
    }
    await _storage.clear();
    state = const AsyncValue.data(null);
  }
}
