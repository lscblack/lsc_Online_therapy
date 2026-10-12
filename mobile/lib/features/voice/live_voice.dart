import 'dart:async';
import 'dart:io' show Directory, File;
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:record/record.dart';

import '../../core/i18n/i18n.dart';
import '../../state/auth.dart';

enum LivePhase { idle, listening, thinking, speaking, error }

class LiveTurn {
  const LiveTurn(this.role, this.text);
  final String role; // 'user' | 'assistant'
  final String text;
}

class LiveVoiceState {
  const LiveVoiceState({this.phase = LivePhase.idle, this.turns = const [], this.error});
  final LivePhase phase;
  final List<LiveTurn> turns;
  final String? error;
  bool get running => phase != LivePhase.idle && phase != LivePhase.error;

  LiveVoiceState copyWith({LivePhase? phase, List<LiveTurn>? turns, Object? error = _keep}) =>
      LiveVoiceState(
        phase: phase ?? this.phase,
        turns: turns ?? this.turns,
        error: identical(error, _keep) ? this.error : error as String?,
      );
}

const _keep = Object();

/// Hands-free live voice: auto-listen (with silence detection) -> transcribe + answer (reusing the
/// guarded /v1/voice/chat turn) -> speak the answer with the device's TTS -> auto-listen again.
class LiveVoiceController extends AutoDisposeNotifier<LiveVoiceState> {
  final AudioRecorder _rec = AudioRecorder();
  final FlutterTts _tts = FlutterTts();
  bool _running = false;
  StreamSubscription<Amplitude>? _amp;
  String? _conversationId;

  @override
  LiveVoiceState build() {
    ref.onDispose(() {
      _running = false;
      _amp?.cancel();
      _rec.dispose();
      _tts.stop();
    });
    return const LiveVoiceState();
  }

  Future<void> start() async {
    if (_running) return;
    try {
      if (!await _rec.hasPermission()) {
        state = state.copyWith(phase: LivePhase.error, error: 'denied');
        return;
      }
    } catch (_) {
      state = state.copyWith(phase: LivePhase.error, error: 'unavailable');
      return;
    }
    await _tts.awaitSpeakCompletion(true);
    _running = true;
    state = state.copyWith(phase: LivePhase.listening, turns: const [], error: null);
    unawaited(_loop());
  }

  Future<void> _loop() async {
    while (_running) {
      final audio = await _listen();
      if (!_running) break;
      if (audio == null || audio.length < 2000) continue; // silence / too short
      state = state.copyWith(phase: LivePhase.thinking);
      try {
        final lang = ref.read(languageProvider);
        final r = await ref
            .read(voiceApiProvider)
            .chat(audio, conversationId: _conversationId, language: lang);
        if (r.conversationId.isNotEmpty) _conversationId = r.conversationId;
        state = state.copyWith(turns: [
          ...state.turns,
          if (r.transcript.trim().isNotEmpty) LiveTurn('user', r.transcript),
          LiveTurn('assistant', r.answer),
        ]);
        if (!_running) break;
        state = state.copyWith(phase: LivePhase.speaking);
        await _speak(r.answer, r.language);
      } catch (_) {
        if (_running) {
          state = state.copyWith(phase: LivePhase.error, error: 'error');
          await Future<void>.delayed(const Duration(seconds: 1));
          if (_running) state = state.copyWith(phase: LivePhase.listening, error: null);
        }
      }
    }
  }

  Future<Uint8List?> _listen() async {
    state = state.copyWith(phase: LivePhase.listening);
    final path = kIsWeb
        ? ''
        : '${Directory.systemTemp.path}/ubuzima_live_${DateTime.now().microsecondsSinceEpoch}.m4a';
    try {
      await _rec.start(
          RecordConfig(encoder: kIsWeb ? AudioEncoder.opus : AudioEncoder.aacLc), path: path);
    } catch (_) {
      return null;
    }
    final done = Completer<void>();
    var heardSpeech = false;
    DateTime? silenceAt;
    final startedAt = DateTime.now();
    await _amp?.cancel();
    _amp = _rec.onAmplitudeChanged(const Duration(milliseconds: 250)).listen((a) {
      final now = DateTime.now();
      final loud = a.current > -28; // dBFS: speaking is louder than ambient
      if (loud) {
        heardSpeech = true;
        silenceAt = null;
      } else if (heardSpeech) {
        silenceAt ??= now;
      }
      final endedBySilence =
          silenceAt != null && now.difference(silenceAt!) > const Duration(milliseconds: 1300);
      final maxedOut = now.difference(startedAt) > const Duration(seconds: 15);
      if (!_running || (heardSpeech && endedBySilence) || maxedOut) {
        if (!done.isCompleted) done.complete();
      }
    });
    // Safety: never hang if amplitude never fires.
    unawaited(Future<void>.delayed(const Duration(seconds: 16)).then((_) {
      if (!done.isCompleted) done.complete();
    }));
    await done.future;
    await _amp?.cancel();
    _amp = null;
    String? out;
    try {
      out = await _rec.stop();
    } catch (_) {
      return null;
    }
    if (!heardSpeech || out == null || out.isEmpty) return null;
    if (kIsWeb) {
      final res = await Dio().get<List<int>>(out, options: Options(responseType: ResponseType.bytes));
      return Uint8List.fromList(res.data ?? const []);
    }
    final f = File(out);
    final bytes = await f.readAsBytes();
    try {
      await f.delete();
    } catch (_) {}
    return bytes;
  }

  Future<void> _speak(String text, String lang) async {
    final clean = text
        .replaceAll(RegExp(r'\s*\[S\d+\]'), '')
        .replaceAll('**', '')
        .replaceAll(RegExp(r'^\s*[*\-•]\s+', multiLine: true), '');
    if (clean.trim().isEmpty) return;
    try {
      await _tts.setLanguage(lang == 'rw' ? 'rw-RW' : 'en-US');
    } catch (_) {
      try {
        await _tts.setLanguage('en-US');
      } catch (_) {}
    }
    try {
      await _tts.speak(clean); // awaits completion (awaitSpeakCompletion=true)
    } catch (_) {}
  }

  /// Stop the agent speaking and return to listening (barge-in).
  Future<void> interrupt() async {
    try {
      await _tts.stop();
    } catch (_) {}
    if (_running) state = state.copyWith(phase: LivePhase.listening);
  }

  Future<void> stop() async {
    _running = false;
    await _amp?.cancel();
    _amp = null;
    try {
      await _rec.stop();
    } catch (_) {}
    try {
      await _tts.stop();
    } catch (_) {}
    state = state.copyWith(phase: LivePhase.idle);
  }
}

final liveVoiceProvider =
    AutoDisposeNotifierProvider<LiveVoiceController, LiveVoiceState>(LiveVoiceController.new);
