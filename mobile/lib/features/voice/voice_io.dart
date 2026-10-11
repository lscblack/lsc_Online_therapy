import 'dart:async';
import 'dart:io' show Directory, File;
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:just_audio/just_audio.dart';
import 'package:record/record.dart';

/// A finished recording ready to upload.
class RecordedAudio {
  const RecordedAudio(this.bytes, this.filename);
  final Uint8List bytes;
  final String filename;
}

/// Mic capture seam so tests never need a real microphone.
abstract class VoiceRecorder {
  /// Ask for (or confirm) microphone permission.
  Future<bool> ensurePermission();
  Future<void> start();

  /// Stops capture and returns the audio, or null if nothing was recorded.
  Future<RecordedAudio?> stop();

  /// Releases the mic and the underlying recorder.
  Future<void> dispose();
}

/// Reply playback seam.
abstract class VoicePlayer {
  /// true while a reply is audibly playing; false when it ends, is stopped,
  /// or fails to start (e.g. web autoplay rejection).
  Stream<bool> get playingStream;
  Future<void> play(Uint8List bytes, String mime);
  Future<void> stop();
  Future<void> setMuted(bool muted);
  Future<void> dispose();
}

/// `record`-backed recorder: opus/webm on web, AAC elsewhere.
class RecordVoiceRecorder implements VoiceRecorder {
  AudioRecorder? _rec;
  AudioRecorder get _r => _rec ??= AudioRecorder();

  @override
  Future<bool> ensurePermission() => _r.hasPermission();

  @override
  Future<void> start() async {
    if (kIsWeb) {
      await _r.start(const RecordConfig(encoder: AudioEncoder.opus), path: '');
    } else {
      final path =
          '${Directory.systemTemp.path}/ubuzima_${DateTime.now().microsecondsSinceEpoch}.m4a';
      await _r.start(const RecordConfig(encoder: AudioEncoder.aacLc),
          path: path);
    }
  }

  @override
  Future<RecordedAudio?> stop() async {
    final rec = _rec;
    if (rec == null) return null;
    final path = await rec.stop();
    if (path == null || path.isEmpty) return null;
    if (kIsWeb) {
      // On web the path is a blob: URL.
      final res = await Dio().get<List<int>>(path,
          options: Options(responseType: ResponseType.bytes));
      return RecordedAudio(
          Uint8List.fromList(res.data ?? const []), 'audio.webm');
    }
    final f = File(path);
    final bytes = await f.readAsBytes();
    try {
      await f.delete();
    } catch (_) {}
    return RecordedAudio(bytes, 'audio.m4a');
  }

  @override
  Future<void> dispose() async {
    final rec = _rec;
    _rec = null;
    if (rec == null) return;
    try {
      if (await rec.isRecording()) await rec.stop();
    } catch (_) {}
    await rec.dispose();
  }
}

/// `just_audio`-backed player; plays from an in-memory data URI.
class JustAudioVoicePlayer implements VoicePlayer {
  AudioPlayer? _p;
  StreamSubscription<PlayerState>? _sub;
  final _out = StreamController<bool>.broadcast();

  AudioPlayer get _pl {
    final existing = _p;
    if (existing != null) return existing;
    final p = _p = AudioPlayer();
    _sub = p.playerStateStream.listen((st) {
      _out.add(st.playing && st.processingState != ProcessingState.completed);
    });
    return p;
  }

  @override
  Stream<bool> get playingStream => _out.stream;

  @override
  Future<void> play(Uint8List bytes, String mime) async {
    final p = _pl;
    await p.setAudioSource(AudioSource.uri(Uri.dataFromBytes(bytes,
        mimeType: mime.isEmpty ? 'audio/mpeg' : mime)));
    // play() completes when playback ends; do not block on it, but never let
    // a rejection (e.g. web autoplay policy) escape as an unhandled error.
    unawaited(p.play().catchError((Object _) {
      if (!_out.isClosed) _out.add(false);
    }));
  }

  @override
  Future<void> stop() async => _p?.stop();

  @override
  Future<void> setMuted(bool muted) async => _p?.setVolume(muted ? 0 : 1);

  @override
  Future<void> dispose() async {
    final p = _p;
    _p = null;
    await _sub?.cancel();
    await p?.dispose();
    await _out.close();
  }
}
