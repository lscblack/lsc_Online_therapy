import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme.dart';
import 'features/shell/shell.dart';

class UbuzimaApp extends ConsumerWidget {
  const UbuzimaApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'Ubuzima',
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: ref.watch(themeModeProvider),
      // Framework widgets (Material) have no 'rw' locale; app strings come
      // from languageProvider, so Material stays on its default (en).
      home: const AppShell(),
    );
  }
}
