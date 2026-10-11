import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';
import '../data/endpoints/chat.dart';
import '../data/endpoints/identity.dart';
import '../data/endpoints/profile.dart';
import '../data/endpoints/voice.dart';
import '../data/token_store.dart';

final tokenStoreProvider = Provider<TokenStore>((ref) => SecureTokenStore());

final apiClientProvider =
    Provider<ApiClient>((ref) => ApiClient(tokens: ref.watch(tokenStoreProvider)));

final identityApiProvider = Provider<IdentityApi>((ref) =>
    IdentityApi(ref.watch(apiClientProvider), ref.watch(tokenStoreProvider)));
final profileApiProvider =
    Provider<ProfileApi>((ref) => ProfileApi(ref.watch(apiClientProvider)));
final chatApiProvider =
    Provider<ChatApi>((ref) => ChatApi(ref.watch(apiClientProvider)));
final voiceApiProvider =
    Provider<VoiceApi>((ref) => VoiceApi(ref.watch(apiClientProvider)));

class AuthState {
  const AuthState({this.ready = false, this.anonId});
  final bool ready;
  final String? anonId;
}

class AuthController extends Notifier<AuthState> {
  Future<void>? _inflight;

  @override
  AuthState build() {
    ref.read(apiClientProvider).onAuthExpired =
        () => state = AuthState(ready: false, anonId: state.anonId);
    return const AuthState();
  }

  /// Ensures an end-user identity exists (reuses stored tokens, else mints an
  /// anonymous one). Single-flight; rethrows ApiError (e.g. offline) to the caller.
  Future<void> ensureAnon() => _inflight ??= _ensure().whenComplete(() => _inflight = null);

  Future<void> _ensure() async {
    final store = ref.read(tokenStoreProvider);
    if (await store.readUser() != null) {
      state = AuthState(ready: true, anonId: await store.readAnonId());
      return;
    }
    final s = await ref.read(identityApiProvider).anon();
    state = AuthState(ready: true, anonId: s.anonId);
  }

  /// Recover an existing identity with its anon id + passphrase.
  Future<void> recover(String anonId, String passphrase) async {
    final s = await ref.read(identityApiProvider).recover(anonId, passphrase);
    state = AuthState(ready: true, anonId: s.anonId);
  }

  /// Clears stored credentials and in-memory session (no re-bootstrap).
  Future<void> clearLocalIdentity() async {
    final store = ref.read(tokenStoreProvider);
    await store.clearUser();
    await store.clearAnonId();
    state = const AuthState();
  }

  /// Clears all local credentials (after a server-side wipe) and mints a fresh identity.
  Future<void> resetIdentity() async {
    await clearLocalIdentity();
    await ensureAnon();
  }
}

final authProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
