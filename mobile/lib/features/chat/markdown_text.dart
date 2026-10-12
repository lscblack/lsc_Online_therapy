import 'package:flutter/material.dart';

/// Minimal markdown for chat answers: **bold**, bullet lists (* / - / •) and paragraphs.
/// Inline [S1]/[S2] citation markers are stripped (sources show as chips). Text stays selectable.
class MarkdownText extends StatelessWidget {
  const MarkdownText(this.text, {super.key, this.style});
  final String text;
  final TextStyle? style;

  static final _bullet = RegExp(r'^(\*|-|•)\s+');
  static final _cite = RegExp(r'\s*\[S\d+\]');
  static final _bold = RegExp(r'\*\*([^*]+)\*\*');
  static final _spaces = RegExp(r' {2,}');

  Widget _rich(String s, TextStyle? base) {
    final cleaned = s.replaceAll(_cite, '').replaceAll(_spaces, ' ').trim();
    final spans = <TextSpan>[];
    var i = 0;
    for (final m in _bold.allMatches(cleaned)) {
      if (m.start > i) spans.add(TextSpan(text: cleaned.substring(i, m.start)));
      spans.add(TextSpan(text: m.group(1), style: const TextStyle(fontWeight: FontWeight.w700)));
      i = m.end;
    }
    if (i < cleaned.length) spans.add(TextSpan(text: cleaned.substring(i)));
    return SelectableText.rich(TextSpan(style: base, children: spans));
  }

  @override
  Widget build(BuildContext context) {
    final base = style ?? Theme.of(context).textTheme.bodyLarge;
    final blocks = text.replaceAll('\r\n', '\n').split(RegExp(r'\n{2,}'));
    final children = <Widget>[];
    for (final block in blocks) {
      final lines = block.split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty).toList();
      if (lines.isEmpty) continue;
      if (lines.every((l) => _bullet.hasMatch(l))) {
        for (final l in lines) {
          children.add(Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('•  ', style: base),
                Expanded(child: _rich(l.replaceFirst(_bullet, ''), base)),
              ],
            ),
          ));
        }
      } else {
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: _rich(lines.join('\n'), base),
        ));
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: children,
    );
  }
}
