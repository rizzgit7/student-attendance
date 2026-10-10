// Typed API failures surfaced to the UI.
class AppException implements Exception {
  AppException(this.code, this.message, {this.statusCode});

  final String code; // machine-readable: invalid_code, rate_limit_exceeded…
  final String message; // human-readable
  final int? statusCode;

  @override
  String toString() => message;
}
