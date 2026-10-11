import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/prefs.dart';
import '../data/models/profile.dart';
import 'auth.dart';

const _kOnboarded = 'onboarded';

/// Whether first-run onboarding has been completed (persisted in prefs).
class OnboardedController extends Notifier<bool> {
  @override
  bool build() => readPref(ref.read(prefsProvider), _kOnboarded) == '1';

  Future<void> markDone() async {
    await writePref(ref.read(prefsProvider), _kOnboarded, '1');
    state = true;
  }

  /// Re-run onboarding (e.g. from Settings).
  Future<void> reset() async {
    await writePref(ref.read(prefsProvider), _kOnboarded, '0');
    state = false;
  }
}

final onboardedProvider =
    NotifierProvider<OnboardedController, bool>(OnboardedController.new);

/// What the wizard has collected so far. Empty values mean "not provided".
class OnboardingDraft {
  const OnboardingDraft({
    this.nickname = '',
    this.ageBand,
    this.gender,
    this.pronouns,
    this.tonePref,
    this.interests = const [],
    this.sensitive = '',
  });

  final String nickname;
  final String? ageBand;
  final String? gender;
  final String? pronouns;
  final String? tonePref;
  final List<String> interests;
  final String sensitive;

  /// Only provided fields; sensitive context only when entered.
  ProfileUpdate toUpdate() {
    final nick = nickname.trim();
    final sens = sensitive.trim();
    return ProfileUpdate(
      nickname: nick.isEmpty ? null : nick,
      ageBand: ageBand,
      gender: gender,
      pronouns: pronouns,
      tonePref: tonePref,
      interests: interests.isEmpty ? null : List.of(interests),
      sensitiveContext: sens.isEmpty ? null : sens,
    );
  }
}

/// Ensures a session, PUTs the provided fields (skipped when nothing was
/// provided), then marks onboarding done. Throws on failure (nothing marked).
Future<void> submitOnboarding(WidgetRef ref, OnboardingDraft d) async {
  await ref.read(authProvider.notifier).ensureAnon();
  final u = d.toUpdate();
  if (u.toJson().isNotEmpty) await ref.read(profileApiProvider).put(u);
  await ref.read(onboardedProvider.notifier).markDone();
}
