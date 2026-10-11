import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../api_client.dart';
import '../models/chat.dart';

class VoiceApi {
  VoiceApi(this._c);
  final ApiClient _c;

  MultipartFile _audio(List<int> bytes, String filename) =>
      MultipartFile.fromBytes(bytes, filename: filename);

  /// Voice turn: audio in, transcript + guarded answer + base64 audio out.
  Future<VoiceResponse> chat(List<int> audio,
      {String? conversationId,
      String? language,
      String? voice,
      String filename = 'audio.webm'}) async {
    // Builder: FormData is single-use, so a 401 retry rebuilds it.
    return VoiceResponse.fromJson(await _c.postForm(
        '/v1/voice/chat',
        () => FormData.fromMap({
              'audio': _audio(audio, filename),
              'conversation_id': ?conversationId,
              'language': ?language,
              'voice': ?voice,
            })));
  }

  Future<TranscribeResponse> transcribe(List<int> audio,
      {String? language, String filename = 'audio.webm'}) async {
    return TranscribeResponse.fromJson(await _c.postForm(
        '/v1/voice/transcribe',
        () => FormData.fromMap({
              'audio': _audio(audio, filename),
              'language': ?language,
            })));
  }

  Future<Uint8List> speak(String text,
      {required String language, String? voice}) {
    return _c.postForBytes('/v1/voice/speak', {
      'text': text,
      'language': language,
      'voice': ?voice,
    });
  }
}
