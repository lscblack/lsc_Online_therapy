import 'dart:ui' as ui;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../prefs.dart';
import 'strings.dart';

export '../prefs.dart';

const supportedLangs = ['en', 'rw'];

/// Look up [key] in [lang]; falls back to en, then the key itself.
String translate(String lang, String key) =>
    kStrings[lang]?[key] ?? kStrings['en']![key] ?? key;

/// Callable translator bound to a language: `t('nav.chat')`.
class T {
  const T(this.lang);
  final String lang;
  String call(String key) => translate(lang, key);
}

String _deviceLang() {
  final code = ui.PlatformDispatcher.instance.locale.languageCode;
  return supportedLangs.contains(code) ? code : 'en';
}

class LanguageController extends StateNotifier<String> {
  LanguageController(this._ref) : super(_initial(_ref));
  final Ref _ref;

  static String _initial(Ref ref) {
    final saved = readPref(ref.read(prefsProvider), 'lang');
    return supportedLangs.contains(saved) ? saved! : _deviceLang();
  }

  Future<void> set(String lang) async {
    if (!supportedLangs.contains(lang)) return;
    state = lang;
    await writePref(_ref.read(prefsProvider), 'lang', lang);
  }
}

/// Current language code: 'en' | 'rw'.
final languageProvider =
    StateNotifierProvider<LanguageController, String>((ref) => LanguageController(ref));

/// Watch for a translator: `final t = ref.watch(tProvider); t('nav.chat')`.
final tProvider = Provider<T>((ref) => T(ref.watch(languageProvider)));
