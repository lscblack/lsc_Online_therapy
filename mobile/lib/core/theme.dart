import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'prefs.dart';

// Warm emerald/forest green palette (not a clinical "hospital" green).
// Solid colours only: no gradients anywhere.
const _lightScheme = ColorScheme(
  brightness: Brightness.light,
  primary: Color(0xFF117A53), // emerald/forest green
  onPrimary: Color(0xFFFFFFFF),
  primaryContainer: Color(0xFFCDEBDC),
  onPrimaryContainer: Color(0xFF00210F),
  secondary: Color(0xFF0F8F88), // teal-green accent
  onSecondary: Color(0xFFFFFFFF),
  secondaryContainer: Color(0xFFBFECE7),
  onSecondaryContainer: Color(0xFF00201E),
  tertiary: Color(0xFF3B6A4A),
  onTertiary: Color(0xFFFFFFFF),
  error: Color(0xFFC0392B),
  onError: Color(0xFFFFFFFF),
  surface: Color(0xFFF4FAF6),
  onSurface: Color(0xFF10231A),
  surfaceContainerHighest: Color(0xFFE2F0E8),
  onSurfaceVariant: Color(0xFF42564C),
  outline: Color(0xFF6F8378),
  outlineVariant: Color(0xFFC5DBCF),
);

const _darkScheme = ColorScheme(
  brightness: Brightness.dark,
  primary: Color(0xFF45CF9F), // bright mint on dark
  onPrimary: Color(0xFF00351F),
  primaryContainer: Color(0xFF0C5F41),
  onPrimaryContainer: Color(0xFFBFECD6),
  secondary: Color(0xFF35C7BD), // teal-green on dark
  onSecondary: Color(0xFF00201E),
  secondaryContainer: Color(0xFF00504B),
  onSecondaryContainer: Color(0xFFBFECE7),
  tertiary: Color(0xFF9FD6B0),
  onTertiary: Color(0xFF07371F),
  error: Color(0xFFFFB4AB),
  onError: Color(0xFF690005),
  surface: Color(0xFF0A1712),
  onSurface: Color(0xFFE6F2EC),
  surfaceContainerHighest: Color(0xFF1C352B),
  onSurfaceVariant: Color(0xFFBFD3C8),
  outline: Color(0xFF899B90),
  outlineVariant: Color(0xFF42564C),
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
