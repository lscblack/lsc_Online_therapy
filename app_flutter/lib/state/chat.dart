import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/i18n/i18n.dart';
import '../data/api_client.dart';
import '../data/endpoints/chat.dart';
import '../data/models/chat.dart';
import 'auth.dart';

enum ChatRole { user, assistant }

enum MessageStatus { streaming, done, error }

/// One chat turn entry. Message text is never logged.
class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    this.text = '',
    this.status = MessageStatus.done,
    this.citations = const [],
    this.safetyFlags = const SafetyFlags(),
  });

  final int id;
  final ChatRole role;
  final String text;
  final MessageStatus status;
  final List<Citation> citations;
  final SafetyFlags safetyFlags;

  ChatMessage copyWith({
    String? text,
    MessageStatus? status,
    List<Citation>? citations,
    SafetyFlags? safetyFlags,
  }) =>
      ChatMessage(
        id: id,
        role: role,
        text: text ?? this.text,
        status: status ?? this.status,
        citations: citations ?? this.citations,
        safetyFlags: safetyFlags ?? this.safetyFlags,
      );
}

class ChatState {
  const ChatState({this.messages = const [], this.conversationId});
  final List<ChatMessage> messages;
  final String? conversationId;

  bool get busy =>
      messages.any((m) => m.status == MessageStatus.streaming);

  ChatState copyWith({List<ChatMessage>? messages, String? conversationId}) =>
      ChatState(
          messages: messages ?? this.messages,
          conversationId: conversationId ?? this.conversationId);
}

class ChatController extends Notifier<ChatState> {
  int _next = 0;

  @override
  ChatState build() => const ChatState();

  /// Send a user message and stream the assistant's reply.
  Future<void> send(String text) async {
    final msg = text.trim();
    if (msg.isEmpty || state.busy) return;
    state = state.copyWith(messages: [
      ...state.messages,
      ChatMessage(id: _next++, role: ChatRole.user, text: msg),
    ]);
    await _runTurn(msg);
  }

  /// Re-run the turn that failed (assistant message [id]) without
  /// duplicating the user's message.
  Future<void> retry(int id) async {
    if (state.busy) return;
    final i = state.messages.indexWhere((m) => m.id == id);
    if (i <= 0 || state.messages[i].status != MessageStatus.error) return;
    final user = state.messages[i - 1];
    if (user.role != ChatRole.user) return;
    state = state.copyWith(
        messages: [...state.messages.sublist(0, i), ...state.messages.sublist(i + 1)]);
    await _runTurn(user.text);
  }

  void _update(int id, ChatMessage Function(ChatMessage) f) {
    state = state.copyWith(
        messages: [for (final m in state.messages) m.id == id ? f(m) : m]);
  }

  Future<void> _runTurn(String msg) async {
    final aid = _next++;
    state = state.copyWith(messages: [
      ...state.messages,
      ChatMessage(id: aid, role: ChatRole.assistant, status: MessageStatus.streaming),
    ]);
    final api = ref.read(chatApiProvider);
    final req = ChatRequest(
        message: msg,
        conversationId: state.conversationId,
        language: ref.read(languageProvider));

    void finish(ChatResponse r) {
      final hasText = r.answer.isNotEmpty ||
          (state.messages.where((m) => m.id == aid).firstOrNull?.text.isNotEmpty ?? false);
      if (!hasText) {
        // An empty final reply is not a clean answer.
        _update(aid, (m) => m.copyWith(status: MessageStatus.error));
        return;
      }
      _update(
          aid,
          (m) => m.copyWith(
              text: r.answer.isNotEmpty ? r.answer : m.text,
              status: MessageStatus.done,
              citations: r.citations,
              safetyFlags: r.safetyFlags));
      if (r.conversationId.isNotEmpty) {
        state = state.copyWith(conversationId: r.conversationId);
      }
    }

    var gotToken = false;
    var finished = false;
    try {
      await for (final ev in api.streamChat(req)) {
        switch (ev) {
          case ChatToken(:final text):
            gotToken = true;
            _update(aid, (m) => m.copyWith(text: m.text + text));
          case ChatDone(:final response):
            finished = true;
            finish(response);
        }
      }
      if (!finished) {
        // Connection closed before `done`: the reply (and its safety flags) may
        // be truncated, so never present it as complete. Partial text is kept.
        _update(aid, (m) => m.copyWith(status: MessageStatus.error));
      }
    } on ApiError catch (e) {
      if (!gotToken && !e.isOffline && const {404, 405, 501}.contains(e.status)) {
        try {
          finish(await api.send(req));
          return;
        } catch (_) {/* fall through to error */}
      }
      _update(aid, (m) => m.copyWith(status: MessageStatus.error));
    } catch (_) {
      _update(aid, (m) => m.copyWith(status: MessageStatus.error));
    }
  }
}

final chatProvider =
    NotifierProvider<ChatController, ChatState>(ChatController.new);
