class Citation {
  const Citation({required this.id, this.documentId, this.title, this.page, this.score});

  final String id;
  final String? documentId;
  final String? title;
  final int? page;
  final double? score;

  factory Citation.fromJson(Map<String, Object?> j) => Citation(
        id: (j['id'] as String?) ?? '',
        documentId: j['document_id'] as String?,
        title: j['title'] as String?,
        page: (j['page'] as num?)?.toInt(),
        score: (j['score'] as num?)?.toDouble(),
      );
}

class SafetyFlags {
  const SafetyFlags({
    this.crisis = false,
    this.needsReferral = false,
    this.inKnowledge,
    this.guardReason,
    this.category,
    this.flags = const [],
  });

  final bool crisis;
  final bool needsReferral;
  final bool? inKnowledge;
  final String? guardReason;
  final String? category;
  final List<String> flags;

  factory SafetyFlags.fromJson(Map<String, Object?> j) => SafetyFlags(
        crisis: j['crisis'] == true,
        needsReferral: j['needs_referral'] == true,
        inKnowledge: j['in_knowledge'] as bool?,
        guardReason: j['guard_reason'] as String?,
        category: j['category'] as String?,
        flags: ((j['flags'] as List?) ?? const []).whereType<String>().toList(),
      );
}

List<Citation> _citations(Object? v) => ((v as List?) ?? const [])
    .whereType<Map<dynamic, dynamic>>()
    .map((m) => Citation.fromJson(m.cast<String, Object?>()))
    .toList();

SafetyFlags _flags(Object? v) => v is Map
    ? SafetyFlags.fromJson(v.cast<String, Object?>())
    : const SafetyFlags();

class ChatRequest {
  const ChatRequest({required this.message, this.conversationId, this.language});
  final String message;
  final String? conversationId;
  final String? language;

  Map<String, Object?> toJson() => {
        'message': message,
        if (conversationId != null) 'conversation_id': conversationId,
        if (language != null) 'language': language,
      };
}

class ChatResponse {
  const ChatResponse({
    required this.answer,
    required this.citations,
    required this.conversationId,
    required this.safetyFlags,
    required this.language,
  });

  final String answer;
  final List<Citation> citations;
  final String conversationId;
  final SafetyFlags safetyFlags;
  final String language;

  factory ChatResponse.fromJson(Map<String, Object?> j) => ChatResponse(
        answer: (j['answer'] as String?) ?? '',
        citations: _citations(j['citations']),
        conversationId: (j['conversation_id'] as String?) ?? '',
        safetyFlags: _flags(j['safety_flags']),
        language: (j['language'] as String?) ?? 'en',
      );
}

class VoiceResponse {
  const VoiceResponse({
    required this.transcript,
    required this.answer,
    required this.citations,
    required this.safetyFlags,
    required this.conversationId,
    required this.language,
    required this.audioBase64,
    required this.audioMime,
    required this.ttsAvailable,
  });

  final String transcript;
  final String answer;
  final List<Citation> citations;
  final SafetyFlags safetyFlags;
  final String conversationId;
  final String language;
  final String audioBase64;
  final String audioMime;
  final bool ttsAvailable;

  factory VoiceResponse.fromJson(Map<String, Object?> j) => VoiceResponse(
        transcript: (j['transcript'] as String?) ?? '',
        answer: (j['answer'] as String?) ?? '',
        citations: _citations(j['citations']),
        safetyFlags: _flags(j['safety_flags']),
        conversationId: (j['conversation_id'] as String?) ?? '',
        language: (j['language'] as String?) ?? 'en',
        audioBase64: (j['audio_base64'] as String?) ?? '',
        audioMime: (j['audio_mime'] as String?) ?? '',
        ttsAvailable: j['tts_available'] != false,
      );
}

class TranscribeResponse {
  const TranscribeResponse({required this.text, this.language});
  final String text;
  final String? language;

  factory TranscribeResponse.fromJson(Map<String, Object?> j) =>
      TranscribeResponse(
          text: (j['text'] as String?) ?? '', language: j['language'] as String?);
}
