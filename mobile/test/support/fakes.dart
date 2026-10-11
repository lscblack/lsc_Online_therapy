import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

class RecordedRequest {
  RecordedRequest(this.method, this.path, this.headers, this.body);
  final String method;
  final String path;
  final Map<String, dynamic> headers;
  final String body;
}

typedef Responder = FutureOr<ResponseBody> Function(RecordedRequest req);

/// Dio adapter driven by a closure; records every request.
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.responder);
  Responder responder;
  final List<RecordedRequest> requests = [];

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    var body = '';
    if (requestStream != null) {
      final bytes = <int>[];
      await for (final c in requestStream) {
        bytes.addAll(c);
      }
      body = utf8.decode(bytes, allowMalformed: true);
    }
    final r = RecordedRequest(
        options.method, options.path, Map.of(options.headers), body);
    requests.add(r);
    return responder(r);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody jsonBody(int status, Object? json) => ResponseBody.fromString(
      jsonEncode(json),
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );

ResponseBody offline() => throw DioException(
      requestOptions: RequestOptions(path: ''),
      type: DioExceptionType.connectionError,
    );
