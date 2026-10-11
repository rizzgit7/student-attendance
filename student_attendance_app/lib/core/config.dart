// Runtime configuration.
///
/// Build with:
///   flutter run --dart-define=BASE_URL=https://your-api.example.com
class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'BASE_URL',
    // Production API (Vercel). For local dev, override at build time:
    //   flutter run --dart-define=BASE_URL=http://10.0.2.2:5000
    defaultValue: 'https://student-attendance.vercel.app',
  );
}
