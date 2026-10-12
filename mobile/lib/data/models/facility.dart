class Facility {
  const Facility({
    required this.id,
    required this.name,
    required this.type,
    this.district,
    this.lat,
    this.lng,
    this.phone,
    this.address,
    this.hours,
    this.services = const [],
    this.distanceKm,
  });

  final String id;
  final String name;
  final String type; // hospital | clinic | health_center | pharmacy
  final String? district;
  final double? lat;
  final double? lng;
  final String? phone;
  final String? address;
  final String? hours;
  final List<String> services;
  final double? distanceKm;

  static double? _d(Object? v) => v == null ? null : (v as num).toDouble();

  factory Facility.fromJson(Map<String, Object?> j) => Facility(
        id: j['id'] as String,
        name: j['name'] as String,
        type: j['type'] as String? ?? 'clinic',
        district: j['district'] as String?,
        lat: _d(j['lat']),
        lng: _d(j['lng']),
        phone: j['phone'] as String?,
        address: j['address'] as String?,
        hours: j['hours'] as String?,
        services: ((j['services'] as List?) ?? const []).map((e) => '$e').toList(),
        distanceKm: _d(j['distance_km']),
      );

  Map<String, Object?> toJson() => {
        'id': id, 'name': name, 'type': type, 'district': district, 'lat': lat, 'lng': lng,
        'phone': phone, 'address': address, 'hours': hours, 'services': services,
        'distance_km': distanceKm,
      };
}
