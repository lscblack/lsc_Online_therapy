import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../chat/chat_screen.dart';
import '../settings/settings_page.dart';
import '../voice/voice_panel.dart';

/// Bottom-nav scaffold: Chat, Voice, Settings.
class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});
  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _index = 0;

  Widget _page() => switch (_index) {
    0 => const ChatScreen(key: ValueKey('page-chat')),
    1 => const VoicePanel(key: ValueKey('page-voice')),
    _ => const SettingsPage(key: ValueKey('page-settings')),
  };

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    final reduce = MediaQuery.of(context).disableAnimations;
    return Scaffold(
      appBar: AppBar(title: Text(t('app.name'))),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: AnimatedSwitcher(
              duration: reduce
                  ? Duration.zero
                  : const Duration(milliseconds: 200),
              child: _page(),
            ),
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
            label: t('nav.chat'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.mic_none),
            selectedIcon: const Icon(Icons.mic),
            label: t('nav.voice'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.settings_outlined),
            selectedIcon: const Icon(Icons.settings),
            label: t('nav.settings'),
          ),
        ],
      ),
    );
  }
}
