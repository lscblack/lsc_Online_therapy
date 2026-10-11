class Profile {
  const Profile({
    this.nickname,
    this.ageBand = 'undisclosed',
    this.gender,
    this.pronouns,
    this.tonePref,
    this.interests = const [],
    this.sensitiveContext,
    this.consent = const {},
    this.updatedAt,
  });

  final String? nickname;
  final String ageBand;
  final String? gender;
  final String? pronouns;
  final String? tonePref;
  final List<String> interests;
  final String? sensitiveContext;
  final Map<String, Object?> consent;
  final String? updatedAt;

  factory Profile.fromJson(Map<String, Object?> j) => Profile(
        nickname: j['nickname'] as String?,
        ageBand: (j['age_band'] as String?) ?? 'undisclosed',
        gender: j['gender'] as String?,
        pronouns: j['pronouns'] as String?,
        tonePref: j['tone_pref'] as String?,
        interests: ((j['interests'] as List?) ?? const []).whereType<String>().toList(),
        sensitiveContext: j['sensitive_context'] as String?,
        consent: ((j['consent'] as Map?) ?? const {}).cast<String, Object?>(),
        updatedAt: j['updated_at'] as String?,
      );
}

/// PUT body. Only fields that are set are sent (omitted = untouched on the server).
class ProfileUpdate {
  const ProfileUpdate({
    this.nickname,
    this.ageBand,
    this.gender,
    this.pronouns,
    this.tonePref,
    this.interests,
    this.sensitiveContext,
  });

  final String? nickname;
  final String? ageBand;
  final String? gender;
  final String? pronouns;
  final String? tonePref;
  final List<String>? interests;
  final String? sensitiveContext;

  Map<String, Object?> toJson() => {
        if (nickname != null) 'nickname': nickname,
        if (ageBand != null) 'age_band': ageBand,
        if (gender != null) 'gender': gender,
        if (pronouns != null) 'pronouns': pronouns,
        if (tonePref != null) 'tone_pref': tonePref,
        if (interests != null) 'interests': interests,
        if (sensitiveContext != null) 'sensitive_context': sensitiveContext,
      };
}
