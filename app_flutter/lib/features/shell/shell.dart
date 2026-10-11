import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../../core/theme.dart';
import '../chat/chat_screen.dart';

/// Bottom-nav scaffold with Chat and Settings destinations.
class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});
  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(t('app.name')),
        actions: [
          IconButton(
            tooltip: t('settings.theme'),
            icon: Icon(Theme.of(context).brightness == Brightness.dark
                ? Icons.light_mode_outlined
                : Icons.dark_mode_outlined),
            onPressed: () {
              final dark = Theme.of(context).brightness == Brightness.dark;
              ref.read(themeModeProvider.notifier).set(dark ? ThemeMode.light : ThemeMode.dark);
            },
          ),
          IconButton(
            tooltip: t('settings.language'),
            icon: const Icon(Icons.translate),
            onPressed: () {
              final l = ref.read(languageProvider);
              ref.read(languageProvider.notifier).set(l == 'en' ? 'rw' : 'en');
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: _index == 0 ? const ChatScreen() : const SettingsPage(),
          ),
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [
          NavigationDestination(
              icon: const Icon(Icons.chat_bubble_outline),
              selectedIcon: const Icon(Icons.chat_bubble),
              label: t('nav.chat')),
          NavigationDestination(
              icon: const Icon(Icons.settings_outlined),
              selectedIcon: const Icon(Icons.settings),
              label: t('nav.settings')),
        ],
      ),
    );
  }
}

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final mode = ref.watch(themeModeProvider);
    final lang = ref.watch(languageProvider);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(t('settings.theme'), style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        SegmentedButton<ThemeMode>(
          segments: [
            ButtonSegment(value: ThemeMode.system, label: Text(t('theme.system'))),
            ButtonSegment(value: ThemeMode.light, label: Text(t('theme.light'))),
            ButtonSegment(value: ThemeMode.dark, label: Text(t('theme.dark'))),
          ],
          selected: {mode},
          onSelectionChanged: (s) => ref.read(themeModeProvider.notifier).set(s.first),
        ),
        const SizedBox(height: 24),
        Text(t('settings.language'), style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        SegmentedButton<String>(
          segments: [
            ButtonSegment(value: 'en', label: Text(t('lang.en'))),
            ButtonSegment(value: 'rw', label: Text(t('lang.rw'))),
          ],
          selected: {lang},
          onSelectionChanged: (s) => ref.read(languageProvider.notifier).set(s.first),
        ),
      ],
    );
  }
}
