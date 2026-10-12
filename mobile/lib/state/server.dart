import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/config.dart';
import '../core/prefs.dart';

const serverUrlKey = 'server_url';

/// The backend base URL the app talks to. Defaults to the compile-time [apiBase], but can be
/// overridden on the device (persisted) — handy for a physical phone that must reach the host's
/// LAN IP without rebuilding. Empty resets to the default.
class ServerUrlController extends StateNotifier<String> {
  ServerUrlController(this._ref) : super(_initial(_ref));
  final Ref _ref;

  static String _initial(Ref ref) {
    final s = readPref(ref.read(prefsProvider), serverUrlKey);
    return (s != null && s.trim().isNotEmpty) ? s.trim() : apiBase;
  }

  Future<void> set(String url) async {
    final v = url.trim();
    state = v.isEmpty ? apiBase : v;
    await writePref(_ref.read(prefsProvider), serverUrlKey, state);
  }
}

final serverUrlProvider =
    StateNotifierProvider<ServerUrlController, String>((ref) => ServerUrlController(ref));
