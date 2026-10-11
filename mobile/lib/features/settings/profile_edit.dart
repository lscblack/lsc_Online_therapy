import '../../data/models/profile.dart';

/// The user's in-progress edits. Empty strings / null mean "no value".
class ProfileEdit {
  const ProfileEdit({
    this.nickname = '',
    this.ageBand = 'undisclosed',
    this.gender,
    this.pronouns,
    this.tonePref,
    this.interests = const [],
    this.sensitive = '',
  });

  factory ProfileEdit.from(Profile p) => ProfileEdit(
    nickname: p.nickname ?? '',
    ageBand: p.ageBand,
    gender: p.gender,
    pronouns: p.pronouns,
    tonePref: p.tonePref,
    interests: List.of(p.interests),
    sensitive: p.sensitiveContext ?? '',
  );

  final String nickname;
  final String ageBand;
  final String? gender;
  final String? pronouns;
  final String? tonePref;
  final List<String> interests;
  final String sensitive;
}

/// Builds a PUT containing ONLY what changed versus [orig]. A text/choice field
/// the user emptied is cleared with an explicit null (ProfileUpdate.clear),
/// which for sensitive_context revokes the stored context.
ProfileUpdate diffProfile(Profile orig, ProfileEdit e) {
  final clear = <ProfileField>{};

  String? text(String? before, String now, ProfileField f) {
    final n = now.trim();
    final b = (before ?? '').trim();
    if (n == b) return null;
    if (n.isEmpty) {
      clear.add(f);
      return null;
    }
    return n;
  }

  String? choice(String? before, String? now, ProfileField f) {
    if (now == before) return null;
    if (now == null) {
      clear.add(f);
      return null;
    }
    return now;
  }

  final oldInt = orig.interests.toSet();
  final interestsChanged =
      oldInt.length != e.interests.toSet().length ||
      !oldInt.containsAll(e.interests);

  return ProfileUpdate(
    nickname: text(orig.nickname, e.nickname, ProfileField.nickname),
    ageBand: e.ageBand == orig.ageBand ? null : e.ageBand,
    gender: choice(orig.gender, e.gender, ProfileField.gender),
    pronouns: choice(orig.pronouns, e.pronouns, ProfileField.pronouns),
    tonePref: choice(orig.tonePref, e.tonePref, ProfileField.tonePref),
    interests: interestsChanged ? List.of(e.interests) : null,
    sensitiveContext: text(
      orig.sensitiveContext,
      e.sensitive,
      ProfileField.sensitiveContext,
    ),
    clear: clear,
  );
}
