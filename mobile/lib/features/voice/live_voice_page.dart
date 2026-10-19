import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../chat/markdown_text.dart';
import 'live_voice.dart';

/// Full-screen hands-free live voice conversation.
class LiveVoicePage extends ConsumerWidget {
  const LiveVoicePage({super.key});

  String _statusKey(LivePhase p) => switch (p) {
        LivePhase.idle => 'live.idle',
        LivePhase.listening => 'live.listening',
        LivePhase.thinking => 'live.thinking',
        LivePhase.speaking => 'live.speaking',
        LivePhase.error => 'chat.error.title',
      };

  Color _orbColor(LivePhase p, ColorScheme cs) => switch (p) {
        LivePhase.listening => cs.primary,
        LivePhase.thinking => cs.tertiary,
        LivePhase.speaking => cs.secondary,
        LivePhase.error => cs.error,
        LivePhase.idle => cs.outline,
      };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final s = ref.watch(liveVoiceProvider);
    final c = ref.read(liveVoiceProvider.notifier);
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: Text(t('live.title'))),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: Column(
              children: [
                Expanded(
                  child: s.turns.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text(t('live.hint'),
                                textAlign: TextAlign.center,
                                style: tt.bodyLarge?.copyWith(color: cs.onSurfaceVariant)),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: s.turns.length,
                          itemBuilder: (_, i) {
                            final turn = s.turns[s.turns.length - 1 - i];
                            final isUser = turn.role == 'user';
                            return Align(
                              alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                              child: Container(
                                margin: const EdgeInsets.only(bottom: 10),
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                constraints: BoxConstraints(
                                    maxWidth: MediaQuery.of(context).size.width * 0.82),
                                decoration: BoxDecoration(
                                  color: isUser ? cs.primary : cs.surfaceContainerHighest,
                                  border: isUser
                                      ? null
                                      : Border.all(
                                          color: cs.outlineVariant.withValues(alpha: 0.6)),
                                  borderRadius: BorderRadius.only(
                                    topLeft: const Radius.circular(18),
                                    topRight: const Radius.circular(18),
                                    bottomLeft: Radius.circular(isUser ? 18 : 4),
                                    bottomRight: Radius.circular(isUser ? 4 : 18),
                                  ),
                                ),
                                child: isUser
                                    ? Text(turn.text,
                                        style: tt.bodyLarge?.copyWith(color: cs.onPrimary))
                                    : MarkdownText(turn.text,
                                        style: tt.bodyLarge?.copyWith(color: cs.onSurface)),
                              ),
                            );
                          },
                        ),
                ),
                // State orb + status
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Column(
                    children: [
                      _Orb(
                          color: _orbColor(s.phase, cs),
                          foreground: cs.onPrimary,
                          active: s.running),
                      const SizedBox(height: 10),
                      Semantics(
                        liveRegion: true,
                        child: Text(
                          s.error != null
                              ? (s.error == 'denied' ? t('voice.denied') : t('chat.error.body'))
                              : t(_statusKey(s.phase)),
                          style: tt.titleSmall,
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ],
                  ),
                ),
                // Controls
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
                  child: s.running
                      ? Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            OutlinedButton.icon(
                              onPressed: s.phase == LivePhase.speaking ? c.interrupt : null,
                              icon: const Icon(Icons.pan_tool_alt_outlined),
                              label: Text(t('live.interrupt')),
                            ),
                            const SizedBox(width: 12),
                            FilledButton.icon(
                              style: FilledButton.styleFrom(
                                  backgroundColor: cs.error, foregroundColor: cs.onError),
                              onPressed: c.stop,
                              icon: const Icon(Icons.stop),
                              label: Text(t('live.end')),
                            ),
                          ],
                        )
                      : FilledButton.icon(
                          onPressed: () => c.start(),
                          icon: const Icon(Icons.graphic_eq),
                          label: Text(t('live.start')),
                        ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Orb extends StatefulWidget {
  const _Orb({required this.color, required this.foreground, required this.active});
  final Color color;
  final Color foreground;
  final bool active;
  @override
  State<_Orb> createState() => _OrbState();
}

class _OrbState extends State<_Orb> with SingleTickerProviderStateMixin {
  late final AnimationController _ctl =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat(reverse: true);
  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctl,
      builder: (context, _) {
        final scale = widget.active ? 1.0 + _ctl.value * 0.25 : 1.0;
        return Container(
          width: 64 * scale,
          height: 64 * scale,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: widget.color.withValues(alpha: widget.active ? 0.9 : 0.5),
            boxShadow: [
              if (widget.active)
                BoxShadow(color: widget.color.withValues(alpha: 0.4), blurRadius: 20, spreadRadius: 4),
            ],
          ),
          child: Icon(Icons.mic, color: widget.foreground, size: 28),
        );
      },
    );
  }
}
