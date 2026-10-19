import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'prefs.dart';

// Unified emerald/teal 2026 palette — shared language with the web app
// (see docs/redesign-2026.md). Solid colours only: no gradients anywhere.
// bg -> surface (page), surface(#fff) -> surfaceContainerHighest (cards/bubbles).
const _lightScheme = ColorScheme(
  brightness: Brightness.light,
  primary: Color(0xFF15A06A), // emerald green
  onPrimary: Color(0xFFFFFFFF),
  primaryContainer: Color(0xFFC6EFDA),
  onPrimaryContainer: Color(0xFF053E27),
  secondary: Color(0xFF2BB6A3), // teal-green accent
  onSecondary: Color(0xFFFFFFFF),
  secondaryContainer: Color(0xFFBFECE7),
  onSecondaryContainer: Color(0xFF00201E),
  tertiary: Color(0xFF0C7A4E), // primary-strong (deep emerald)
  onTertiary: Color(0xFFFFFFFF),
  error: Color(0xFFC0392B),
  onError: Color(0xFFFFFFFF),
  surface: Color(0xFFEEF8F2), // page background (bg)
  onSurface: Color(0xFF10271D), // text
  surfaceContainerHighest: Color(0xFFFFFFFF), // cards / bubbles (surface)
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
  tertiary: Color(0xFF63DCB0), // primary-strong on dark
  onTertiary: Color(0xFF07371F),
  error: Color(0xFFFF6B5E),
  onError: Color(0xFF5B0D07),
  surface: Color(0xFF0A1712), // page background (bg)
  onSurface: Color(0xFFE6F2EC), // text
  surfaceContainerHighest: Color(0xFF0F201A), // cards / bubbles (surface)
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
      surfaceTintColor: Colors.transparent,
      shadowColor: scheme.shadow.withValues(alpha: 0.12),
      elevation: 1,
      margin: EdgeInsets.zero,
      shape: const RoundedRectangleBorder(borderRadius: radius),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 48),
        // Pill buttons, ≥44px tap target (shared component rule).
        shape: const StadiumBorder(),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 48),
        shape: const StadiumBorder(),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(shape: const StadiumBorder()),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: scheme.surfaceContainerHighest,
      // Rounded pill-ish field, no hard border.
      border: const OutlineInputBorder(
        borderRadius: BorderRadius.all(Radius.circular(28)),
        borderSide: BorderSide.none,
      ),
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
