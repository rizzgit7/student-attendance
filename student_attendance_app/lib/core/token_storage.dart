// Secure token storage (§16: secure token storage in Flutter).
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _kAccess = 'access_token';
  static const _kRefresh = 'refresh_token';
  static const _kUserJson = 'user_json';

  Future<void> saveSession({
    required String accessToken,
    required String refreshToken,
    String? userJson,
  }) async {
    await _storage.write(key: _kAccess, value: accessToken);
    await _storage.write(key: _kRefresh, value: refreshToken);
    if (userJson != null) {
      await _storage.write(key: _kUserJson, value: userJson);
    }
  }

  Future<String?> accessToken() => _storage.read(key: _kAccess);
  Future<String?> refreshToken() => _storage.read(key: _kRefresh);
  Future<String?> userJson() => _storage.read(key: _kUserJson);

  Future<void> clear() => _storage.deleteAll();
}
