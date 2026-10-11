import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ubuzima/data/api_client.dart';
import 'package:ubuzima/data/endpoints/chat.dart';
import 'package:ubuzima/data/endpoints/profile.dart';
import 'package:ubuzima/data/endpoints/voice.dart';
import 'package:ubuzima/data/models/models.dart';
import 'package:ubuzima/data/token_store.dart';

import 'support/fakes.dart';

const chatJson = {
  'answer': 'Muraho',
  'citations': [
    {'id': 'S1', 'document_id': 'd', 'title': 'T', 'page': 2, 'score': 0.5}
  ],
  'conversation_id': 'c1',
  'safety_flags': {
    'crisis': false,
    'needs_referral': true,
    'in_knowledge': null,
    'guard_reason': 'out_of_scope',
    'category': 'x',
    'flags': ['a']
  },
  'language': 'rw',
};

ApiClient client(FakeAdapter a) => ApiClient(
    tokens: MemoryTokenStore(),
    dio: Dio()..httpClientAdapter = a,
    baseUrl: 'http://x');

void main() {
  test('ChatResponse + SafetyFlags parse', () {
    final r = ChatResponse.fromJson(chatJson);
    expect(r.conversationId, 'c1');
    expect(r.safetyFlags.needsReferral, isTrue);
    expect(r.safetyFlags.guardReason, 'out_of_scope');
    expect(r.safetyFlags.inKnowledge, isNull);
    expect(r.citations.single.title, 'T');
  });

  test('Profile parse + ProfileUpdate omits unset fields', () {
    final p = Profile.fromJson({
      'nickname': 'N', 'age_band': '15_17', 'gender': null, 'pronouns': null,
      'tone_pref': null, 'interests': ['a'], 'consent': {}, 'updated_at': null,
    });
    expect(p.ageBand, '15_17');
    expect(const ProfileUpdate(nickname: 'Z').toJson(), {'nickname': 'Z'});
    // untouched fields absent; explicitly cleared fields are JSON null
    final j = const ProfileUpdate(
        gender: 'f', clear: {ProfileField.sensitiveContext, ProfileField.nickname}).toJson();
    expect(j, {'gender': 'f', 'sensitive_context': null, 'nickname': null});
    expect(j.containsKey('pronouns'), isFalse);
    expect(const ProfileUpdate().toJson(), isEmpty);
  });

  test('VoiceResponse parse', () {
    final v = VoiceResponse.fromJson({
      ...chatJson, 'transcript': 't', 'audio_base64': 'QQ==', 'audio_mime': 'audio/mpeg',
    });
    expect(v.ttsAvailable, isTrue);
    expect(v.audioBase64, 'QQ==');
  });

  test('streamChat yields tokens then final response', () async {
    final a = FakeAdapter((r) => ResponseBody(
          Stream.fromIterable(<Uint8List>[
            Uint8List.fromList(utf8.encode('event: delta\ndata: Mur\n\nevent: delta\nda')),
            Uint8List.fromList(utf8.encode('ta: aho\n\nevent: done\ndata: ${jsonEncode(chatJson)}\n\n')),
          ]),
          200,
          headers: {Headers.contentTypeHeader: ['text/event-stream']},
        ));
    final ev = await ChatApi(client(a)).streamChat(const ChatRequest(message: 'hi')).toList();
    expect(ev.whereType<ChatToken>().map((e) => e.text).join(), 'Muraho');
    expect(ev.last, isA<ChatDone>());
    expect((ev.last as ChatDone).response.answer, 'Muraho');
    expect(jsonDecode(a.requests.single.body)['message'], 'hi');
  });

  test('streamChat HTTP error surfaces ApiError', () async {
    final a = FakeAdapter((r) => jsonBody(429, {'error': {'code': 'rate_limited', 'message': 'm'}}));
    await expectLater(ChatApi(client(a)).streamChat(const ChatRequest(message: 'x')).toList(),
        throwsA(isA<ApiError>().having((e) => e.code, 'code', 'rate_limited')));
  });

  test('profile get/put/wipe hit right routes', () async {
    final a = FakeAdapter((r) => r.method == 'DELETE'
        ? ResponseBody.fromString('', 204)
        : jsonBody(200, {
            'nickname': null, 'age_band': 'undisclosed', 'gender': null, 'pronouns': null,
            'tone_pref': null, 'interests': [], 'consent': {}, 'updated_at': null,
          }));
    final p = ProfileApi(client(a));
    await p.get();
    await p.put(const ProfileUpdate(nickname: 'x'));
    await p.wipe();
    expect(a.requests.map((r) => '${r.method} ${r.path}'),
        ['GET /v1/profile', 'PUT /v1/profile', 'DELETE /v1/profile']);
  });

  test('voice.chat sends multipart and retries safely; speak returns bytes', () async {
    final a = FakeAdapter((r) => r.path == '/v1/voice/speak'
        ? ResponseBody.fromBytes([1, 2, 3], 200, headers: {Headers.contentTypeHeader: ['audio/mpeg']})
        : jsonBody(200, {...chatJson, 'transcript': 't', 'audio_base64': '', 'audio_mime': 'audio/mpeg'}));
    final v = VoiceApi(client(a));
    final r = await v.chat([1, 2], conversationId: 'c', language: 'rw');
    expect(r.transcript, 't');
    expect(a.requests.single.body, contains('name="conversation_id"'));
    expect(await v.speak('hi', language: 'en'), [1, 2, 3]);
  });
}
