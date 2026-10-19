import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../../state/auth.dart';
import '../../state/chat.dart';
import '../voice/voice_panel.dart';
import 'assistant_response.dart';

export 'assistant_response.dart';

/// Nickname for the welcome state; null when unavailable (never throws).
final chatNicknameProvider = FutureProvider<String?>((ref) async {
  try {
    final n = (await ref.read(profileApiProvider).get()).nickname?.trim();
    return (n == null || n.isEmpty) ? null : n;
  } catch (_) {
    return null;
  }
});

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});
  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _text = TextEditingController();
  final _focus = FocusNode();

  @override
  void dispose() {
    _text.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _submit() {
    final v = _text.text.trim();
    if (v.isEmpty || ref.read(chatProvider).busy) return;
    _text.clear();
    ref.read(chatProvider.notifier).send(v);
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    final chat = ref.watch(chatProvider);
    final msgs = chat.messages;
    return Column(
      children: [
        Expanded(
          child: RefreshIndicator(
            // Pull down to reconnect (re-establish the identity against the backend).
            onRefresh: () => ref.read(authProvider.notifier).ensureAnon().catchError((_) {}),
            child: msgs.isEmpty
                ? ListView(
                    key: const Key('chat-thread'),
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: const [_Welcome()],
                  )
                : Semantics(
                    container: true,
                    label: t('chat.thread'),
                    child: ListView.builder(
                      key: const Key('chat-thread'),
                      reverse: true,
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                      itemCount: msgs.length,
                      itemBuilder: (_, i) {
                        final m = msgs[msgs.length - 1 - i];
                        final isLast = i == 0;
                        return _MessageRow(
                          key: ValueKey(m.id),
                          m: m,
                          // A sent message reads as "seen" once something follows it.
                          seen: !isLast,
                          onRetry: isLast
                              ? () => ref.read(chatProvider.notifier).retry(m.id)
                              : null,
                        );
                      },
                    ),
                  ),
          ),
        ),
        _Composer(
          controller: _text,
          focus: _focus,
          enabled: !chat.busy,
          onSend: _submit,
        ),
      ],
    );
  }
}

class _MessageRow extends ConsumerWidget {
  const _MessageRow(
      {super.key, required this.m, required this.onRetry, this.seen = false});
  final ChatMessage m;
  final bool seen;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isUser = m.role == ChatRole.user;
    final reduce = MediaQuery.disableAnimationsOf(context);
    final maxW = MediaQuery.sizeOf(context).width * 0.85;
    final body = Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxW.clamp(0, 560)),
        child: isUser
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  UserBubble(text: m.text),
                  SentMeta(seen: seen),
                ],
              )
            : AssistantResponseView(
                text: m.text,
                citations: m.citations,
                safetyFlags: m.safetyFlags,
                streaming: m.status == MessageStatus.streaming,
                failed: m.status == MessageStatus.error,
                onRetry: onRetry,
              ),
      ),
    );
    final padded = Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: body);
    if (reduce) return padded;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOut,
      builder: (_, v, child) => Opacity(
        opacity: v,
        child: Transform.translate(offset: Offset(0, (1 - v) * 8), child: child),
      ),
      child: padded,
    );
  }
}

class _Welcome extends ConsumerWidget {
  const _Welcome();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final nick = ref.watch(chatNicknameProvider).valueOrNull;
    final tt = Theme.of(context).textTheme;
    final title = nick == null
        ? t('chat.welcome')
        : t('chat.welcomeNamed').replaceAll('{name}', nick);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          key: const Key('chat-welcome'),
          mainAxisSize: MainAxisSize.min,
          children: [
            ExcludeSemantics(
                child: Icon(Icons.favorite_outline,
                    size: 40, color: Theme.of(context).colorScheme.primary)),
            const SizedBox(height: 12),
            Text(title, textAlign: TextAlign.center, style: tt.titleLarge),
            const SizedBox(height: 8),
            Text(t('chat.welcomeSub'), textAlign: TextAlign.center, style: tt.bodyLarge),
          ],
        ),
      ),
    );
  }
}

class _Composer extends ConsumerWidget {
  const _Composer({
    required this.controller,
    required this.focus,
    required this.enabled,
    required this.onSend,
  });
  final TextEditingController controller;
  final FocusNode focus;
  final bool enabled;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Semantics(
              label: t('chat.composer'),
              child: TextField(
                key: const Key('composer-field'),
                controller: controller,
                focusNode: focus,
                minLines: 1,
                maxLines: 5,
                keyboardType: TextInputType.multiline,
                textInputAction: TextInputAction.newline,
                textCapitalization: TextCapitalization.sentences,
                decoration: InputDecoration(
                  hintText: t('chat.hint'),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.outlined(
            key: const Key('voice-button'),
            tooltip: t('voice.open'),
            onPressed: () => showVoicePanel(context),
            icon: const Icon(Icons.mic_none),
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            key: const Key('send-button'),
            tooltip: t('btn.send'),
            onPressed: enabled ? onSend : null,
            icon: const Icon(Icons.send_rounded),
            iconSize: 22,
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
          ),
        ],
      ),
    );
  }
}

