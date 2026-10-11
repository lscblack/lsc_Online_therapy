import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ubuzima/core/i18n/i18n.dart';
import 'package:ubuzima/core/theme.dart';
import 'package:ubuzima/data/api_client.dart';
import 'package:ubuzima/data/endpoints/chat.dart';
import 'package:ubuzima/data/models/chat.dart';
import 'package:ubuzima/features/chat/chat_screen.dart';
import 'package:ubuzima/state/auth.dart';

ChatResponse resp(String a,
        {String cid = 'c1',
        List<Citation> cites = const [],
        SafetyFlags flags = const SafetyFlags()}) =>
    ChatResponse(
        answer: a,
        citations: cites,
        conversationId: cid,
        safetyFlags: flags,
        language: 'en');

class FakeChat implements ChatApi {
  FakeChat(this.handler);
  Stream<ChatStreamEvent> Function(ChatRequest) handler;
  final List<ChatRequest> reqs = [];
  @override
  Stream<ChatStreamEvent> streamChat(ChatRequest req, {CancelToken? cancelToken}) {
    reqs.add(req);
    return handler(req);
  }

  @override
  Future<ChatResponse> send(ChatRequest req) async => throw UnimplementedError();
}

Stream<ChatStreamEvent> ok(ChatResponse r) async* {
  yield ChatToken(r.answer);
  yield ChatDone(r);
}

Future<FakeChat> pumpChat(WidgetTester t, FakeChat fake) async {
  SharedPreferences.setMockInitialValues({'lang': 'en'});
  final prefs = await SharedPreferences.getInstance();
  await t.pumpWidget(ProviderScope(
    overrides: [
      prefsProvider.overrideWithValue(prefs),
      chatApiProvider.overrideWithValue(fake),
      chatNicknameProvider.overrideWith((ref) async => 'Amani'),
    ],
    child: MaterialApp(theme: lightTheme, home: const Scaffold(body: ChatScreen())),
  ));
  await t.pump();
  return fake;
}

Future<void> say(WidgetTester t, String s) async {
  await t.enterText(find.byKey(const Key('composer-field')), s);
  await t.tap(find.byKey(const Key('send-button')));
  await t.pump();
}

void main() {
  testWidgets('welcome uses nickname', (t) async {
    await pumpChat(t, FakeChat((_) => const Stream.empty()));
    await t.pump();
    expect(find.textContaining('Amani'), findsOneWidget);
  });

  testWidgets('streams tokens into bubble with typing indicator', (t) async {
    final c = StreamController<ChatStreamEvent>();
    await pumpChat(t, FakeChat((_) => c.stream));
    await say(t, 'hi');
    expect(find.byKey(const Key('typing-indicator')), findsOneWidget);
    c.add(const ChatToken('Hel'));
    await t.pump();
    c.add(const ChatToken('lo there'));
    await t.pump();
    expect(find.text('Hello there'), findsOneWidget);
    expect(find.byKey(const Key('typing-indicator')), findsOneWidget);
    // composer disabled while streaming
    expect(t.widget<IconButton>(find.byKey(const Key('send-button'))).onPressed, isNull);
    c.add(ChatDone(resp('Hello there!')));
    await c.close();
    await t.pump(const Duration(milliseconds: 400));
    expect(find.text('Hello there!'), findsOneWidget);
    expect(find.byKey(const Key('typing-indicator')), findsNothing);
    expect(t.widget<IconButton>(find.byKey(const Key('send-button'))).onPressed, isNotNull);
  });

  testWidgets('citations render chips', (t) async {
    await pumpChat(
        t,
        FakeChat((_) => ok(resp('Answer', cites: const [
              Citation(id: 'a', title: 'WHO Guide', page: 3),
              Citation(id: 'b', title: 'MoH'),
            ]))));
    await say(t, 'q');
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byKey(const Key('citation-chip-0')), findsOneWidget);
    expect(find.byKey(const Key('citation-chip-1')), findsOneWidget);
    expect(find.text('WHO Guide, p.3'), findsOneWidget);
  });

  testWidgets('crisis renders calm panel, not error style', (t) async {
    await pumpChat(
        t,
        FakeChat((_) => ok(resp('I hear you.',
            flags: const SafetyFlags(crisis: true, needsReferral: true)))));
    await say(t, 'q');
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byKey(const Key('crisis-panel')), findsOneWidget);
    expect(find.byType(CrisisPanel), findsOneWidget);
    expect(find.byKey(const Key('chat-error')), findsNothing);
    expect(find.byType(ChatErrorCard), findsNothing);
    final cs = lightTheme.colorScheme;
    final box = t.widget<Container>(find
        .descendant(
            of: find.byKey(const Key('crisis-panel')),
            matching: find.byType(Container))
        .first);
    final color = (box.decoration as BoxDecoration).color;
    expect(color, isNot(cs.error));
    expect(color, isNot(cs.errorContainer));
    expect(find.byIcon(Icons.error_outline), findsNothing);
    expect(find.byIcon(Icons.warning_amber_rounded), findsNothing);
  });

  testWidgets('out-of-knowledge and needsReferral render calm referral', (t) async {
    for (final f in const [
      SafetyFlags(inKnowledge: false),
      SafetyFlags(needsReferral: true),
    ]) {
      await pumpChat(t, FakeChat((_) => ok(resp('Not sure.', flags: f))));
      await say(t, 'q');
      await t.pump(const Duration(milliseconds: 400));
      expect(find.byKey(const Key('referral-callout')), findsOneWidget);
      expect(find.byKey(const Key('crisis-panel')), findsNothing);
      expect(find.byKey(const Key('chat-error')), findsNothing);
      await t.pumpWidget(const SizedBox());
    }
  });

  testWidgets('conversationId from first response is sent on second', (t) async {
    final fake = await pumpChat(t, FakeChat((r) => ok(resp('a', cid: 'conv-9'))));
    await say(t, 'one');
    await t.pump(const Duration(milliseconds: 400));
    await say(t, 'two');
    await t.pump(const Duration(milliseconds: 400));
    expect(fake.reqs[0].conversationId, isNull);
    expect(fake.reqs[1].conversationId, 'conv-9');
    expect(fake.reqs[1].language, 'en');
  });

  testWidgets('stream error shows friendly retry; retry recovers', (t) async {
    var fail = true;
    final fake = await pumpChat(t, FakeChat((_) {
      if (fail) {
        return Stream.error(const ApiError('offline', 'offline', 0));
      }
      return ok(resp('Back again'));
    }));
    await say(t, 'q');
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byKey(const Key('chat-error')), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
    expect(t.takeException(), isNull);
    fail = false;
    await t.tap(find.byKey(const Key('retry-button')));
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(find.text('Back again'), findsOneWidget);
    expect(find.byKey(const Key('chat-error')), findsNothing);
    expect(fake.reqs.length, 2);
    expect(fake.reqs[1].message, 'q');
    expect(find.byKey(const Key('user-bubble')), findsOneWidget);
  });

  testWidgets('mid-stream error after tokens is handled', (t) async {
    await pumpChat(t, FakeChat((_) async* {
      yield const ChatToken('part');
      throw const ApiError('stream', 'boom', 500);
    }));
    await say(t, 'q');
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byKey(const Key('chat-error')), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('falls back to send when streaming unavailable (404)', (t) async {
    final fake = FakeChat((_) => Stream.error(const ApiError('not_found', 'x', 404)));
    final f2 = _SendFallback(fake);
    await pumpChat(t, f2);
    await say(t, 'q');
    await t.pump(const Duration(milliseconds: 400));
    expect(find.text('fallback'), findsOneWidget);
  });
}

class _SendFallback extends FakeChat {
  _SendFallback(FakeChat o) : super(o.handler);
  @override
  Future<ChatResponse> send(ChatRequest req) async => resp('fallback');
}
