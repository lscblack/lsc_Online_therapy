import 'package:flutter/cupertino.dart' show CupertinoLocalizations;
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/i18n/i18n.dart';
import 'core/theme.dart';
import 'features/onboarding/onboarding_page.dart';
import 'features/shell/shell.dart';
import 'state/profile.dart';

class UbuzimaApp extends ConsumerWidget {
  const UbuzimaApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'Ubuzima',
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: ref.watch(themeModeProvider),
      locale: Locale(ref.watch(languageProvider)),
      supportedLocales: [for (final l in supportedLangs) Locale(l)],
      localizationsDelegates: const [
        _FallbackMaterialDelegate(),
        _FallbackWidgetsDelegate(),
        _FallbackCupertinoDelegate(),
      ],
      home: ref.watch(onboardedProvider)
          ? const AppShell()
          : const OnboardingPage(),
    );
  }
}

// Material has no 'rw' translations of its own widget strings, so framework
// widgets fall back to English there while app strings come from kStrings.
Locale _frameworkLocale(Locale l) =>
    GlobalMaterialLocalizations.delegate.isSupported(l)
    ? l
    : const Locale('en');

class _FallbackMaterialDelegate
    extends LocalizationsDelegate<MaterialLocalizations> {
  const _FallbackMaterialDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<MaterialLocalizations> load(Locale locale) =>
      GlobalMaterialLocalizations.delegate.load(_frameworkLocale(locale));
  @override
  bool shouldReload(
    covariant LocalizationsDelegate<MaterialLocalizations> old,
  ) => false;
}

class _FallbackWidgetsDelegate
    extends LocalizationsDelegate<WidgetsLocalizations> {
  const _FallbackWidgetsDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<WidgetsLocalizations> load(Locale locale) =>
      GlobalWidgetsLocalizations.delegate.load(_frameworkLocale(locale));
  @override
  bool shouldReload(
    covariant LocalizationsDelegate<WidgetsLocalizations> old,
  ) => false;
}

class _FallbackCupertinoDelegate
    extends LocalizationsDelegate<CupertinoLocalizations> {
  const _FallbackCupertinoDelegate();
  @override
  bool isSupported(Locale locale) => true;
  @override
  Future<CupertinoLocalizations> load(Locale locale) =>
      GlobalCupertinoLocalizations.delegate.load(_frameworkLocale(locale));
  @override
  bool shouldReload(
    covariant LocalizationsDelegate<CupertinoLocalizations> old,
  ) => false;
}
