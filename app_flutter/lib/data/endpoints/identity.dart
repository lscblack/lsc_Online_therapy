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

  /// Explicit refresh; delegates to ApiClient's single-flight refresh so the
  /// (possibly rotating) refresh token is never spent twice concurrently.
  Future<TokenPair> refresh() => _c.refreshNow();
}
