import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ubuzima/app.dart';
import 'package:ubuzima/core/i18n/i18n.dart';
import 'package:ubuzima/data/api_client.dart';
import 'package:ubuzima/data/token_store.dart';
import 'package:ubuzima/state/auth.dart';
import 'package:ubuzima/state/profile.dart';

import 'support/fakes.dart';

class Harness {
  late FakeAdapter adapter;
  late SharedPreferences prefs;
  late ProviderContainer container;
  late Widget app;

  Future<void> init({bool failPut = false}) async {
    SharedPreferences.setMockInitialValues({'lang': 'en'});
    prefs = await SharedPreferences.getInstance();
    final store = MemoryTokenStore();
    adapter = FakeAdapter((r) {
      if (r.path == '/v1/identity/anon') {
        return jsonBody(200, {
          'access_token': 'A',
          'refresh_token': 'R',
          'token_type': 'bearer',
          'anon_id': 'anon-1',
        });
      }
      if (r.path == '/v1/profile' && failPut) return offline();
      return jsonBody(200, {'age_band': 'undisclosed', 'interests': []});
    });
    container = ProviderContainer(overrides: [
      prefsProvider.overrideWithValue(prefs),
      tokenStoreProvider.overrideWithValue(store),
      apiClientProvider.overrideWithValue(ApiClient(
          tokens: store,
          dio: Dio()..httpClientAdapter = adapter,
          baseUrl: 'http://x')),
    ]);
    app = UncontrolledProviderScope(
        container: container, child: const UbuzimaApp());
  }

  List<RecordedRequest> get puts =>
      adapter.requests.where((r) => r.method == 'PUT').toList();
  Map<String, dynamic> get putBody =>
      jsonDecode(puts.single.body) as Map<String, dynamic>;
}

Future<void> tapKey(WidgetTester t, String k) async {
  await t.pump();
  final f = find.byKey(Key(k));
  await t.ensureVisible(f);
  await t.tap(f);
  await t.pumpAndSettle();
}

void main() {
  Future<Harness> boot(WidgetTester t, {bool failPut = false}) async {
    t.view.physicalSize = const Size(320, 640);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    final h = Harness();
    await h.init(failPut: failPut);
    addTearDown(h.container.dispose);
    await t.pumpWidget(h.app);
    await t.pumpAndSettle();
    return h;
  }

  testWidgets('full wizard: ensureAnon then PUT only provided fields; sets onboarded',
      (t) async {
    final h = await boot(t);
    expect(find.byKey(const Key('ob-nick')), findsOneWidget);
    await t.enterText(find.byKey(const Key('ob-nick')), ' Amina ');
    await tapKey(t, 'ob-next');
    await tapKey(t, 'ob-age-18_19');
    await tapKey(t, 'ob-pron-she/her');
    await tapKey(t, 'ob-next');
    await tapKey(t, 'ob-tone-gentle');
    await tapKey(t, 'ob-int-sleep');
    await tapKey(t, 'ob-int-stress');
    await tapKey(t, 'ob-next');
    await t.enterText(find.byKey(const Key('ob-sensitive')), 'I have asthma');
    await tapKey(t, 'ob-finish');

    // Chat welcome fetches GET /v1/profile once the shell shows; ignore it.
    final paths = h.adapter.requests.where((r) => r.method != 'GET').map((r) => '${r.method} ${r.path}').toList();
    expect(paths.first, 'POST /v1/identity/anon');
    expect(paths.last, 'PUT /v1/profile');
    expect(h.putBody, {
      'nickname': 'Amina',
      'age_band': '18_19',
      'pronouns': 'she/her',
      'tone_pref': 'gentle',
      'interests': ['sleep', 'stress'],
      'sensitive_context': 'I have asthma',
    });
    expect(h.container.read(onboardedProvider), isTrue);
    expect(h.prefs.getString('onboarded'), '1');
    expect(find.byKey(const Key('ob-nick')), findsNothing);
    expect(find.text('Chat'), findsWidgets); // app shell
  });

  testWidgets('skipping after nickname: session + minimal payload + onboarded',
      (t) async {
    final h = await boot(t);
    await t.enterText(find.byKey(const Key('ob-nick')), 'Neza');
    await tapKey(t, 'ob-next');
    await tapKey(t, 'ob-skip');
    await tapKey(t, 'ob-skip');
    await tapKey(t, 'ob-skip');
    expect(h.adapter.requests.first.path, '/v1/identity/anon');
    expect(h.putBody, {'nickname': 'Neza'});
    expect(h.container.read(onboardedProvider), isTrue);
  });

  testWidgets('Skip on sensitive step sends NO sensitive_context even if typed',
      (t) async {
    final h = await boot(t);
    await t.enterText(find.byKey(const Key('ob-nick')), 'Neza');
    await tapKey(t, 'ob-next');
    await tapKey(t, 'ob-next');
    await tapKey(t, 'ob-next');
    await t.enterText(find.byKey(const Key('ob-sensitive')), 'secret stuff');
    await tapKey(t, 'ob-skip');
    expect(h.putBody.containsKey('sensitive_context'), isFalse);
    expect(h.putBody, {'nickname': 'Neza'});
    expect(h.puts.single.body.contains('secret'), isFalse);
  });

  testWidgets('choosing rw switches the app language', (t) async {
    final h = await boot(t);
    expect(h.container.read(languageProvider), 'en');
    await tapKey(t, 'ob-lang-rw');
    expect(h.container.read(languageProvider), 'rw');
    expect(find.text('Twakwita nde?'), findsOneWidget);
  });

  testWidgets('failed save keeps the wizard and does not set onboarded',
      (t) async {
    final h = await boot(t, failPut: true);
    await t.enterText(find.byKey(const Key('ob-nick')), 'Neza');
    await tapKey(t, 'ob-next');
    await tapKey(t, 'ob-skip');
    await tapKey(t, 'ob-skip');
    await tapKey(t, 'ob-skip');
    expect(h.container.read(onboardedProvider), isFalse);
    expect(find.byKey(const Key('ob-error')), findsOneWidget);
  });

  testWidgets('returning user goes straight to the shell; reset re-runs wizard',
      (t) async {
    t.view.physicalSize = const Size(320, 640);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.resetPhysicalSize);
    final h = Harness();
    await h.init();
    await h.prefs.setString('onboarded', '1');
    addTearDown(h.container.dispose);
    await t.pumpWidget(h.app);
    await t.pumpAndSettle();
    expect(find.byKey(const Key('ob-nick')), findsNothing);
    expect(h.adapter.requests.where((r) => r.method != 'GET'), isEmpty);
    await h.container.read(onboardedProvider.notifier).reset();
    await t.pumpAndSettle();
    expect(find.byKey(const Key('ob-nick')), findsOneWidget);
  });
}
