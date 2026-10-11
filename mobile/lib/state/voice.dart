import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models/chat.dart';
import '../features/voice/voice_io.dart';
import 'auth.dart';
import '../core/i18n/i18n.dart';
import 'chat.dart';

final voiceRecorderProvider =
    Provider<VoiceRecorder>((ref) => RecordVoiceRecorder());
final voicePlayerProvider =
    Provider<VoicePlayer>((ref) => JustAudioVoicePlayer());

enum VoicePhase { idle, starting, recording, processing, denied, unavailable, error }

/// One voice exchange. Transcript/answer are never logged.
class VoiceTurn {
  VoiceTurn(this.response) : audio = _decode(response);
  final VoiceResponse response;

  /// Decoded reply audio, or null when TTS is unavailable/empty/invalid.
  final Uint8List? audio;

  static Uint8List? _decode(VoiceResponse r) {
    if (!r.ttsAvailable || r.audioBase64.isEmpty) return null;
    try {
      return base64Decode(r.audioBase64);
    } catch (_) {
      return null;
    }
  }
}

class VoiceState {
  const VoiceState({
    this.phase = VoicePhase.idle,
    this.elapsed = Duration.zero,
    this.turns = const [],
    this.playing = false,
    this.muted = false,
  });
  final VoicePhase phase;
  final Duration elapsed;
  final List<VoiceTurn> turns;
  final bool playing;
  final bool muted;

  VoiceTurn? get last => turns.isEmpty ? null : turns.last;

  VoiceState copyWith({
    VoicePhase? phase,
    Duration? elapsed,
    List<VoiceTurn>? turns,
    bool? playing,
    bool? muted,
  }) =>
      VoiceState(
        phase: phase ?? this.phase,
        elapsed: elapsed ?? this.elapsed,
        turns: turns ?? this.turns,
        playing: playing ?? this.playing,
        muted: muted ?? this.muted,
      );
}

class VoiceController extends AutoDisposeNotifier<VoiceState> {
  Timer? _ticker;
  bool _disposed = false;
  late final VoiceRecorder _rec = ref.read(voiceRecorderProvider);
  late final VoicePlayer _player = ref.read(voicePlayerProvider);
  StreamSubscription<bool>? _playSub;

  @override
  VoiceState build() {
    _rec; // bind now so dispose can release them
    // Reflect real playback (ended / stopped / failed) in state.
    _playSub = _player.playingStream.listen((p) {
      if (!_disposed && state.playing != p) state = state.copyWith(playing: p);
    });
    ref.onDispose(() {
      _disposed = true;
      _ticker?.cancel();
      _playSub?.cancel();
      // Release the mic and playback even if mid-recording.
      unawaited(_release());
    });
    return const VoiceState();
  }

  Future<void> _release() async {
    try {
      await _rec.stop();
    } catch (_) {}
    try {
      await _rec.dispose();
    } catch (_) {}
    try {
      await _player.dispose();
    } catch (_) {}
  }

  bool get isRecording => state.phase == VoicePhase.recording;

  /// Tap handler: start when idle/errored, stop+send when recording.
  Future<void> toggle() async {
    switch (state.phase) {
      case VoicePhase.recording:
        await stopAndSend();
      case VoicePhase.processing || VoicePhase.starting:
        return;
      default:
        await start();
    }
  }

  Future<void> start() async {
    // Re-entrancy guard: ignore taps while starting/recording/processing.
    if (state.phase == VoicePhase.starting ||
        state.phase == VoicePhase.recording ||
        state.phase == VoicePhase.processing) {
      return;
    }
    state = state.copyWith(phase: VoicePhase.starting);
    // Never record over a playing reply.
    await _stopPlayback();
    try {
      if (!await _rec.ensurePermission()) {
        if (!_disposed) state = state.copyWith(phase: VoicePhase.denied);
        return;
      }
      await _rec.start();
    } catch (_) {
      if (!_disposed) state = state.copyWith(phase: VoicePhase.unavailable);
      return;
    }
    if (_disposed) return;
    state = state.copyWith(phase: VoicePhase.recording, elapsed: Duration.zero);
    _ticker?.cancel();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_disposed) return;
      state = state.copyWith(elapsed: state.elapsed + const Duration(seconds: 1));
    });
  }

  Future<void> stopAndSend() async {
    if (!isRecording) return;
    _ticker?.cancel();
    state = state.copyWith(phase: VoicePhase.processing);
    try {
      final audio = await _rec.stop();
      if (audio == null || audio.bytes.isEmpty) {
        if (!_disposed) state = state.copyWith(phase: VoicePhase.error);
        return;
      }
      final r = await ref.read(voiceApiProvider).chat(audio.bytes,
          conversationId: ref.read(chatProvider).conversationId,
          language: ref.read(languageProvider),
          filename: audio.filename);
      if (_disposed) return;
      if (r.conversationId.isNotEmpty) {
        ref.read(chatProvider.notifier).adoptConversation(r.conversationId);
      }
      state = state.copyWith(
          phase: VoicePhase.idle, turns: [...state.turns, VoiceTurn(r)]);
      await _autoplay(state.turns.last);
    } catch (_) {
      if (!_disposed) state = state.copyWith(phase: VoicePhase.error);
    }
  }

  bool canPlay(VoiceTurn turn) => turn.audio != null;

  Future<void> _autoplay(VoiceTurn turn) => play(turn);

  Future<void> play(VoiceTurn turn) async {
    final bytes = turn.audio;
    if (bytes == null) return;
    try {
      await _player.stop();
      await _player.setMuted(state.muted);
      await _player.play(bytes, turn.response.audioMime);
      if (!_disposed) state = state.copyWith(playing: true);
    } catch (_) {
      // Playback is a bonus; the text answer is already shown.
      if (!_disposed) state = state.copyWith(playing: false);
    }
  }

  Future<void> stopPlayback() => _stopPlayback();

  Future<void> _stopPlayback() async {
    try {
      await _player.stop();
    } catch (_) {}
    if (!_disposed) state = state.copyWith(playing: false);
  }

  Future<void> toggleMute() async {
    if (_disposed) return;
    final m = !state.muted;
    state = state.copyWith(muted: m);
    try {
      await _player.setMuted(m);
    } catch (_) {}
  }
}

final voiceControllerProvider =
    NotifierProvider.autoDispose<VoiceController, VoiceState>(
        VoiceController.new);
