import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:ubuzima/data/api_client.dart';
import 'package:ubuzima/data/sse.dart';

Stream<List<int>> chunks(List<String> parts) =>
    Stream.fromIterable(parts.map(utf8.encode));

void main() {
  test('delta tokens then done', () async {
    final ev = await parseSse(chunks([
      'event: delta\ndata: Hel\n\n',
      'event: delta\ndata: lo \n\nevent: done\ndata: {"answer":"Hello"}\n\n',
      'data: [DONE]\n\n',
    ])).toList();
    expect(ev.map((e) => e.event), ['delta', 'delta', 'done']);
    expect(ev.take(2).map((e) => e.data).join(), 'Hello ');
    expect(ev.last.data, '{"answer":"Hello"}');
  });

  test('split chunk mid-line, CRLF and multibyte', () async {
    final bytes = utf8.encode('event: delta\r\ndata: mu\u{1F600}rakoze\r\n\r\n');
    final cut = 20;
    final ev = await parseSse(
        Stream.fromIterable([bytes.sublist(0, cut), bytes.sublist(cut, bytes.length - 1), bytes.sublist(bytes.length - 1)])).toList();
    expect(ev.single.data, 'mu\u{1F600}rakoze');
  });

  test('CRLF split between \\r and \\n', () async {
    final ev = await parseSse(chunks(['event: delta\r\ndata: a\r', '\n\r', '\ndata: [DONE]\r\n\r\n'])).toList();
    expect(ev.single.data, 'a');
  });

  test('multi-line data joined', () async {
    final ev = await parseSse(chunks(['event: delta\ndata: a\ndata: b\n\n'])).toList();
    expect(ev.single.data, 'a\nb');
  });

  test('error event throws ApiError', () async {
    final s = parseSse(chunks([
      'event: delta\ndata: hi\n\n',
      'event: error\ndata: {"code":"rate_limited","message":"slow down"}\n\n',
    ]));
    await expectLater(
        s.toList(),
        throwsA(isA<ApiError>().having((e) => e.code, 'code', 'rate_limited')));
  });

  test('final event without trailing blank line is flushed', () async {
    final ev = await parseSse(chunks(['event: done\ndata: {}'])).toList();
    expect(ev.single.event, 'done');
  });
}
