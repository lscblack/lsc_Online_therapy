import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ubuzima/app.dart';
import 'package:ubuzima/core/i18n/i18n.dart';
import 'package:ubuzima/data/api_client.dart';
import 'package:ubuzima/data/models/token_pair.dart';
import 'package:ubuzima/data/token_store.dart';
import 'package:ubuzima/data/endpoints/chat.dart';
import 'package:ubuzima/data/models/chat.dart';
import 'package:ubuzima/state/auth.dart';
import 'package:ubuzima/state/chat.dart';
import 'package:ubuzima/features/settings/settings_actions.dart';
import 'package:ubuzima/state/profile.dart';

import 'support/fakes.dart';

class LoggingStore extends MemoryTokenStore {
  LoggingStore(this.log);
  final List<String> log;
  @override
  Future<void> clearUser() {
    log.add('clearUser');
    return super.clearUser();
  }

  @override
  Future<void> clearAnonId() {
    log.add('clearAnonId');
    return super.clearAnonId();
  }
}

class _FakeChat implements ChatApi {
  final reqs = <ChatRequest>[];
  @override
  Stream<ChatStreamEvent> streamChat(
    ChatRequest req, {
    CancelToken? cancelToken,
  }) async* {
    reqs.add(req);
    const r = ChatResponse(
      answer: 'ok',
      citations: [],
      conversationId: 'old-conv',
      safetyFlags: SafetyFlags(),
      language: 'en',
    );
    yield ChatToken('ok');
    yield const ChatDone(r);
  }

  @override
  Future<ChatResponse> send(ChatRequest req) async =>
      throw UnimplementedError();
}

class Env {
  final log = <String>[];
  late FakeAdapter adapter;
  late SharedPreferences prefs;
  late ProviderContainer container;
  late LoggingStore store;
  late Widget app;
  bool failDelete = false;

  Future<void> init() async {
    SharedPreferences.setMockInitialValues({'lang': 'en', 'onboarded': '1'});
    prefs = await SharedPreferences.getInstance();
    store = LoggingStore(log);
    await store.writeUser(
      const TokenPair(accessToken: 'OLD', refreshToken: 'OLDR'),
    );
    await store.writeAnonId('old-anon');
    adapter = FakeAdapter((r) {
      log.add('${r.method} ${r.path}');
      if (r.path == '/v1/identity/anon') {
        return jsonBody(200, {
          'access_token': 'NEW',
          'refresh_token': 'NEWR',
          'token_type': 'bearer',
          'anon_id': 'new-anon',
        });
      }
      if (r.method == 'DELETE') {
        if (failDelete) return offline();
        return ResponseBody.fromString('', 204);
      }
      return jsonBody(200, {
        'nickname': 'Amina',
        'age_band': '18_19',
        'gender': 'female',
        'tone_pref': 'gentle',
        'interests': ['sleep'],
        'sensitive_context': 'asthma',
      });
    });
    container = ProviderContainer(
      overrides: [
        prefsProvider.overrideWithValue(prefs),
        tokenStoreProvider.overrideWithValue(store),
        apiClientProvider.overrideWithValue(
          ApiClient(
            tokens: store,
            dio: Dio()..httpClientAdapter = adapter,
            baseUrl: 'http://x',
          ),
        ),
      ],
    );
    app = UncontrolledProviderScope(
      container: container,
      child: const UbuzimaApp(),
    );
  }

  List<RecordedRequest> get puts =>
      adapter.requests.where((r) => r.method == 'PUT').toList();
}

Future<void> tapK(WidgetTester t, String k) async {
  final f = find.byKey(Key(k));
  await t.pumpAndSettle();
  await t.ensureVisible(f);
  await t.pumpAndSettle();
  await t.tap(f);
  await t.pumpAndSettle();
}

void main() {
  Future<Env> boot(WidgetTester t) async {
    t.view.physicalSize = const Size(400, 900);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    final e = Env();
    await e.init();
    addTearDown(e.container.dispose);
    await t.pumpWidget(e.app);
    await t.pumpAndSettle();
    await t.tap(find.byIcon(Icons.settings_outlined));
    await t.pumpAndSettle();
    return e;
  }

  testWidgets('edit profile loads current values', (t) async {
    await boot(t);
    final nick = t.widget<TextField>(find.byKey(const Key('set-nick')));
    expect(nick.controller!.text, 'Amina');
    final sens = t.widget<TextField>(find.byKey(const Key('set-sens')));
    expect(sens.controller!.text, 'asthma');
    expect(
      t.widget<ChoiceChip>(find.byKey(const Key('set-age-18_19'))).selected,
      isTrue,
    );
    expect(
      t.widget<FilterChip>(find.byKey(const Key('set-int-sleep'))).selected,
      isTrue,
    );
  });

  testWidgets('saving a changed field sends only that field', (t) async {
    final e = await boot(t);
    await t.enterText(find.byKey(const Key('set-nick')), 'Neza');
    await tapK(t, 'set-save');
    expect(e.puts, hasLength(1));
    expect(jsonDecode(e.puts.single.body), {'nickname': 'Neza'});
    expect(find.byKey(const Key('set-saved')), findsOneWidget);
  });

  testWidgets('saving with no changes sends nothing', (t) async {
    final e = await boot(t);
    await tapK(t, 'set-save');
    expect(e.puts, isEmpty);
  });

  testWidgets('clearing fields (incl. sensitive_context) sends explicit null', (
    t,
  ) async {
    final e = await boot(t);
    await t.enterText(find.byKey(const Key('set-nick')), '   ');
    await t.enterText(find.byKey(const Key('set-sens')), '');
    await tapK(t, 'set-gender-female'); // deselect
    await tapK(t, 'set-save');
    expect(jsonDecode(e.puts.single.body), {
      'nickname': null,
      'gender': null,
      'sensitive_context': null,
    });
  });

  testWidgets('interests and age band changes are sent', (t) async {
    final e = await boot(t);
    await tapK(t, 'set-int-stress');
    await tapK(t, 'set-age-20_24');
    await tapK(t, 'set-save');
    expect(jsonDecode(e.puts.single.body), {
      'age_band': '20_24',
      'interests': ['sleep', 'stress'],
    });
  });

  testWidgets('re-run onboarding resets the flag and shows the wizard', (
    t,
  ) async {
    final e = await boot(t);
    await tapK(t, 'set-rerun');
    expect(e.container.read(onboardedProvider), isFalse);
    expect(e.prefs.getString('onboarded'), '0');
    expect(find.byKey(const Key('ob-nick')), findsOneWidget);
  });

  testWidgets('wipe: cancel does nothing', (t) async {
    final e = await boot(t);
    await tapK(t, 'set-wipe');
    expect(find.byKey(const Key('wipe-confirm')), findsOneWidget);
    await tapK(t, 'wipe-cancel');
    expect(e.log.where((l) => l.startsWith('DELETE')), isEmpty);
    expect(await e.store.readAnonId(), 'old-anon');
  });

  testWidgets(
    'wipe: DELETE, then clear token+anon_id, reset onboarded, re-bootstrap',
    (t) async {
      final e = await boot(t);
      e.log.clear();
      await tapK(t, 'set-wipe');
      await tapK(t, 'wipe-confirm');
      final ops = e.log.where((l) => !l.startsWith('GET')).toList();
      expect(ops, [
        'DELETE /v1/profile',
        'clearUser',
        'clearAnonId',
        'POST /v1/identity/anon',
      ]);
      expect(e.container.read(onboardedProvider), isFalse);
      expect(e.prefs.getString('onboarded'), '0');
      expect((await e.store.readUser())!.accessToken, 'NEW');
      expect(await e.store.readAnonId(), 'new-anon');
      expect(find.byKey(const Key('ob-nick')), findsOneWidget);
    },
  );

  testWidgets('wipe failure keeps everything and shows a calm error', (
    t,
  ) async {
    final e = await boot(t);
    e.failDelete = true;
    await tapK(t, 'set-wipe');
    await tapK(t, 'wipe-confirm');
    expect(e.container.read(onboardedProvider), isTrue);
    expect(await e.store.readAnonId(), 'old-anon');
    expect(find.byKey(const Key('set-wipe-error')), findsOneWidget);
  });

  test('wipe resets chat state and conversation id', () async {
    final e = Env();
    await e.init();
    final fake = _FakeChat();
    final c = ProviderContainer(
      overrides: [
        prefsProvider.overrideWithValue(e.prefs),
        tokenStoreProvider.overrideWithValue(e.store),
        apiClientProvider.overrideWithValue(
          ApiClient(
            tokens: e.store,
            dio: Dio()..httpClientAdapter = e.adapter,
            baseUrl: 'http://x',
          ),
        ),
        chatApiProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(c.dispose);
    await c.read(chatProvider.notifier).send('hello');
    expect(c.read(chatProvider).messages, isNotEmpty);
    expect(c.read(chatProvider).conversationId, 'old-conv');

    await c.read(settingsActionsProvider).wipeMyData();

    expect(c.read(chatProvider).messages, isEmpty);
    expect(c.read(chatProvider).conversationId, isNull);
    await c.read(chatProvider.notifier).send('hi again');
    expect(fake.reqs.last.conversationId, isNull);
  });

  testWidgets('nav reaches Chat, Voice and Settings', (t) async {
    t.view.physicalSize = const Size(400, 900);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    final e = Env();
    await e.init();
    addTearDown(e.container.dispose);
    await t.pumpWidget(e.app);
    await t.pumpAndSettle();
    expect(find.byType(NavigationDestination), findsNWidgets(3));
    await t.tap(
      find.descendant(
        of: find.byType(NavigationBar),
        matching: find.byIcon(Icons.mic_none),
      ),
    );
    await t.pumpAndSettle();
    expect(find.text('Talk to Ubuzima'), findsOneWidget);
    await t.tap(find.byIcon(Icons.settings_outlined));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('set-wipe')), findsOneWidget);
    await t.tap(find.byIcon(Icons.chat_bubble_outline));
    await t.pumpAndSettle();
    expect(find.byKey(const Key('voice-button')), findsOneWidget);
  });

  testWidgets(
    'Kinyarwanda locale builds without Material localization errors',
    (t) async {
      final e = Env();
      await e.init();
      await e.prefs.setString('lang', 'rw');
      final c = ProviderContainer(
        overrides: [
          prefsProvider.overrideWithValue(e.prefs),
          tokenStoreProvider.overrideWithValue(e.store),
          apiClientProvider.overrideWithValue(
            ApiClient(
              tokens: e.store,
              dio: Dio()..httpClientAdapter = e.adapter,
              baseUrl: 'http://x',
            ),
          ),
        ],
      );
      addTearDown(c.dispose);
      await t.pumpWidget(
        UncontrolledProviderScope(container: c, child: const UbuzimaApp()),
      );
      await t.pumpAndSettle();
      expect(t.takeException(), isNull);
      expect(find.text('Ibiganiro'), findsWidgets);
    },
  );
}
