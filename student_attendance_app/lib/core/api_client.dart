// Dio client with automatic bearer tokens and refresh-on-401 (§16).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config.dart';
import 'errors.dart';
import 'token_storage.dart';

final tokenStorageProvider = Provider<TokenStorage>((_) => TokenStorage());

/// Run [body] and rethrow failures as [AppException] carrying the API's own
/// message, so screens show "You are not assigned to teach this subject here"
/// instead of a raw DioException dump.
Future<T> guardApi<T>(Future<T> Function() body) async {
  try {
    return await body();
  } on DioException catch (e) {
    throw ApiClient.toAppException(e);
  }
}

final apiClientProvider = Provider<ApiClient>((ref) {
  final client = ApiClient(ref.watch(tokenStorageProvider));
  ref.onDispose(client.close);
  return client;
});

class ApiClient {
  ApiClient(this._storage) {
    dio = Dio(BaseOptions(
      baseUrl: AppConfig.baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ));
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: _onRequest,
        onError: _onError,
      ),
    );
  }

  final TokenStorage _storage;
  late final Dio dio;
  bool _refreshing = false;

  Future<void> _onRequest(
      RequestOptions options, RequestInterceptorHandler handler) async {
    try {
      final token = await _storage.accessToken();
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    } catch (_) {
      // Never let an unreadable token store block the request itself —
      // login must still reach the server when secure storage is broken.
    }
    handler.next(options);
  }

  Future<void> _onError(
      DioException error, ErrorInterceptorHandler handler) async {
    if (error.response?.statusCode == 401 && !_refreshing) {
      bool refreshed = false;
      try {
        refreshed = await _tryRefresh();
      } catch (_) {
        // A refresh failure must never swallow the original response:
        // forward the 401 so the UI can show the server's message.
        refreshed = false;
      }
      if (refreshed) {
        // replay the original request once with the fresh token
        final opts = error.requestOptions;
        opts.headers['Authorization'] =
            'Bearer ${await _storage.accessToken()}';
        try {
          final resp = await dio.fetch<dynamic>(opts);
          handler.resolve(resp);
          return;
        } on DioException catch (e) {
          handler.next(e);
          return;
        }
      }
    }
    handler.next(error);
  }

  Future<bool> _tryRefresh() async {
    _refreshing = true;
    try {
      final refresh = await _storage.refreshToken();
      if (refresh == null) {
        return false;
      }
      final bare = Dio(BaseOptions(baseUrl: AppConfig.baseUrl));
      final resp = await bare.post('/auth/refresh', data: {
        'refresh_token': refresh,
      });
      final data = resp.data as Map<String, dynamic>;
      await _storage.saveSession(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String,
      );
      return true;
    } catch (_) {
      try {
        await _storage.clear();
      } catch (_) {
        // Clearing a broken store must not mask the login failure.
      }
      return false;
    } finally {
      _refreshing = false;
    }
  }

  /// Translate Dio errors into [AppException] with the API's error code.
  static AppException toAppException(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map<String, dynamic>) {
        return AppException(
          (data['error'] ?? 'unknown').toString(),
          (data['message'] ?? 'Request failed').toString(),
          statusCode: error.response?.statusCode,
        );
      }
      return AppException(
        'network',
        'Network error — check your connection.',
        statusCode: error.response?.statusCode,
      );
    }
    return AppException('unknown', error.toString());
  }

  void close() => dio.close(force: true);
}
