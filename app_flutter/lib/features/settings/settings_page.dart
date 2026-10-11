import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../../core/theme.dart';
import '../../data/models/profile.dart';
import '../../state/auth.dart';
import 'profile_edit.dart';
import 'settings_actions.dart';

const _ages = ['under15', '15_17', '18_19', '20_24', '25_plus'];
const _genders = ['female', 'male', 'nonbinary'];
const _pronouns = [('she/her', 'she'), ('he/him', 'he'), ('they/them', 'they')];
const _tones = ['casual', 'gentle', 'direct'];
const _interestKeys = [
  'sleep',
  'stress',
  'relationships',
  'nutrition',
  'sexual_health',
  'fitness',
];

enum _Load { loading, ready, failed }

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});
  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  _Load _load = _Load.loading;
  Profile _orig = const Profile();
  final _nick = TextEditingController();
  final _sens = TextEditingController();
  String _age = 'undisclosed';
  String? _gender, _pron, _tone;
  final List<String> _interests = [];
  bool _saving = false, _saved = false, _saveFailed = false;
  bool _wiping = false, _wipeFailed = false;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  @override
  void dispose() {
    _nick.dispose();
    _sens.dispose();
    super.dispose();
  }

  Future<void> _fetch() async {
    setState(() => _load = _Load.loading);
    try {
      await ref.read(authProvider.notifier).ensureAnon();
      final p = await ref.read(profileApiProvider).get();
      if (!mounted) return;
      _adopt(p);
      setState(() => _load = _Load.ready);
    } catch (_) {
      if (mounted) setState(() => _load = _Load.failed);
    }
  }

  void _adopt(Profile p) {
    final e = ProfileEdit.from(p);
    _orig = p;
    _nick.text = e.nickname;
    _sens.text = e.sensitive;
    _age = e.ageBand;
    _gender = e.gender;
    _pron = e.pronouns;
    _tone = e.tonePref;
    _interests
      ..clear()
      ..addAll(e.interests);
  }

  ProfileEdit get _edit => ProfileEdit(
    nickname: _nick.text,
    ageBand: _age,
    gender: _gender,
    pronouns: _pron,
    tonePref: _tone,
    interests: _interests,
    sensitive: _sens.text,
  );

  Future<void> _save() async {
    final u = diffProfile(_orig, _edit);
    if (u.toJson().isEmpty) {
      setState(() {
        _saved = true;
        _saveFailed = false;
      });
      return;
    }
    setState(() {
      _saving = true;
      _saved = false;
      _saveFailed = false;
    });
    try {
      final p = await ref.read(profileApiProvider).put(u);
      if (!mounted) return;
      _adopt(p);
      setState(() => _saved = true);
    } catch (_) {
      if (mounted) setState(() => _saveFailed = true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _touch(VoidCallback f) => setState(() {
    f();
    _saved = false;
  });

  Future<void> _wipe() async {
    final t = ref.read(tProvider);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(t('wipe.title')),
        content: Text(t('wipe.body')),
        actions: [
          TextButton(
            key: const Key('wipe-cancel'),
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(t('btn.cancel')),
          ),
          FilledButton(
            key: const Key('wipe-confirm'),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
              foregroundColor: Theme.of(ctx).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(t('wipe.confirm')),
          ),
        ],
      ),
    );
    if (ok != true) return;
    setState(() {
      _wiping = true;
      _wipeFailed = false;
    });
    try {
      await ref.read(settingsActionsProvider).wipeMyData();
      // The gate in UbuzimaApp now shows onboarding for the fresh identity.
    } catch (_) {
      if (mounted) setState(() => _wipeFailed = true);
    } finally {
      if (mounted) setState(() => _wiping = false);
    }
  }

  Widget _card(
    String title,
    List<Widget> children,
    ThemeData theme, {
    String? note,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: Text(title, style: theme.textTheme.titleMedium),
            ),
            if (note != null) ...[
              const SizedBox(height: 4),
              Text(
                note,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            const SizedBox(height: 12),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _label(String text, ThemeData theme) => Padding(
    padding: const EdgeInsets.only(top: 16, bottom: 8),
    child: Text(text, style: theme.textTheme.titleSmall),
  );

  Widget _choice(
    List<(String, String)> opts,
    String? sel,
    String prefix,
    void Function(String?) set,
  ) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final o in opts)
          ChoiceChip(
            key: Key('$prefix-${o.$1}'),
            label: Text(o.$2),
            selected: sel == o.$1,
            materialTapTargetSize: MaterialTapTargetSize.padded,
            onSelected: (on) => _touch(() => set(on ? o.$1 : null)),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    final theme = Theme.of(context);
    final mode = ref.watch(themeModeProvider);
    final lang = ref.watch(languageProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _card(t('settings.appearance'), [
            Text(t('settings.theme'), style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            SegmentedButton<ThemeMode>(
              segments: [
                ButtonSegment(
                  value: ThemeMode.system,
                  label: Text(t('theme.system')),
                ),
                ButtonSegment(
                  value: ThemeMode.light,
                  label: Text(t('theme.light')),
                ),
                ButtonSegment(
                  value: ThemeMode.dark,
                  label: Text(t('theme.dark')),
                ),
              ],
              selected: {mode},
              onSelectionChanged: (s) =>
                  ref.read(themeModeProvider.notifier).set(s.first),
            ),
            const SizedBox(height: 16),
            Text(t('settings.language'), style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: [
                ButtonSegment(value: 'en', label: Text(t('lang.en'))),
                ButtonSegment(value: 'rw', label: Text(t('lang.rw'))),
              ],
              selected: {lang},
              onSelectionChanged: (s) =>
                  ref.read(languageProvider.notifier).set(s.first),
            ),
          ], theme),
          _card(
            t('settings.profile'),
            _profileBody(t, theme),
            theme,
            note: t('settings.profile.note'),
          ),
          _card(
            t('settings.onboarding'),
            [
              OutlinedButton.icon(
                key: const Key('set-rerun'),
                onPressed: () =>
                    ref.read(settingsActionsProvider).rerunOnboarding(),
                icon: const Icon(Icons.replay),
                label: Text(t('settings.rerun')),
              ),
            ],
            theme,
            note: t('settings.rerun.note'),
          ),
          _card(
            t('settings.data'),
            [
              FilledButton.tonalIcon(
                key: const Key('set-wipe'),
                style: FilledButton.styleFrom(
                  foregroundColor: theme.colorScheme.error,
                ),
                onPressed: _wiping ? null : _wipe,
                icon: const Icon(Icons.delete_outline),
                label: Text(_wiping ? t('wipe.working') : t('wipe.button')),
              ),
              if (_wipeFailed) ...[
                const SizedBox(height: 12),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    t('wipe.error'),
                    key: const Key('set-wipe-error'),
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                ),
              ],
            ],
            theme,
            note: t('wipe.note'),
          ),
        ],
      ),
    );
  }

  List<Widget> _profileBody(T t, ThemeData theme) {
    switch (_load) {
      case _Load.loading:
        return [
          Center(
            child: Semantics(
              label: t('settings.loading'),
              child: const CircularProgressIndicator(),
            ),
          ),
        ];
      case _Load.failed:
        return [
          Text(t('settings.loadError'), key: const Key('set-load-error')),
          const SizedBox(height: 8),
          OutlinedButton(
            key: const Key('set-retry'),
            onPressed: _fetch,
            child: Text(t('chat.retry')),
          ),
        ];
      case _Load.ready:
        return [
          TextField(
            key: const Key('set-nick'),
            controller: _nick,
            maxLength: 40,
            onChanged: (_) => _touch(() {}),
            decoration: InputDecoration(labelText: t('ob.nick.label')),
          ),
          _label(t('ob.age.label'), theme),
          _choice(
            [for (final a in _ages) (a, t('ob.age.$a'))],
            _age == 'undisclosed' ? null : _age,
            'set-age',
            (v) => _age = v ?? 'undisclosed',
          ),
          _label(t('ob.gender.label'), theme),
          _choice(
            [for (final g in _genders) (g, t('ob.gender.$g'))],
            _gender,
            'set-gender',
            (v) => _gender = v,
          ),
          _label(t('ob.pron.label'), theme),
          _choice(
            [for (final p in _pronouns) (p.$1, t('ob.pron.${p.$2}'))],
            _pron,
            'set-pron',
            (v) => _pron = v,
          ),
          _label(t('ob.tone.label'), theme),
          _choice(
            [for (final x in _tones) (x, t('ob.tone.$x'))],
            _tone,
            'set-tone',
            (v) => _tone = v,
          ),
          _label(t('ob.interests.label'), theme),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final k in _interestKeys)
                FilterChip(
                  key: Key('set-int-$k'),
                  label: Text(t('ob.int.$k')),
                  selected: _interests.contains(k),
                  materialTapTargetSize: MaterialTapTargetSize.padded,
                  onSelected: (on) => _touch(
                    () => on ? _interests.add(k) : _interests.remove(k),
                  ),
                ),
            ],
          ),
          _label(t('ob.sens.title'), theme),
          Text(t('settings.sens.note'), style: theme.textTheme.bodySmall),
          const SizedBox(height: 8),
          TextField(
            key: const Key('set-sens'),
            controller: _sens,
            minLines: 2,
            maxLines: 6,
            maxLength: 1000,
            onChanged: (_) => _touch(() {}),
            decoration: InputDecoration(labelText: t('ob.sens.label')),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              key: const Key('set-save'),
              onPressed: _saving ? null : _save,
              child: Text(_saving ? t('ob.saving') : t('btn.save')),
            ),
          ),
          if (_saved || _saveFailed) ...[
            const SizedBox(height: 12),
            Semantics(
              liveRegion: true,
              child: _saveFailed
                  ? Text(
                      t('settings.saveError'),
                      key: const Key('set-save-error'),
                      style: TextStyle(color: theme.colorScheme.error),
                    )
                  : Text(t('settings.saved'), key: const Key('set-saved')),
            ),
          ],
        ];
    }
  }
}
