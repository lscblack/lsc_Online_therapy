import 'dart:convert';

import 'package:dio/dio.dart';

import '../api_client.dart';
import '../models/chat.dart';
import '../sse.dart';

sealed class ChatStreamEvent {
  const ChatStreamEvent();
}

/// One streamed text chunk (whitespace preserved).
class ChatToken extends ChatStreamEvent {
  const ChatToken(this.text);
  final String text;
}

/// Final guarded response; `response.answer` is authoritative over the tokens.
class ChatDone extends ChatStreamEvent {
  const ChatDone(this.response);
  final ChatResponse response;
}

class ChatApi {
  ChatApi(this._c);
  final ApiClient _c;

  Future<ChatResponse> send(ChatRequest req) async =>
      ChatResponse.fromJson(await _c.postJson('/v1/chat', body: req.toJson()));

  /// POST /v1/chat/stream: yields [ChatToken]s, then a [ChatDone].
  Stream<ChatStreamEvent> streamChat(ChatRequest req,
      {CancelToken? cancelToken}) async* {
    final body = await _c.postForStream('/v1/chat/stream', req.toJson(),
        cancelToken: cancelToken);
    await for (final ev in parseSse(body)) {
      if (ev.event == 'delta' || ev.event == 'message') {
        yield ChatToken(ev.data);
      } else if (ev.event == 'done') {
        try {
          final j = jsonDecode(ev.data);
          if (j is Map) yield ChatDone(ChatResponse.fromJson(j.cast<String, Object?>()));
        } catch (_) {/* malformed meta: ignore */}
      }
    }
  }
}
