import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ubuzima/data/api_client.dart';
import 'package:ubuzima/data/models/token_pair.dart';
import 'package:ubuzima/data/token_store.dart';

import 'support/fakes.dart';

Map<String, Object?> pair(String a, String r) =>
    {'access_token': a, 'refresh_token': r, 'token_type': 'bearer'};

Future<(ApiClient, FakeAdapter, MemoryTokenStore)> setup(Responder r,
    {bool withTokens = true}) async {
  final store = MemoryTokenStore();
  if (withTokens) {
    await store.writeUser(const TokenPair(accessToken: 'A1', refreshToken: 'R1'));
  }
  final adapter = FakeAdapter(r);
  final dio = Dio()..httpClientAdapter = adapter;
  return (ApiClient(tokens: store, dio: dio, baseUrl: 'http://x'), adapter, store);
}

void main() {
  test('attaches bearer for auth user, none omits it', () async {
    final (c, a, _) = await setup((_) => jsonBody(200, {'ok': true}));
    await c.getJson('/v1/profile');
    await c.getJson('/v1/health', auth: AuthMode.none);
    expect(a.requests[0].headers['Authorization'], 'Bearer A1');
    expect(a.requests[1].headers.containsKey('Authorization'), isFalse);
  });

  test('error envelope becomes ApiError', () async {
    final (c, _, _) = await setup((_) => jsonBody(
        422, {'error': {'code': 'validation_error', 'message': 'bad'}}));
    expect(
        () => c.getJson('/v1/profile'),
        throwsA(isA<ApiError>()
            .having((e) => e.code, 'code', 'validation_error')
            .having((e) => e.message, 'message', 'bad')
            .having((e) => e.status, 'status', 422)));
  });

  test('401 triggers exactly one refresh then retry', () async {
    var profileCalls = 0;
    final (c, a, store) = await setup((r) {
      if (r.path == '/v1/identity/refresh') return jsonBody(200, pair('A2', 'R2'));
      profileCalls++;
      if (r.headers['Authorization'] == 'Bearer A1') {
        return jsonBody(401, {'error': {'code': 'unauthorized', 'message': 'x'}});
      }
      return jsonBody(200, {'ok': 1});
    });
    // two concurrent calls share one refresh (single-flight)
    final res = await Future.wait([c.getJson('/v1/profile'), c.getJson('/v1/profile')]);
    expect(res.first['ok'], 1);
    expect(a.requests.where((r) => r.path == '/v1/identity/refresh').length, 1);
    expect(profileCalls, 4);
    expect((await store.readUser())!.accessToken, 'A2');
    expect((await store.readUser())!.refreshToken, 'R2');
  });

  test('retried request failing 401 again does not loop', () async {
    final (c, a, _) = await setup((r) {
      if (r.path == '/v1/identity/refresh') return jsonBody(200, pair('A2', 'R2'));
      return jsonBody(401, {'error': {'code': 'unauthorized', 'message': 'x'}});
    });
    await expectLater(c.getJson('/v1/profile'),
        throwsA(isA<ApiError>().having((e) => e.status, 'status', 401)));
    expect(a.requests.length, 3);
  });

  test('transient refresh failure (5xx / offline) keeps tokens', () async {
    for (final transient in [true, false]) {
      final (c, _, store) = await setup((r) {
        if (r.path == '/v1/identity/refresh') {
          return transient
              ? jsonBody(503, {'error': {'code': 'unavailable', 'message': 'x'}})
              : offline();
        }
        return jsonBody(401, {'error': {'code': 'unauthorized', 'message': 'x'}});
      });
      await expectLater(c.getJson('/v1/profile'), throwsA(isA<ApiError>()));
      expect(await store.readUser(), isNotNull, reason: 'transient=$transient');
    }
  });

  test('definitive refresh rejection (401/403/400) clears tokens', () async {
    for (final code in [400, 401, 403]) {
      final (c, _, store) = await setup((r) =>
          jsonBody(r.path == '/v1/identity/refresh' ? code : 401,
              {'error': {'code': 'invalid_token', 'message': 'x'}}));
      var expired = 0;
      c.onAuthExpired = () => expired++;
      await expectLater(
          c.getJson('/v1/profile'),
          throwsA(isA<ApiError>()
              .having((e) => e.code, 'code', 'auth_expired')
              .having((e) => e.status, 'status', 401)));
      expect(await store.readUser(), isNull, reason: 'code=$code');
      expect(expired, 1);
    }
  });

  test('401 without a refresh token is just an error, no refresh call', () async {
    final (c, a, _) = await setup(
        (_) => jsonBody(401, {'error': {'code': 'unauthorized', 'message': 'x'}}),
        withTokens: false);
    await expectLater(c.getJson('/v1/profile'), throwsA(isA<ApiError>()));
    expect(a.requests.length, 1);
  });

  test('network failure maps to offline', () async {
    final (c, _, _) = await setup((_) => offline());
    await expectLater(
        c.getJson('/v1/profile'),
        throwsA(isA<ApiError>()
            .having((e) => e.code, 'code', 'offline')
            .having((e) => e.status, 'status', 0)));
  });

  test('non-envelope error body still yields ApiError', () async {
    final (c, _, _) =
        await setup((_) => ResponseBody.fromString('oops', 502));
    await expectLater(c.getJson('/v1/profile'),
        throwsA(isA<ApiError>().having((e) => e.status, 'status', 502)));
  });
}
