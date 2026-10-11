class TokenPair {
  const TokenPair({
    required this.accessToken,
    required this.refreshToken,
    this.tokenType = 'bearer',
  });

  final String accessToken;
  final String refreshToken;
  final String tokenType;

  /// Returns null when the map lacks usable tokens.
  static TokenPair? tryParse(Map<String, Object?> j) {
    final a = j['access_token'];
    final r = j['refresh_token'];
    if (a is! String || a.isEmpty || r is! String || r.isEmpty) return null;
    final t = j['token_type'];
    return TokenPair(
        accessToken: a, refreshToken: r, tokenType: t is String ? t : 'bearer');
  }

  Map<String, Object?> toJson() => {
        'access_token': accessToken,
        'refresh_token': refreshToken,
        'token_type': tokenType,
      };
}

class AnonSession {
  const AnonSession({required this.tokens, required this.anonId});
  final TokenPair tokens;
  final String anonId;
}
