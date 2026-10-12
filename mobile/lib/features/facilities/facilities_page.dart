import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/i18n/i18n.dart';
import '../../data/models/facility.dart';
import '../../state/auth.dart';

const _cacheKey = 'facilities_cache_v1';

IconData _iconFor(String type) => switch (type) {
      'hospital' => Icons.local_hospital_outlined,
      'pharmacy' => Icons.local_pharmacy_outlined,
      'clinic' => Icons.medical_services_outlined,
      _ => Icons.medical_information_outlined,
    };

/// Nearby health facilities — hospitals, clinics, health centres and pharmacies, sorted by
/// distance from the user's location. Works offline from a cached copy, with call + directions.
class FacilitiesPage extends ConsumerStatefulWidget {
  const FacilitiesPage({super.key});
  @override
  ConsumerState<FacilitiesPage> createState() => _FacilitiesPageState();
}

class _FacilitiesPageState extends ConsumerState<FacilitiesPage> {
  List<Facility> _all = const [];
  bool _loading = true;
  bool _offline = false;
  bool _noLocation = false;
  String _type = 'all';

  @override
  void initState() {
    super.initState();
    _loadCache();
    _refresh();
  }

  void _loadCache() {
    final raw = readPref(ref.read(prefsProvider), _cacheKey);
    if (raw == null) return;
    try {
      final list = (jsonDecode(raw) as List)
          .map((e) => Facility.fromJson((e as Map).cast<String, Object?>()))
          .toList();
      setState(() => _all = list);
    } catch (_) {}
  }

  Future<Position?> _position() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return null;
      var p = await Geolocator.checkPermission();
      if (p == LocationPermission.denied) p = await Geolocator.requestPermission();
      if (p == LocationPermission.denied || p == LocationPermission.deniedForever) return null;
      return await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium));
    } catch (_) {
      return null;
    }
  }

  Future<void> _refresh() async {
    setState(() => _loading = _all.isEmpty);
    final pos = await _position();
    if (mounted) setState(() => _noLocation = pos == null);
    try {
      final list = await ref
          .read(facilitiesApiProvider)
          .list(lat: pos?.latitude, lng: pos?.longitude);
      if (!mounted) return;
      setState(() {
        _all = list;
        _offline = false;
        _loading = false;
      });
      await writePref(ref.read(prefsProvider), _cacheKey,
          jsonEncode(list.map((f) => f.toJson()).toList()));
    } catch (_) {
      if (mounted) {
        setState(() {
          _offline = true;
          _loading = false;
        });
      }
    }
  }

  Future<void> _call(String phone) async {
    final uri = Uri(scheme: 'tel', path: phone);
    if (await canLaunchUrl(uri)) await launchUrl(uri);
  }

  Future<void> _directions(Facility f) async {
    if (f.lat == null || f.lng == null) return;
    final uri = Uri.parse(
        'https://www.google.com/maps/dir/?api=1&destination=${f.lat},${f.lng}');
    if (await canLaunchUrl(uri)) await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tProvider);
    final theme = Theme.of(context);
    final shown = _type == 'all' ? _all : _all.where((f) => f.type == _type).toList();
    final filters = <(String, String)>[
      ('all', t('fac.all')),
      ('hospital', t('fac.hospitals')),
      ('health_center', t('fac.clinics')),
      ('pharmacy', t('fac.pharmacies')),
    ];

    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Text(t('fac.title'),
              style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(t('fac.body2'), style: theme.textTheme.bodyMedium
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          const SizedBox(height: 12),
          if (_offline)
            _banner(theme, Icons.wifi_off, t('fac.offlineMode'), theme.colorScheme.tertiaryContainer),
          if (_noLocation && !_offline)
            _banner(theme, Icons.location_off, t('fac.noLocation'), theme.colorScheme.secondaryContainer),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final f in filters) ...[
                  ChoiceChip(
                    label: Text(f.$2),
                    selected: _type == f.$1,
                    onSelected: (_) => setState(() => _type = f.$1),
                  ),
                  const SizedBox(width: 8),
                ],
              ],
            ),
          ),
          const SizedBox(height: 8),
          if (_loading)
            const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()))
          else if (shown.isEmpty)
            Padding(padding: const EdgeInsets.all(24), child: Center(child: Text(t('fac.empty'))))
          else
            for (final f in shown) _facilityCard(f, theme, t),
        ],
      ),
    );
  }

  Widget _banner(ThemeData theme, IconData icon, String text, Color bg) => Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
        child: Row(children: [
          Icon(icon, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: theme.textTheme.bodySmall)),
        ]),
      );

  Widget _facilityCard(Facility f, ThemeData theme, T t) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    backgroundColor: theme.colorScheme.secondaryContainer,
                    child: Icon(_iconFor(f.type), color: theme.colorScheme.onSecondaryContainer),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(f.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                        if (f.address != null || f.district != null)
                          Text([f.address, f.district].where((e) => e != null).join(' · '),
                              style: theme.textTheme.bodySmall
                                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                        if (f.hours != null)
                          Text(f.hours!, style: theme.textTheme.bodySmall),
                      ],
                    ),
                  ),
                  if (f.distanceKm != null)
                    Chip(
                      visualDensity: VisualDensity.compact,
                      label: Text('${f.distanceKm!.toStringAsFixed(f.distanceKm! < 10 ? 1 : 0)} km'),
                    ),
                ],
              ),
              if (f.services.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  for (final s in f.services.take(4))
                    Chip(
                      visualDensity: VisualDensity.compact,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      label: Text(s.replaceAll('_', ' '), style: theme.textTheme.bodySmall),
                    ),
                ]),
              ],
              const SizedBox(height: 6),
              Row(children: [
                if (f.phone != null)
                  TextButton.icon(
                    onPressed: () => _call(f.phone!),
                    icon: const Icon(Icons.call, size: 18),
                    label: Text(t('fac.call')),
                  ),
                if (f.lat != null && f.lng != null)
                  TextButton.icon(
                    onPressed: () => _directions(f),
                    icon: const Icon(Icons.directions, size: 18),
                    label: Text(t('fac.directions')),
                  ),
              ]),
            ],
          ),
        ),
      );
}
