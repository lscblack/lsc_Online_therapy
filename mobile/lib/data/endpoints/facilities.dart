import '../api_client.dart';
import '../models/facility.dart';

class FacilitiesApi {
  FacilitiesApi(this._c);
  final ApiClient _c;

  Future<List<Facility>> list({double? lat, double? lng, String? type, int limit = 200}) async {
    final q = <String, String>{'limit': '$limit'};
    if (lat != null && lng != null) {
      q['lat'] = lat.toStringAsFixed(6);
      q['lng'] = lng.toStringAsFixed(6);
    }
    if (type != null && type.isNotEmpty) q['type'] = type;
    final qs = q.entries.map((e) => '${e.key}=${Uri.encodeQueryComponent(e.value)}').join('&');
    final rows = await _c.getJsonList('/v1/facilities?$qs');
    return rows
        .whereType<Map>()
        .map((m) => Facility.fromJson(m.cast<String, Object?>()))
        .toList();
  }
}
