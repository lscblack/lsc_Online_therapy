import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models/token_pair.dart';

/// Persistence for the end-user token pair and anonymous id.
abstract class TokenStore {
  Future<TokenPair?> readUser();
  Future<void> writeUser(TokenPair t);
  Future<void> clearUser();
  Future<String?> readAnonId();
  Future<void> writeAnonId(String id);
  Future<void> clearAnonId();
}

/// flutter_secure_storage-backed store (Keychain / Keystore).
class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
      : _s = storage ?? const FlutterSecureStorage();
  final FlutterSecureStorage _s;
  static const _kUser = 'ubuzima.user_tokens';
  static const _kAnon = 'ubuzima.anon_id';

  @override
  Future<TokenPair?> readUser() async {
    try {
      final raw = await _s.read(key: _kUser);
      if (raw == null) return null;
      final j = jsonDecode(raw);
      return j is Map ? TokenPair.tryParse(j.cast<String, Object?>()) : null;
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> writeUser(TokenPair t) => _s.write(key: _kUser, value: jsonEncode(t.toJson()));

  @override
  Future<void> clearUser() => _s.delete(key: _kUser);

  @override
  Future<String?> readAnonId() async {
    try {
      return await _s.read(key: _kAnon);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> writeAnonId(String id) => _s.write(key: _kAnon, value: id);

  @override
  Future<void> clearAnonId() => _s.delete(key: _kAnon);
}

/// In-memory store for tests / previews.
class MemoryTokenStore implements TokenStore {
  TokenPair? _user;
  String? _anon;

  @override
  Future<TokenPair?> readUser() async => _user;
  @override
  Future<void> writeUser(TokenPair t) async => _user = t;
  @override
  Future<void> clearUser() async => _user = null;
  @override
  Future<String?> readAnonId() async => _anon;
  @override
  Future<void> writeAnonId(String id) async => _anon = id;
  @override
  Future<void> clearAnonId() async => _anon = null;
}
