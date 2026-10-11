import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// SharedPreferences instance (null if unavailable). Overridden in main().
final prefsProvider = Provider<SharedPreferences?>((ref) => null);

Future<SharedPreferences?> loadPrefs() async {
  try {
    return await SharedPreferences.getInstance();
  } catch (_) {
    return null;
  }
}

String? readPref(SharedPreferences? p, String key) {
  try {
    return p?.getString(key);
  } catch (_) {
    return null;
  }
}

Future<void> writePref(SharedPreferences? p, String key, String value) async {
  try {
    await p?.setString(key, value);
  } catch (_) {}
}
