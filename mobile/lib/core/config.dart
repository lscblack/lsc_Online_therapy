import 'package:flutter/foundation.dart';

/// Backend base URL.
///
/// The backend listens on 0.0.0.0:8099 (all interfaces), so it is reachable over the network.
/// A client, though, must target a concrete address, which differs by platform:
///   - Android emulator reaches the host machine at 10.0.2.2 (not 127.0.0.1).
///   - Web, desktop and the iOS simulator reach it at 127.0.0.1.
///   - A physical phone must use the host's LAN IP — pass it explicitly:
///       `flutter run --dart-define=API_BASE=http://YOUR-LAN-IP:8099`
/// An explicit --dart-define=API_BASE=... always wins.
String _resolveApiBase() {
  const override = String.fromEnvironment('API_BASE');
  if (override.isNotEmpty) return override;
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
    return 'http://10.0.2.2:8099';
  }
  return 'http://127.0.0.1:8099';
}

final String apiBase = _resolveApiBase();
