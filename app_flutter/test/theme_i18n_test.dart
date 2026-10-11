import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ubuzima/app.dart';
import 'package:ubuzima/core/config.dart';
import 'package:ubuzima/core/i18n/i18n.dart';
import 'package:ubuzima/core/theme.dart';

Future<ProviderContainer> makeContainer([Map<String, Object> initial = const {}]) async {
  SharedPreferences.setMockInitialValues(initial);
  final prefs = await SharedPreferences.getInstance();
  final c = ProviderContainer(overrides: [prefsProvider.overrideWithValue(prefs)]);
  addTearDown(c.dispose);
  return c;
}

void main() {
  test('config default apiBase', () {
    expect(apiBase, 'http://127.0.0.1:8099');
  });

  test('t() differs for en vs rw', () {
    expect(translate('en', 'nav.chat'), isNot(translate('rw', 'nav.chat')));
    expect(translate('rw', 'app.name'), 'Ubuzima');
    expect(translate('en', 'missing.key'), 'missing.key');
  });

  test('language defaults to en and toggling persists', () async {
    final c = await makeContainer();
    expect(c.read(languageProvider), 'en');
    await c.read(languageProvider.notifier).set('rw');
    expect(c.read(languageProvider), 'rw');
    final prefs = c.read(prefsProvider)!;
    expect(prefs.getString('lang'), 'rw');
    final c2 = ProviderContainer(overrides: [prefsProvider.overrideWithValue(prefs)]);
    addTearDown(c2.dispose);
    expect(c2.read(languageProvider), 'rw');
  });

  test('theme mode defaults to system and persists', () async {
    final c = await makeContainer();
    expect(c.read(themeModeProvider), ThemeMode.system);
    await c.read(themeModeProvider.notifier).set(ThemeMode.dark);
    expect(c.read(prefsProvider)!.getString('theme_mode'), 'dark');
  });

  test('light and dark color schemes, no gradients', () {
    expect(buildTheme(Brightness.light).colorScheme.brightness, Brightness.light);
    expect(buildTheme(Brightness.dark).colorScheme.brightness, Brightness.dark);
    expect(lightTheme.colorScheme.primary, isNot(darkTheme.colorScheme.primary));
  });

  testWidgets('shell shows app name and nav destinations', (tester) async {
    SharedPreferences.setMockInitialValues({'onboarded': '1'});
    final prefs = await SharedPreferences.getInstance();
    await tester.pumpWidget(ProviderScope(
      overrides: [prefsProvider.overrideWithValue(prefs)],
      child: const UbuzimaApp(),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Ubuzima'), findsWidgets);
    expect(find.text('Chat'), findsWidgets);
    expect(find.text('Settings'), findsWidgets);
    await tester.tap(find.byIcon(Icons.settings_outlined));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Kinyarwanda'));
    await tester.pumpAndSettle();
    expect(find.text('Ibiganiro'), findsWidgets);
  });
}
