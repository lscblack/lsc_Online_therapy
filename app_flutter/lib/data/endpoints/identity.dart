import '../api_client.dart';
import '../models/token_pair.dart';
import '../token_store.dart';

class IdentityApi {
  IdentityApi(this._c, this._tokens);
  final ApiClient _c;
  final TokenStore _tokens;

  AnonSession _session(Map<String, Object?> j) {
    final t = TokenPair.tryParse(j);
    final id = j['anon_id'];
    if (t == null || id is! String) {
      throw const ApiError('bad_response', 'Malformed session response', 200);
    }
    return AnonSession(tokens: t, anonId: id);
  }

  Future<AnonSession> _store(AnonSession s) async {
    await _tokens.writeUser(s.tokens);
    await _tokens.writeAnonId(s.anonId);
    return s;
  }

  /// Creates an anonymous identity and stores tokens + anon_id.
  Future<AnonSession> anon() async => _store(_session(
      await _c.postJson('/v1/identity/anon', auth: AuthMode.none)));

  Future<bool> upgrade(String passphrase) async {
    final j = await _c.postJson('/v1/identity/upgrade', body: {'passphrase': passphrase});
    return j['is_upgraded'] == true;
  }

  Future<AnonSession> recover(String anonId, String passphrase) async =>
      _store(_session(await _c.postJson('/v1/identity/recover',
          auth: AuthMode.none,
          body: {'anon_id': anonId, 'passphrase': passphrase})));

  /// Explicit refresh (same single-flight path as the 401 retry).
  Future<TokenPair> refresh() async {
    final cur = await _tokens.readUser();
    if (cur == null) throw const ApiError('auth_expired', 'Session expired', 401);
    final j = await _c.postJson('/v1/identity/refresh',
        auth: AuthMode.none, body: {'refresh_token': cur.refreshToken});
    final t = TokenPair.tryParse(j);
    if (t == null) throw const ApiError('bad_response', 'Malformed refresh response', 200);
    await _tokens.writeUser(t);
    return t;
  }
}
