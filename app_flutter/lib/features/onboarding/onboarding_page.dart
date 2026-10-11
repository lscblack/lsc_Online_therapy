import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';
import '../../state/auth.dart';
import '../../state/profile.dart';

const _ages = ['under15', '15_17', '18_19', '20_24', '25_plus'];
const _genders = ['female', 'male', 'nonbinary'];
const _pronouns = [('she/her', 'she'), ('he/him', 'he'), ('they/them', 'they')];
const _tones = ['casual', 'gentle', 'direct'];
const _interestKeys = [
  'sleep', 'stress', 'relationships', 'nutrition', 'sexual_health', 'fitness'
];
const _steps = 4;

/// First-run wizard. Nickname is required to continue; every later step is
/// skippable. Skipping a step discards what was typed on it.
class OnboardingPage extends ConsumerStatefulWidget {
  const OnboardingPage({super.key});
  @override
  ConsumerState<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends ConsumerState<OnboardingPage> {
  int _step = 0;
  bool _busy = false;
  bool _failed = false;

  final _nick = TextEditingController();
  final _sens = TextEditingController();
  String? _age, _gender, _pron, _tone;
  final List<String> _interests = [];

  // One node per step so the AnimatedSwitcher's outgoing and incoming
  // subtrees never share a FocusNode.
  final _headingFocus = List.generate(
      _steps, (i) => FocusNode(debugLabel: 'onboarding-heading-$i'));

  @override
  void initState() {
    super.initState();
    // Create the anonymous identity up front; retried on finish if offline.
    Future.microtask(() => ref.read(authProvider.notifier).ensureAnon().catchError((_) {}));
  }

  @override
  void dispose() {
    _nick.dispose();
    _sens.dispose();
    for (final f in _headingFocus) {
      f.dispose();
    }
    super.dispose();
  }

  OnboardingDraft get _draft => OnboardingDraft(
        nickname: _nick.text,
        ageBand: _age,
        gender: _gender,
        pronouns: _pron,
        tonePref: _tone,
        interests: _interests,
        sensitive: _sens.text,
      );

  void _go(int s) {
    setState(() {
      _step = s;
      _failed = false;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _headingFocus[_step].requestFocus();
    });
  }

  void _clearStep(int s) {
    switch (s) {
      case 1:
        _age = _gender = _pron = null;
      case 2:
        _tone = null;
        _interests.clear();
      case 3:
        _sens.clear();
    }
  }

  void _skip() {
    _clearStep(_step);
    if (_step == _steps - 1) {
      _finish();
    } else {
      _go(_step + 1);
    }
  }

  Future<void> _finish() async {
    setState(() {
      _busy = true;
      _failed = false;
    });
    try {
      await submitOnboarding(ref, _draft);
      // The gate in UbuzimaApp swaps this page out once onboarded is true.
    } catch (_) {
      if (mounted) setState(() => _failed = true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    final theme = Theme.of(context);
    final reduce = MediaQuery.of(context).disableAnimations;
    final canNext = _step != 0 || _nick.text.trim().isNotEmpty;
    final last = _step == _steps - 1;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                  child: Semantics(
                    label: '${t('ob.step')} ${_step + 1} ${t('ob.of')} $_steps',
                    child: ExcludeSemantics(
                      child: TweenAnimationBuilder<double>(
                        tween: Tween(end: (_step + 1) / _steps),
                        duration: reduce ? Duration.zero : const Duration(milliseconds: 300),
                        builder: (_, v, _) => ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: LinearProgressIndicator(value: v, minHeight: 8),
                        ),
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
                    child: AnimatedSwitcher(
                      duration: reduce ? Duration.zero : const Duration(milliseconds: 250),
                      transitionBuilder: (c, a) => FadeTransition(
                        opacity: a,
                        child: SlideTransition(
                          position: Tween(begin: const Offset(0.05, 0), end: Offset.zero)
                              .animate(a),
                          child: c,
                        ),
                      ),
                      child: KeyedSubtree(
                        key: ValueKey(_step),
                        child: _stepBody(t, theme),
                      ),
                    ),
                  ),
                ),
                if (_failed)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Semantics(
                      liveRegion: true,
                      child: Text(t('ob.error'),
                          key: const Key('ob-error'),
                          style: TextStyle(color: theme.colorScheme.error)),
                    ),
                  ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                  child: Wrap(
                    alignment: WrapAlignment.end,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      if (_step > 0)
                        TextButton(
                          key: const Key('ob-back'),
                          onPressed: _busy ? null : () => _go(_step - 1),
                          child: Text(t('ob.back')),
                        ),
                      if (_step > 0)
                        TextButton(
                          key: const Key('ob-skip'),
                          onPressed: _busy ? null : _skip,
                          child: Text(t('ob.skip')),
                        ),
                      FilledButton(
                        key: Key(last ? 'ob-finish' : 'ob-next'),
                        onPressed: (!canNext || _busy)
                            ? null
                            : (last ? _finish : () => _go(_step + 1)),
                        child: Text(_busy
                            ? t('ob.saving')
                            : _failed
                                ? t('ob.retry')
                                : last
                                    ? t('ob.finish')
                                    : t('ob.next')),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _heading(String text, ThemeData theme) => Focus(
        focusNode: _headingFocus[_step],
        child: Semantics(
          header: true,
          child: Text(text, style: theme.textTheme.headlineSmall),
        ),
      );

  Widget _label(String text, ThemeData theme) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 8),
        child: Text(text, style: theme.textTheme.titleMedium),
      );

  /// Single-select chip group; tapping the selected chip clears it.
  Widget _choice(List<(String value, String label)> opts, String? sel,
      String keyPrefix, void Function(String?) set) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final o in opts)
          ChoiceChip(
            key: Key('$keyPrefix-${o.$1}'),
            label: Text(o.$2),
            selected: sel == o.$1,
            materialTapTargetSize: MaterialTapTargetSize.padded,
            onSelected: (on) => setState(() => set(on ? o.$1 : null)),
          ),
      ],
    );
  }

  Widget _stepBody(T t, ThemeData theme) {
    switch (_step) {
      case 0:
        final lang = ref.watch(languageProvider);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _heading(t('ob.nick.title'), theme),
            const SizedBox(height: 16),
            TextField(
              key: const Key('ob-nick'),
              controller: _nick,
              autofocus: true,
              maxLength: 40,
              textInputAction: TextInputAction.next,
              onChanged: (_) => setState(() {}),
              onSubmitted: (_) {
                if (_nick.text.trim().isNotEmpty) _go(1);
              },
              decoration: InputDecoration(
                labelText: t('ob.nick.label'),
                helperText: t('ob.nick.hint'),
                helperMaxLines: 2,
              ),
            ),
            _label(t('ob.lang.label'), theme),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final l in supportedLangs)
                  ChoiceChip(
                    key: Key('ob-lang-$l'),
                    label: Text(t('lang.$l')),
                    selected: lang == l,
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    onSelected: (_) => ref.read(languageProvider.notifier).set(l),
                  ),
              ],
            ),
          ],
        );
      case 1:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _heading(t('ob.about.title'), theme),
            const SizedBox(height: 8),
            Text(t('ob.about.note')),
            _label(t('ob.age.label'), theme),
            _choice([for (final a in _ages) (a, t('ob.age.$a'))], _age, 'ob-age',
                (v) => _age = v),
            _label(t('ob.gender.label'), theme),
            _choice([for (final g in _genders) (g, t('ob.gender.$g'))], _gender,
                'ob-gender', (v) => _gender = v),
            _label(t('ob.pron.label'), theme),
            _choice([for (final p in _pronouns) (p.$1, t('ob.pron.${p.$2}'))], _pron,
                'ob-pron', (v) => _pron = v),
          ],
        );
      case 2:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _heading(t('ob.style.title'), theme),
            _label(t('ob.tone.label'), theme),
            _choice([for (final x in _tones) (x, t('ob.tone.$x'))], _tone, 'ob-tone',
                (v) => _tone = v),
            _label(t('ob.interests.label'), theme),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final k in _interestKeys)
                  FilterChip(
                    key: Key('ob-int-$k'),
                    label: Text(t('ob.int.$k')),
                    selected: _interests.contains(k),
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    onSelected: (on) => setState(
                        () => on ? _interests.add(k) : _interests.remove(k)),
                  ),
              ],
            ),
          ],
        );
      default:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _heading(t('ob.sens.title'), theme),
            const SizedBox(height: 4),
            Text(t('ob.sens.optional'),
                style: theme.textTheme.labelLarge
                    ?.copyWith(color: theme.colorScheme.secondary)),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.lock_outline),
                    const SizedBox(width: 12),
                    Expanded(child: Text(t('ob.sens.privacy'))),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              key: const Key('ob-sensitive'),
              controller: _sens,
              minLines: 3,
              maxLines: 6,
              maxLength: 1000,
              decoration: InputDecoration(labelText: t('ob.sens.label')),
            ),
          ],
        );
    }
  }
}
