import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/i18n/i18n.dart';

/// Nearby health facilities — hospitals, clinics and pharmacies based on the user's location.
/// Placeholder for now (coming soon); will work offline from a synced facilities dataset.
class FacilitiesPage extends ConsumerWidget {
  const FacilitiesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tProvider);
    final theme = Theme.of(context);
    final cats = [
      (Icons.local_hospital_outlined, t('fac.hospitals'), t('fac.hospitals.sub')),
      (Icons.medical_services_outlined, t('fac.clinics'), t('fac.clinics.sub')),
      (Icons.local_pharmacy_outlined, t('fac.pharmacies'), t('fac.pharmacies.sub')),
    ];
    return RefreshIndicator(
      onRefresh: () async {},
      child: ListView(
        padding: const EdgeInsets.all(16),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: theme.colorScheme.primary,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.place_outlined, color: theme.colorScheme.onPrimary, size: 36),
                const SizedBox(height: 10),
                Text(t('fac.title'),
                    style: theme.textTheme.titleLarge
                        ?.copyWith(color: theme.colorScheme.onPrimary, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Text(t('fac.body'),
                    style: theme.textTheme.bodyMedium
                        ?.copyWith(color: theme.colorScheme.onPrimary.withValues(alpha: 0.92))),
                const SizedBox(height: 14),
                FilledButton.tonalIcon(
                  onPressed: null, // coming soon
                  icon: const Icon(Icons.my_location),
                  label: Text(t('fac.useLocation')),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerLeft,
            child: Chip(
              avatar: const Icon(Icons.schedule, size: 18),
              label: Text(t('fac.soon')),
            ),
          ),
          const SizedBox(height: 8),
          for (final c in cats)
            Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: theme.colorScheme.secondaryContainer,
                  child: Icon(c.$1, color: theme.colorScheme.onSecondaryContainer),
                ),
                title: Text(c.$2, style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(c.$3),
                trailing: const Icon(Icons.chevron_right),
                onTap: null,
              ),
            ),
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(t('fac.offline'),
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          ),
        ],
      ),
    );
  }
}
