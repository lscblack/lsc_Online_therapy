import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'prefs.dart';

// Warm "buddy" palette. Solid colours only: no gradients anywhere.
const _lightScheme = ColorScheme(
  brightness: Brightness.light,
  primary: Color(0xFFB3412F), // warm coral-brick, 5.9:1 on white-ish
  onPrimary: Color(0xFFFFFFFF),
  primaryContainer: Color(0xFFFFDAD2),
  onPrimaryContainer: Color(0xFF410D05),
  secondary: Color(0xFF0B6B69), // teal
  onSecondary: Color(0xFFFFFFFF),
  secondaryContainer: Color(0xFFBDEEEA),
  onSecondaryContainer: Color(0xFF00201F),
  tertiary: Color(0xFF7A5A00),
  onTertiary: Color(0xFFFFFFFF),
  error: Color(0xFFB3261E),
  onError: Color(0xFFFFFFFF),
  surface: Color(0xFFFFF8F4),
  onSurface: Color(0xFF2A1F1B),
  surfaceContainerHighest: Color(0xFFF1E4DE),
  onSurfaceVariant: Color(0xFF55443E),
  outline: Color(0xFF85736C),
  outlineVariant: Color(0xFFD8C2BA),
);

const _darkScheme = ColorScheme(
  brightness: Brightness.dark,
  primary: Color(0xFFFFB4A5),
  onPrimary: Color(0xFF5F1507),
  primaryContainer: Color(0xFF8A2D1D),
  onPrimaryContainer: Color(0xFFFFDAD2),
  secondary: Color(0xFF7FD6D1),
  onSecondary: Color(0xFF00201F),
  secondaryContainer: Color(0xFF00504E),
  onSecondaryContainer: Color(0xFFBDEEEA),
  tertiary: Color(0xFFEFC04C),
  onTertiary: Color(0xFF3F2E00),
  error: Color(0xFFFFB4AB),
  onError: Color(0xFF690005),
  surface: Color(0xFF1F1613),
  onSurface: Color(0xFFF2DFD9),
  surfaceContainerHighest: Color(0xFF3A2D28),
  onSurfaceVariant: Color(0xFFD8C2BA),
  outline: Color(0xFFA08C85),
  outlineVariant: Color(0xFF55443E),
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
