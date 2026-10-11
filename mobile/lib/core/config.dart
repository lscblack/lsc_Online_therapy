/// Backend base URL. Override with `--dart-define=API_BASE=https://...`.
const String apiBase =
    String.fromEnvironment('API_BASE', defaultValue: 'http://127.0.0.1:8099');
