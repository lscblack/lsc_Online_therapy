import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../../data/models/chat.dart';
import 'markdown_text.dart';

/// Reusable assistant reply: bubble text + citations + calm referral/crisis
/// callouts + neutral error state. Shared by chat (Task 4) and voice (Task 5).
///
/// Build from raw fields, or via [AssistantResponseView.fromChat] /
/// [AssistantResponseView.fromVoice].
class AssistantResponseView extends ConsumerWidget {
  const AssistantResponseView({
    super.key,
    required this.text,
    this.citations = const [],
    this.safetyFlags = const SafetyFlags(),
    this.streaming = false,
    this.failed = false,
    this.offline = false,
    this.onRetry,
  });

  factory AssistantResponseView.fromChat(ChatResponse r, {Key? key}) =>
      AssistantResponseView(
          key: key,
          text: r.answer,
          citations: r.citations,
          safetyFlags: r.safetyFlags);

  factory AssistantResponseView.fromVoice(VoiceResponse r, {Key? key}) =>
      AssistantResponseView(
          key: key,
          text: r.answer,
          citations: r.citations,
          safetyFlags: r.safetyFlags);

  final String text;
  final List<Citation> citations;
  final SafetyFlags safetyFlags;
  final bool streaming;
  final bool failed;
  final bool offline;
  final VoidCallback? onRetry;

  /// Referral applies when flagged or the answer is outside the knowledge base.
  bool get showReferral =>
      !safetyFlags.crisis &&
      (safetyFlags.needsReferral || safetyFlags.inKnowledge == false);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final done = !streaming && !failed;
    return Semantics(
      container: true,
      // Announce once the reply is complete, not per token.
      liveRegion: !streaming,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (failed) ...[
            // Keep any partial text visible above the error card.
            if (text.isNotEmpty) ...[
              AssistantBubble(
                  child: MarkdownText(text,
                      style: Theme.of(context)
                          .textTheme
                          .bodyLarge
                          ?.copyWith(color: cs.onSurface))),
              const SizedBox(height: 8),
            ],
            ChatErrorCard(offline: offline, onRetry: onRetry),
          ] else ...[
            if (text.isNotEmpty || streaming)
              AssistantBubble(
                  child: text.isEmpty
                      ? const TypingIndicator()
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            MarkdownText(text,
                                style: Theme.of(context)
                                    .textTheme
                                    .bodyLarge
                                    ?.copyWith(color: cs.onSurface)),
                            if (streaming) ...[
                              const SizedBox(height: 6),
                              const TypingIndicator(),
                            ],
                          ],
                        )),
            if (done && safetyFlags.crisis) ...[
              const SizedBox(height: 8),
              const CrisisPanel(),
            ],
            if (done && showReferral) ...[
              const SizedBox(height: 8),
              const ReferralCallout(),
            ],
            if (done && citations.isNotEmpty) ...[
              const SizedBox(height: 8),
              CitationChips(citations: citations),
            ],
          ],
        ],
      ),
    );
  }
}

class AssistantBubble extends StatelessWidget {
  const AssistantBubble({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      key: const Key('assistant-bubble'),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(6),
          topRight: Radius.circular(20),
          bottomLeft: Radius.circular(20),
          bottomRight: Radius.circular(20),
        ),
      ),
      child: child,
    );
  }
}

class UserBubble extends StatelessWidget {
  const UserBubble({super.key, required this.text});
  final String text;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      key: const Key('user-bubble'),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: cs.primaryContainer,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(20),
          topRight: Radius.circular(6),
          bottomLeft: Radius.circular(20),
          bottomRight: Radius.circular(20),
        ),
      ),
      child: SelectableText(text,
          style: Theme.of(context)
              .textTheme
              .bodyLarge
              ?.copyWith(color: cs.onPrimaryContainer)),
    );
  }
}

/// Soft callout with an icon: shared look for calm (non-error) notices.
class _CalmCard extends StatelessWidget {
  const _CalmCard({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    required this.background,
    required this.foreground,
  });
  final IconData icon;
  final String title;
  final String body;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ExcludeSemantics(child: Icon(icon, color: foreground)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: tt.titleSmall
                        ?.copyWith(color: foreground, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(body, style: tt.bodyMedium?.copyWith(color: foreground)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Calm, caring "talk to a doctor" notice. Never an error style.
class ReferralCallout extends ConsumerWidget {
  const ReferralCallout({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final cs = Theme.of(context).colorScheme;
    return _CalmCard(
      key: const Key('referral-callout'),
      icon: Icons.medical_services_outlined,
      title: t('chat.referral.title'),
      body: t('chat.referral.body'),
      background: cs.secondaryContainer,
      foreground: cs.onSecondaryContainer,
    );
  }
}

/// Supportive crisis panel: warm, caring, referral foregrounded. Not an alarm.
class CrisisPanel extends ConsumerWidget {
  const CrisisPanel({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final cs = Theme.of(context).colorScheme;
    return Semantics(
      container: true,
      child: _CalmCard(
        key: const Key('crisis-panel'),
        icon: Icons.favorite_outline,
        title: t('chat.crisis.title'),
        body: t('chat.crisis.body'),
        background: cs.primaryContainer,
        foreground: cs.onPrimaryContainer,
      ),
    );
  }
}

/// Neutral (non-red) failure state with a retry action.
class ChatErrorCard extends ConsumerWidget {
  const ChatErrorCard({super.key, this.offline = false, this.onRetry});
  final bool offline;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final cs = Theme.of(context).colorScheme;
    return Container(
      key: const Key('chat-error'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        border: Border.all(color: cs.outlineVariant),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            ExcludeSemantics(
                child: Icon(offline ? Icons.cloud_off_outlined : Icons.refresh,
                    color: cs.onSurfaceVariant)),
            const SizedBox(width: 10),
            Expanded(
                child: Text(t('chat.error.title'),
                    style: Theme.of(context).textTheme.titleSmall)),
          ]),
          const SizedBox(height: 4),
          Text(offline ? t('chat.error.offline') : t('chat.error.body'),
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: cs.onSurfaceVariant)),
          if (onRetry != null) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('retry-button'),
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: Text(t('chat.retry')),
            ),
          ],
        ],
      ),
    );
  }
}

class CitationChips extends ConsumerWidget {
  const CitationChips({super.key, required this.citations});
  final List<Citation> citations;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final cs = Theme.of(context).colorScheme;
    return Semantics(
      container: true,
      label: t('chat.sources'),
      child: Wrap(
        key: const Key('citations'),
        spacing: 8,
        runSpacing: 4,
        children: [
          for (var i = 0; i < citations.length; i++)
            Chip(
              key: Key('citation-chip-$i'),
              avatar: Icon(Icons.menu_book_outlined,
                  size: 16, color: cs.onSecondaryContainer),
              label: Text(_label(citations[i], i)),
              backgroundColor: cs.secondaryContainer,
              labelStyle: TextStyle(color: cs.onSecondaryContainer),
              side: BorderSide.none,
            ),
        ],
      ),
    );
  }

  static String _label(Citation c, int i) {
    final title = (c.title ?? '').trim();
    final base = title.isEmpty ? '${i + 1}' : title;
    return c.page != null ? '$base, p.${c.page}' : base;
  }
}

/// Three softly pulsing dots; static when reduce-motion is on.
class TypingIndicator extends ConsumerStatefulWidget {
  const TypingIndicator({super.key});
  @override
  ConsumerState<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends ConsumerState<TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1200));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    final color = Theme.of(context).colorScheme.onSurfaceVariant;
    return Semantics(
      label: t('chat.typing'),
      child: ExcludeSemantics(
        child: SizedBox(
          key: const Key('typing-indicator'),
          height: 16,
          child: AnimatedBuilder(
            animation: _c,
            builder: (context, child) => Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (var i = 0; i < 3; i++)
                  Padding(
                    padding: const EdgeInsets.only(right: 5),
                    child: Opacity(
                      opacity: _c.isAnimating
                          ? 0.35 + 0.65 * _pulse((_c.value - i * 0.15) % 1.0)
                          : 0.7,
                      child: Container(
                          width: 8,
                          height: 8,
                          decoration:
                              BoxDecoration(color: color, shape: BoxShape.circle)),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  double _pulse(double v) => v < 0.5 ? v * 2 : (1 - v) * 2;
}
