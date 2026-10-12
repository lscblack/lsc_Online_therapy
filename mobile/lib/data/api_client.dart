import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../core/config.dart';
import 'models/token_pair.dart';
import 'token_store.dart';

/// Backend error (envelope `{error:{code,message}}`) or client-side failure.
/// `status == 0` means no HTTP response (e.g. code `offline`).
class ApiError implements Exception {
  const ApiError(this.code, this.message, this.status);
  final String code;
  final String message;
  final int status;

  bool get isOffline => code == 'offline';

  @override
  String toString() => 'ApiError($code, $status): $message';
}

enum AuthMode { none, user }

typedef FormBuilder = FormData Function();

class ApiClient {
  ApiClient({required this.tokens, Dio? dio, String? baseUrl})
      : _dio = (dio ?? Dio()) {
    _dio.options.baseUrl = baseUrl ?? apiBase;
    _dio.options.validateStatus = (int? _) => true;
  }

  final TokenStore tokens;
  final Dio _dio;
  Future<bool>? _refreshing;

  /// Called after the refresh token was definitively rejected and tokens cleared.
  void Function()? onAuthExpired;

  // ---- public helpers ----------------------------------------------------

  Future<Map<String, Object?>> getJson(String path,
          {AuthMode auth = AuthMode.user}) =>
      _json('GET', path, auth: auth);

  Future<Map<String, Object?>> postJson(String path,
          {Object? body, AuthMode auth = AuthMode.user}) =>
      _json('POST', path, body: body, auth: auth);

  Future<Map<String, Object?>> putJson(String path, {Object? body}) =>
      _json('PUT', path, body: body);

  /// Sends a request and returns the decoded JSON object ({} for empty bodies).
  Future<Map<String, Object?>> _json(String method, String path,
      {Object? body, FormBuilder? form, AuthMode auth = AuthMode.user}) async {
    final res = await send(method, path,
        body: body, form: form, auth: auth, responseType: ResponseType.bytes);
    final text = _text(res.data);
    if (text.isEmpty) return const {};
    try {
      final j = jsonDecode(text);
      if (j is Map) return j.cast<String, Object?>();
    } catch (_) {}
    throw ApiError('bad_response', 'Server returned an unexpected response', res.statusCode ?? 0);
  }

  /// GET a JSON array (e.g. /v1/facilities). Returns [] for an empty body.
  Future<List<Object?>> getJsonList(String path, {AuthMode auth = AuthMode.user}) async {
    final res = await send('GET', path, auth: auth, responseType: ResponseType.bytes);
    final text = _text(res.data);
    if (text.isEmpty) return const [];
    try {
      final j = jsonDecode(text);
      if (j is List) return j;
    } catch (_) {}
    throw ApiError('bad_response', 'Server returned an unexpected response', res.statusCode ?? 0);
  }

  Future<Map<String, Object?>> postForm(String path, FormBuilder form) =>
      _json('POST', path, form: form);

  Future<void> delete(String path) async {
    await send('DELETE', path, responseType: ResponseType.bytes);
  }

  Future<Uint8List> postForBytes(String path, Object body) async {
    final res = await send('POST', path,
        body: body,
        responseType: ResponseType.bytes,
        headers: {'Accept': 'audio/*'});
    final d = res.data;
    return d is Uint8List ? d : Uint8List.fromList((d as List<int>?) ?? const []);
  }

  /// POST returning the raw byte stream (for SSE). Errors are thrown as ApiError.
  Future<Stream<List<int>>> postForStream(String path, Object body,
      {CancelToken? cancelToken}) async {
    final res = await send('POST', path,
        body: body,
        responseType: ResponseType.stream,
        headers: {'Accept': 'text/event-stream'},
        cancelToken: cancelToken);
    final rb = res.data as ResponseBody;
    return rb.stream;
  }

  // ---- core --------------------------------------------------------------

  /// Sends with auth + one refresh-on-401 retry. Throws [ApiError] on non-2xx.
  Future<Response<Object?>> send(
    String method,
    String path, {
    Object? body,
    FormBuilder? form,
    AuthMode auth = AuthMode.user,
    ResponseType responseType = ResponseType.bytes,
    Map<String, String>? headers,
    CancelToken? cancelToken,
  }) async {
    final used = auth == AuthMode.user ? (await tokens.readUser())?.accessToken : null;
    var res = await _once(method, path, body, form, auth, responseType, headers,
        cancelToken, used);
    if (res.statusCode == 401 && auth == AuthMode.user) {
      final cur = await tokens.readUser();
      if (cur != null) {
        await _drain(res);
        // Token already rotated by a concurrent refresh: just retry with it.
        if (cur.accessToken != used || await _refresh(cur)) {
          res = await _once(method, path, body, form, auth, responseType, headers,
              cancelToken, (await tokens.readUser())?.accessToken);
        } else {
          throw const ApiError('auth_expired', 'Session expired', 401);
        }
      }
    }
    final code = res.statusCode ?? 0;
    if (code < 200 || code >= 300) throw await _toError(res);
    return res;
  }

  Future<Response<Object?>> _once(
      String method,
      String path,
      Object? body,
      FormBuilder? form,
      AuthMode auth,
      ResponseType responseType,
      Map<String, String>? headers,
      CancelToken? cancelToken,
      String? token) async {
    try {
      return await _dio.request<Object?>(
        path,
        data: form != null ? form() : body,
        cancelToken: cancelToken,
        options: Options(
          method: method,
          responseType: responseType,
          headers: {
            'Accept': 'application/json',
            ...?headers,
            if (token != null) 'Authorization': 'Bearer $token',
          },
          contentType: form != null
              ? null
              : (body != null ? Headers.jsonContentType : null),
        ),
      );
    } on DioException catch (e) {
      if (e.type == DioExceptionType.cancel) {
        throw const ApiError('cancelled', 'Request cancelled', 0);
      }
      throw const ApiError('offline', 'Network unreachable', 0);
    }
  }

  static String _text(Object? d) {
    if (d is List<int>) return utf8.decode(d, allowMalformed: true);
    if (d is String) return d;
    return '';
  }

  Future<void> _drain(Response<Object?> res) async {
    final d = res.data;
    if (d is ResponseBody) {
      try {
        await d.stream.drain<void>();
      } catch (_) {}
    }
  }

  Future<ApiError> _toError(Response<Object?> res) async {
    final status = res.statusCode ?? 0;
    String text = '';
    final d = res.data;
    try {
      if (d is ResponseBody) {
        final b = BytesBuilder();
        await for (final c in d.stream) {
          b.add(c);
        }
        text = utf8.decode(b.toBytes(), allowMalformed: true);
      } else {
        text = _text(d);
      }
      final j = jsonDecode(text);
      if (j is Map && j['error'] is Map) {
        final e = (j['error'] as Map);
        final code = e['code'];
        if (code is String) {
          return ApiError(code, (e['message'] as String?) ?? 'Request failed', status);
        }
      }
    } catch (_) {}
    return ApiError('error', 'Request failed', status);
  }

  /// Explicit refresh via the shared single-flight path. Returns the new pair;
  /// throws ApiError('auth_expired') if rejected, other ApiError if transient.
  Future<TokenPair> refreshNow() async {
    final cur = await tokens.readUser();
    if (cur == null) throw const ApiError('auth_expired', 'Session expired', 401);
    if (!await _refresh(cur)) {
      throw const ApiError('auth_expired', 'Session expired', 401);
    }
    final t = await tokens.readUser();
    if (t == null) throw const ApiError('auth_expired', 'Session expired', 401);
    return t;
  }

  /// Single-flight refresh. true = new tokens stored; false = definitively
  /// rejected (tokens cleared). Throws ApiError on transient failure (tokens kept).
  Future<bool> _refresh(TokenPair cur) {
    final inflight = _refreshing;
    if (inflight != null) return inflight;
    final p = _doRefresh(cur).whenComplete(() => _refreshing = null);
    _refreshing = p;
    return p;
  }

  Future<bool> _doRefresh(TokenPair cur) async {
    final res = await _once('POST', '/v1/identity/refresh',
        {'refresh_token': cur.refreshToken}, null, AuthMode.none,
        ResponseType.bytes, null, null, null);
    final code = res.statusCode ?? 0;
    if (code == 400 || code == 401 || code == 403) {
      await tokens.clearUser();
      onAuthExpired?.call();
      return false;
    }
    if (code < 200 || code >= 300) throw await _toError(res);
    Object? j;
    try {
      j = jsonDecode(_text(res.data));
    } catch (_) {}
    final pair = j is Map ? TokenPair.tryParse(j.cast<String, Object?>()) : null;
    if (pair == null) {
      throw ApiError('bad_response', 'Malformed refresh response', code);
    }
    await tokens.writeUser(pair);
    return true;
  }
}
