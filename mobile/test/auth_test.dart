import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ubuzima/data/api_client.dart';
import 'package:ubuzima/data/token_store.dart';
import 'package:ubuzima/state/auth.dart';

import 'support/fakes.dart';

void main() {
  test('ensureAnon stores tokens + anon_id and is single-flight', () async {
    final store = MemoryTokenStore();
    final adapter = FakeAdapter((r) => jsonBody(200, {
          'access_token': 'A',
          'refresh_token': 'R',
          'token_type': 'bearer',
          'anon_id': 'anon-9',
        }));
    final c = ProviderContainer(overrides: [
      tokenStoreProvider.overrideWithValue(store),
      apiClientProvider.overrideWithValue(ApiClient(
          tokens: store,
          dio: Dio()..httpClientAdapter = adapter,
          baseUrl: 'http://x')),
    ]);
    addTearDown(c.dispose);
    final n = c.read(authProvider.notifier);
    expect(c.read(authProvider).ready, isFalse);
    await Future.wait([n.ensureAnon(), n.ensureAnon(), n.ensureAnon()]);
    expect(adapter.requests.where((r) => r.path == '/v1/identity/anon').length, 1);
    expect((await store.readUser())!.accessToken, 'A');
    expect(await store.readAnonId(), 'anon-9');
    expect(c.read(authProvider).ready, isTrue);
    expect(c.read(authProvider).anonId, 'anon-9');
    await n.ensureAnon(); // already have tokens: no new call
    expect(adapter.requests.length, 1);
  });
}
