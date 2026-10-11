import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'prefs.dart';

// Blue/green palette. Solid colours only: no gradients anywhere.
const _lightScheme = ColorScheme(
  brightness: Brightness.light,
  primary: Color(0xFF1565C0), // blue
  onPrimary: Color(0xFFFFFFFF),
  primaryContainer: Color(0xFFD4E3FF),
  onPrimaryContainer: Color(0xFF001B3D),
  secondary: Color(0xFF0E8A5F), // green
  onSecondary: Color(0xFFFFFFFF),
  secondaryContainer: Color(0xFFBEEBD2),
  onSecondaryContainer: Color(0xFF00210F),
  tertiary: Color(0xFF00658E),
  onTertiary: Color(0xFFFFFFFF),
  error: Color(0xFFC0392B),
  onError: Color(0xFFFFFFFF),
  surface: Color(0xFFF7FAFD),
  onSurface: Color(0xFF0F1F2E),
  surfaceContainerHighest: Color(0xFFE2ECF5),
  onSurfaceVariant: Color(0xFF42525F),
  outline: Color(0xFF72808C),
  outlineVariant: Color(0xFFC2CDD8),
);

const _darkScheme = ColorScheme(
  brightness: Brightness.dark,
  primary: Color(0xFF9ECAFF), // light blue on dark
  onPrimary: Color(0xFF00315B),
  primaryContainer: Color(0xFF1A4A80),
  onPrimaryContainer: Color(0xFFD4E3FF),
  secondary: Color(0xFF8FD5B4), // green on dark
  onSecondary: Color(0xFF00391E),
  secondaryContainer: Color(0xFF0A6B45),
  onSecondaryContainer: Color(0xFFBEEBD2),
  tertiary: Color(0xFF86CFFF),
  onTertiary: Color(0xFF00344E),
  error: Color(0xFFFFB4AB),
  onError: Color(0xFF690005),
  surface: Color(0xFF0B1620),
  onSurface: Color(0xFFE9F2F9),
  surfaceContainerHighest: Color(0xFF1F3242),
  onSurfaceVariant: Color(0xFFC2CDD8),
  outline: Color(0xFF8A99A6),
  outlineVariant: Color(0xFF42525F),
);

ThemeData buildTheme(Brightness b) {
  final scheme = b == Brightness.light ? _lightScheme : _darkScheme;
  final base = ThemeData(useMaterial3: true, colorScheme: scheme, brightness: b);
  final text = base.textTheme.apply(
    bodyColor: scheme.onSurface,
    displayColor: scheme.onSurface,
  );
  const radius = BorderRadius.all(Radius.circular(20));
  return base.copyWith(
    scaffoldBackgroundColor: scheme.surface,
    textTheme: text.copyWith(
      titleLarge: text.titleLarge?.copyWith(fontWeight: FontWeight.w700),
      bodyLarge: text.bodyLarge?.copyWith(height: 1.45),
      bodyMedium: text.bodyMedium?.copyWith(height: 1.45),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      foregroundColor: scheme.onSurface,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    cardTheme: CardThemeData(
      color: scheme.surfaceContainerHighest,
      elevation: 0,
      shape: const RoundedRectangleBorder(borderRadius: radius),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 48),
        shape: const RoundedRectangleBorder(borderRadius: radius),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: scheme.surfaceContainerHighest,
      border: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide.none),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: scheme.surfaceContainerHighest,
      indicatorColor: scheme.primaryContainer,
      indicatorShape: const StadiumBorder(),
    ),
  );
}

final ThemeData lightTheme = buildTheme(Brightness.light);
final ThemeData darkTheme = buildTheme(Brightness.dark);

class ThemeModeController extends StateNotifier<ThemeMode> {
  ThemeModeController(this._ref) : super(_initial(_ref));
  final Ref _ref;

  static ThemeMode _initial(Ref ref) {
    final s = readPref(ref.read(prefsProvider), 'theme_mode');
    return ThemeMode.values.firstWhere((m) => m.name == s, orElse: () => ThemeMode.system);
  }

  Future<void> set(ThemeMode mode) async {
    state = mode;
    await writePref(_ref.read(prefsProvider), 'theme_mode', mode.name);
  }
}

/// ThemeMode: system by default, user override persisted.
final themeModeProvider =
    StateNotifierProvider<ThemeModeController, ThemeMode>((ref) => ThemeModeController(ref));
