// Runtime configuration.
///
/// Build with:
///   flutter run --dart-define=BASE_URL=https://your-api.example.com
class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'BASE_URL',
    defaultValue: 'http://10.0.2.2:5000', // Android emulator → host machine
  );
}
