import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ubuzima/core/i18n/i18n.dart';
import 'package:ubuzima/core/theme.dart';
import 'package:ubuzima/data/endpoints/voice.dart';
import 'package:ubuzima/data/models/chat.dart';
import 'package:ubuzima/features/voice/voice_io.dart';
import 'package:ubuzima/features/voice/voice_panel.dart';
import 'package:ubuzima/state/auth.dart';
import 'package:ubuzima/state/chat.dart';
import 'package:ubuzima/state/voice.dart';

class FakeRecorder implements VoiceRecorder {
  bool permission = true;
  bool throwOnStart = false;
  final calls = <String>[];
  @override
  Future<bool> ensurePermission() async {
    calls.add('perm');
    return permission;
  }

  @override
  Future<void> start() async {
    calls.add('start');
    if (throwOnStart) throw StateError('no mic');
  }

  @override
  Future<RecordedAudio?> stop() async {
    calls.add('stop');
    return RecordedAudio(Uint8List.fromList([1, 2, 3]), 'audio.webm');
  }

  @override
  Future<void> dispose() async => calls.add('dispose');
}

class FakePlayer implements VoicePlayer {
  final calls = <String>[];
  bool throwOnPlay = false;
  final ctrl = StreamController<bool>.broadcast();
  @override
  Stream<bool> get playingStream => ctrl.stream;
  Uint8List? played;
  @override
  Future<void> play(Uint8List bytes, String mime) async {
    calls.add('play');
    if (throwOnPlay) throw StateError('autoplay blocked');
    played = bytes;
  }

  @override
  Future<void> stop() async => calls.add('stop');
  @override
  Future<void> setMuted(bool m) async => calls.add('mute:$m');
  @override
  Future<void> dispose() async => calls.add('dispose');
}

class FakeVoiceApi implements VoiceApi {
  FakeVoiceApi(this.response);
  bool fail = false;
  VoiceResponse response;
  List<int>? bytes;
  String? cid;
  String? lang;
  @override
  Future<VoiceResponse> chat(List<int> audio,
      {String? conversationId,
      String? language,
      String? voice,
      String filename = 'audio.webm'}) async {
    if (fail) throw StateError('boom');
    bytes = audio;
    cid = conversationId;
    lang = language;
    return response;
  }

  @override
  dynamic noSuchMethod(Invocation i) => throw UnimplementedError();
}

VoiceResponse vr({
  String answer = 'Drink water.',
  bool tts = true,
  SafetyFlags flags = const SafetyFlags(),
}) =>
    VoiceResponse(
      transcript: 'I have a headache',
      answer: answer,
      citations: const [],
      safetyFlags: flags,
      conversationId: 'c9',
      language: 'en',
      audioBase64: tts ? base64Encode([9, 8, 7]) : '',
      audioMime: tts ? 'audio/mpeg' : '',
      ttsAvailable: tts,
    );

Future<(FakeRecorder, FakePlayer, FakeVoiceApi)> pumpVoice(
    WidgetTester t, VoiceResponse r,
    {FakeRecorder? rec, String? chatCid}) async {
  SharedPreferences.setMockInitialValues({'lang': 'en'});
  final prefs = await SharedPreferences.getInstance();
  final recorder = rec ?? FakeRecorder();
  final player = FakePlayer();
  final api = FakeVoiceApi(r);
  await t.pumpWidget(ProviderScope(
    overrides: [
      prefsProvider.overrideWithValue(prefs),
      voiceRecorderProvider.overrideWithValue(recorder),
      voicePlayerProvider.overrideWithValue(player),
      voiceApiProvider.overrideWithValue(api),
      if (chatCid != null)
        chatProvider.overrideWith(() => _SeededChat(chatCid)),
    ],
    child: MaterialApp(
        theme: lightTheme, home: const Scaffold(body: VoicePanel())),
  ));
  await t.pump();
  return (recorder, player, api);
}

class _SeededChat extends ChatController {
  _SeededChat(this.cid);
  final String cid;
  @override
  ChatState build() => ChatState(conversationId: cid);
}

Future<void> recordAndStop(WidgetTester t) async {
  await t.tap(find.byKey(const Key('record-button')));
  await t.pump();
  await t.pump(const Duration(seconds: 2));
  await t.tap(find.byKey(const Key('record-button')));
  await t.pump();
  await t.pump();
}

void main() {
  testWidgets('record then stop posts bytes and renders transcript + answer',
      (t) async {
    final (rec, player, api) = await pumpVoice(t, vr(), chatCid: 'c1');
    await t.tap(find.byKey(const Key('record-button')));
    await t.pump();
    expect(find.byKey(const Key('voice-elapsed')), findsOneWidget);
    await t.pump(const Duration(seconds: 2));
    await t.tap(find.byKey(const Key('record-button')));
    await t.pump();
    await t.pump();
    expect(api.bytes, [1, 2, 3]);
    expect(api.cid, 'c1');
    expect(api.lang, 'en');
    expect(find.text('I have a headache'), findsOneWidget);
    expect(find.byKey(const Key('user-bubble')), findsOneWidget);
    expect(find.text('Drink water.'), findsOneWidget);
    expect(find.byKey(const Key('assistant-bubble')), findsOneWidget);
    expect(rec.calls, containsAllInOrder(['perm', 'start', 'stop']));
    expect(player.calls, contains('play'));
    expect(player.played, [9, 8, 7]);
    expect(find.byKey(const Key('voice-replay')), findsOneWidget);
    expect(find.byKey(const Key('voice-mute')), findsOneWidget);
    expect(find.byKey(const Key('voice-live-soon')), findsOneWidget);
  });

  testWidgets('tts unavailable: no playback, text still shows', (t) async {
    final (_, player, _) = await pumpVoice(t, vr(tts: false));
    await recordAndStop(t);
    expect(player.calls, isNot(contains('play')));
    expect(find.text('Drink water.'), findsOneWidget);
    expect(find.byKey(const Key('voice-replay')), findsNothing);
    expect(find.byKey(const Key('chat-error')), findsNothing);
  });

  testWidgets('crisis flag renders calm crisis panel, not an error', (t) async {
    await pumpVoice(t, vr(flags: const SafetyFlags(crisis: true)));
    await recordAndStop(t);
    expect(find.byKey(const Key('crisis-panel')), findsOneWidget);
    expect(find.byKey(const Key('chat-error')), findsNothing);
    expect(find.byKey(const Key('voice-error')), findsNothing);
  });

  testWidgets('mic denied shows friendly message, no crash', (t) async {
    final rec = FakeRecorder()..permission = false;
    await pumpVoice(t, vr(), rec: rec);
    await t.tap(find.byKey(const Key('record-button')));
    await t.pump();
    await t.pump();
    expect(find.byKey(const Key('voice-denied')), findsOneWidget);
    expect(rec.calls, isNot(contains('start')));
    expect(t.takeException(), isNull);
  });

  testWidgets('recorder start failure is friendly, no crash', (t) async {
    final rec = FakeRecorder()..throwOnStart = true;
    await pumpVoice(t, vr(), rec: rec);
    await t.tap(find.byKey(const Key('record-button')));
    await t.pump();
    await t.pump();
    expect(find.byKey(const Key('voice-unavailable')), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('starting a new recording stops playing reply', (t) async {
    final (rec, player, _) = await pumpVoice(t, vr());
    await recordAndStop(t);
    player.calls.clear();
    rec.calls.clear();
    await t.tap(find.byKey(const Key('record-button')));
    await t.pump();
    await t.pump();
    expect(player.calls, contains('stop'));
    expect(rec.calls.last, 'start');
    await t.tap(find.byKey(const Key('record-button')));
    await t.pump();
    await t.pump();
  });

  testWidgets('mute toggles player', (t) async {
    final (_, player, _) = await pumpVoice(t, vr());
    await recordAndStop(t);
    await t.tap(find.byKey(const Key('voice-mute')));
    await t.pump();
    expect(player.calls, contains('mute:true'));
  });

  testWidgets('recorder and player released on dispose (even mid-recording)',
      (t) async {
    final (rec, player, _) = await pumpVoice(t, vr());
    await t.tap(find.byKey(const Key('record-button')));
    await t.pump();
    await t.pumpWidget(const SizedBox());
    await t.pump();
    expect(rec.calls, contains('stop'));
    expect(rec.calls, contains('dispose'));
    expect(player.calls, contains('dispose'));
  });

  testWidgets('playing resets when audio completes; replay is one tap',
      (t) async {
    final (_, player, _) = await pumpVoice(t, vr());
    await recordAndStop(t);
    expect(find.text('Stop playing'), findsOneWidget);
    player.ctrl.add(false);
    await t.pump();
    await t.pump();
    expect(find.text('Play again'), findsOneWidget);
    player.calls.clear();
    await t.tap(find.byKey(const Key('voice-replay')));
    await t.pump();
    expect(player.calls, contains('play'));
  });

  testWidgets('play() failure leaves playing=false, text stays, no throw',
      (t) async {
    final (_, player, _) = await pumpVoice(t, vr());
    player.throwOnPlay = true;
    await recordAndStop(t);
    expect(find.text('Play again'), findsOneWidget);
    expect(find.text('Drink water.'), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('rapid double start creates one recording and one ticker',
      (t) async {
    final (rec, _, _) = await pumpVoice(t, vr());
    final c = ProviderScope.containerOf(t.element(find.byType(VoicePanel)));
    final n = c.read(voiceControllerProvider.notifier);
    unawaited(n.start());
    unawaited(n.start());
    await t.pump();
    await t.pump();
    expect(rec.calls.where((e) => e == 'start').length, 1);
    await t.pump(const Duration(seconds: 3));
    expect(c.read(voiceControllerProvider).elapsed, const Duration(seconds: 3));
    await t.pumpWidget(const SizedBox());
    await t.pump(const Duration(seconds: 3));
    expect(t.takeException(), isNull);
  });

  testWidgets('voice.chat failure shows error, hides stale turn, chat usable',
      (t) async {
    final (_, _, api) = await pumpVoice(t, vr());
    await recordAndStop(t);
    expect(find.text('Drink water.'), findsOneWidget);
    api.fail = true;
    await recordAndStop(t);
    expect(find.byKey(const Key('voice-error')), findsOneWidget);
    expect(find.text('Drink water.'), findsNothing);
    expect(find.byKey(const Key('record-button')), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('empty transcript renders no user bubble', (t) async {
    await pumpVoice(
        t,
        VoiceResponse(
            transcript: '',
            answer: 'Hello.',
            citations: const [],
            safetyFlags: const SafetyFlags(),
            conversationId: 'c',
            language: 'en',
            audioBase64: '',
            audioMime: '',
            ttsAvailable: false));
    await recordAndStop(t);
    expect(find.byKey(const Key('user-bubble')), findsNothing);
    expect(find.text('Hello.'), findsOneWidget);
  });
}
