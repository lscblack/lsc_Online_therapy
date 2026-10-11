import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/auth.dart';
import '../../state/profile.dart';

/// App-level settings operations. Bound to the container (not a widget) so a
/// wipe keeps running after the Settings screen is swapped out for onboarding.
class SettingsActions {
  SettingsActions(this._ref);
  final Ref _ref;

  /// Erases server data, then local credentials, then restarts onboarding on a
  /// fresh anonymous identity. Throws (leaving everything as it was) if the
  /// server delete fails.
  Future<void> wipeMyData() async {
    await _ref.read(profileApiProvider).wipe();
    final auth = _ref.read(authProvider.notifier);
    await auth.clearLocalIdentity();
    await _ref.read(onboardedProvider.notifier).reset();
    try {
      await auth.ensureAnon();
    } catch (_) {
      // Offline: onboarding retries ensureAnon when it finishes.
    }
  }

  Future<void> rerunOnboarding() =>
      _ref.read(onboardedProvider.notifier).reset();
}

final settingsActionsProvider = Provider<SettingsActions>(SettingsActions.new);
