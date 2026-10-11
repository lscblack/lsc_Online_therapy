import 'dart:async';
import 'dart:convert';

import 'api_client.dart';

class SseEvent {
  const SseEvent(this.event, this.data);
  final String event;
  final String data;
}

SseEvent? _block(String block) {
  var event = 'message';
  final data = <String>[];
  for (final line in block.split('\n')) {
    if (line.isEmpty || line.startsWith(':')) continue;
    final i = line.indexOf(':');
    final field = i == -1 ? line : line.substring(0, i);
    var val = i == -1 ? '' : line.substring(i + 1);
    if (val.startsWith(' ')) val = val.substring(1);
    if (field == 'event') {
      event = val;
    } else if (field == 'data') {
      data.add(val);
    }
  }
  return data.isEmpty ? null : SseEvent(event, data.join('\n'));
}

ApiError _errorFrom(String data) {
  var code = 'stream_error';
  var msg = 'Stream error';
  try {
    final j = jsonDecode(data);
    if (j is Map) {
      final e = j['error'] is Map ? j['error'] as Map : j;
      if (e['code'] is String) code = e['code'] as String;
      if (e['message'] is String) msg = e['message'] as String;
    }
  } catch (_) {}
  return ApiError(code, msg, 200);
}

/// Parses an SSE byte stream into events. Handles arbitrary chunk boundaries
/// (including mid-UTF8 / mid-CRLF), ignores `[DONE]`, and throws [ApiError] on
/// `event: error`.
Stream<SseEvent> parseSse(Stream<List<int>> body) async* {
  var buf = '';
  await for (final chunk in body.cast<List<int>>().transform(utf8.decoder)) {
    buf += chunk;
    // Normalise newlines, but keep a trailing lone \r (its \n may come next).
    final hold = buf.endsWith('\r');
    var work = hold ? buf.substring(0, buf.length - 1) : buf;
    work = work.replaceAll('\r\n', '\n').replaceAll('\r', '\n');
    buf = hold ? '$work\r' : work;
    final scan = hold ? work : buf;
    var start = 0;
    while (true) {
      final idx = scan.indexOf('\n\n', start);
      if (idx == -1) break;
      final ev = _block(scan.substring(start, idx));
      start = idx + 2;
      if (ev == null) continue;
      if (ev.data == '[DONE]') return;
      if (ev.event == 'error') throw _errorFrom(ev.data);
      yield ev;
    }
    buf = (hold ? '${scan.substring(start)}\r' : scan.substring(start));
  }
  final tail = _block(buf.replaceAll('\r\n', '\n').replaceAll('\r', '\n'));
  if (tail != null && tail.data != '[DONE]') {
    if (tail.event == 'error') throw _errorFrom(tail.data);
    yield tail;
  }
}
