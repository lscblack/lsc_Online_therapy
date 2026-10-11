import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../../state/voice.dart';
import '../chat/assistant_response.dart';

/// Opens the voice panel as a bottom sheet. State is scoped to the sheet, so
/// the mic and player are released when it closes.
Future<void> showVoicePanel(BuildContext context) => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (_) => const VoicePanel(),
    );

String _mmss(Duration d) =>
    '${d.inMinutes.toString().padLeft(2, '0')}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';

class VoicePanel extends ConsumerWidget {
  const VoicePanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final s = ref.watch(voiceControllerProvider);
    final c = ref.read(voiceControllerProvider.notifier);
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    // After a failed turn, don't leave the previous answer reading as its result.
    final last = s.phase == VoicePhase.error ? null : s.last;
    final status = switch (s.phase) {
      VoicePhase.recording => t('voice.recording'),
      VoicePhase.processing => t('voice.processing'),
      _ => t('voice.ready'),
    };
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(t('voice.title'), style: tt.titleLarge, textAlign: TextAlign.center),
              const SizedBox(height: 4),
              Text(t('voice.hint'),
                  style: tt.bodyMedium?.copyWith(color: cs.onSurfaceVariant),
                  textAlign: TextAlign.center),
              const SizedBox(height: 16),
              if (s.phase == VoicePhase.denied)
                _Notice(key: const Key('voice-denied'), text: t('voice.denied'))
              else if (s.phase == VoicePhase.unavailable)
                _Notice(
                    key: const Key('voice-unavailable'),
                    text: t('voice.unavailable'))
              else if (s.phase == VoicePhase.error)
                _Notice(key: const Key('voice-error'), text: t('voice.error')),
              if (last != null) ...[
                const SizedBox(height: 8),
                if (last.response.transcript.trim().isNotEmpty) ...[
                  Align(
                      alignment: Alignment.centerRight,
                      child: Semantics(
                          label: t('voice.you'),
                          child: UserBubble(text: last.response.transcript))),
                  const SizedBox(height: 10),
                ],
                // Same crisis / referral / citation treatment as chat.
                Align(
                    alignment: Alignment.centerLeft,
                    child: AssistantResponseView.fromVoice(last.response)),
                const SizedBox(height: 10),
                if (c.canPlay(last))
                  _PlaybackRow(
                    playing: s.playing,
                    muted: s.muted,
                    onPlay: () => c.play(last),
                    onStop: c.stopPlayback,
                    onMute: c.toggleMute,
                  )
                else
                  Text(t('voice.textOnly'),
                      key: const Key('voice-text-only'),
                      style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
              ],
              const SizedBox(height: 20),
              Center(
                child: Column(children: [
                  RecordButton(
                    recording: s.phase == VoicePhase.recording,
                    busy: s.phase == VoicePhase.processing,
                    onPressed: c.toggle,
                  ),
                  const SizedBox(height: 8),
                  // Announce state changes to screen readers.
                  Semantics(
                    liveRegion: true,
                    child: Text(status, style: tt.titleSmall),
                  ),
                  if (s.phase == VoicePhase.recording)
                    Text(_mmss(s.elapsed),
                        key: const Key('voice-elapsed'),
                        style: tt.bodyMedium?.copyWith(
                            fontFeatures: const [FontFeature.tabularFigures()])),
                ]),
              ),
              const SizedBox(height: 16),
              Center(
                child: Tooltip(
                  message: t('voice.live'),
                  child: OutlinedButton.icon(
                    key: const Key('voice-live-soon'),
                    onPressed: null,
                    icon: const Icon(Icons.graphic_eq),
                    label: Text(t('voice.live')),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({super.key, required this.text});
  final String text;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          border: Border.all(color: cs.outlineVariant),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(children: [
          ExcludeSemantics(
              child: Icon(Icons.mic_off_outlined, color: cs.onSurfaceVariant)),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: Theme.of(context).textTheme.bodyMedium)),
        ]),
      ),
    );
  }
}

class _PlaybackRow extends ConsumerWidget {
  const _PlaybackRow({
    required this.playing,
    required this.muted,
    required this.onPlay,
    required this.onStop,
    required this.onMute,
  });
  final bool playing;
  final bool muted;
  final VoidCallback onPlay;
  final VoidCallback onStop;
  final VoidCallback onMute;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    return Row(children: [
      OutlinedButton.icon(
        key: const Key('voice-replay'),
        onPressed: playing ? onStop : onPlay,
        icon: Icon(playing ? Icons.stop : Icons.replay),
        label: Text(playing ? t('voice.pause') : t('voice.replay')),
      ),
      const SizedBox(width: 8),
      IconButton(
        key: const Key('voice-mute'),
        tooltip: muted ? t('voice.unmute') : t('voice.mute'),
        onPressed: onMute,
        icon: Icon(muted ? Icons.volume_off : Icons.volume_up),
        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
      ),
    ]);
  }
}

/// Large press-to-toggle mic button with a soft pulse while recording
/// (static when reduce-motion is on).
class RecordButton extends ConsumerStatefulWidget {
  const RecordButton({
    super.key = const Key('record-button'),
    required this.recording,
    required this.busy,
    required this.onPressed,
  });
  final bool recording;
  final bool busy;
  final VoidCallback onPressed;
  @override
  ConsumerState<RecordButton> createState() => _RecordButtonState();
}

class _RecordButtonState extends ConsumerState<RecordButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1400));

  void _sync() {
    final animate =
        widget.recording && !MediaQuery.disableAnimationsOf(context);
    if (animate && !_c.isAnimating) {
      _c.repeat(reverse: true);
    } else if (!animate && _c.isAnimating) {
      _c.stop();
      _c.value = 0;
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sync();
  }

  @override
  void didUpdateWidget(RecordButton old) {
    super.didUpdateWidget(old);
    _sync();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    final cs = Theme.of(context).colorScheme;
    final label = widget.recording ? t('voice.stop') : t('voice.record');
    final bg = widget.recording ? cs.tertiary : cs.primary;
    final fg = widget.recording ? cs.onTertiary : cs.onPrimary;
    return Semantics(
      button: true,
      enabled: !widget.busy,
      label: label,
      value: widget.recording ? t('voice.recording') : null,
      onTap: widget.busy ? null : widget.onPressed,
      excludeSemantics: true,
      child: SizedBox(
        width: 120,
        height: 120,
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, child) => Stack(
            alignment: Alignment.center,
            children: [
              if (widget.recording)
                Container(
                  width: 88 + 32 * _c.value,
                  height: 88 + 32 * _c.value,
                  decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: bg.withValues(alpha: 0.22 * (1 - _c.value * 0.5))),
                ),
              child!,
            ],
          ),
          child: Material(
            color: bg,
            shape: const CircleBorder(),
            child: InkWell(
              customBorder: const CircleBorder(),
              onTap: widget.busy ? null : widget.onPressed,
              child: SizedBox(
                width: 88,
                height: 88,
                child: widget.busy
                    ? Padding(
                        padding: const EdgeInsets.all(28),
                        child: CircularProgressIndicator(color: fg, strokeWidth: 3))
                    : Icon(widget.recording ? Icons.stop : Icons.mic,
                        size: 40, color: fg),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
