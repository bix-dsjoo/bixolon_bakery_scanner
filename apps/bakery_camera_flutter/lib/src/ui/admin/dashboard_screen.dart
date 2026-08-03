import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../admin/admin_models.dart';
import '../../admin/admin_repository.dart';
import '../bixolon_theme_extension.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({
    required this.repository,
    required this.range,
    this.onAttentionSelected,
    this.readiness,
    super.key,
  });

  final AdminRepository repository;
  final DateRange range;
  final ValueChanged<AttentionItem>? onAttentionSelected;
  final ValueListenable<DashboardAvailability>? readiness;

  @override
  Widget build(
    BuildContext context,
  ) => ValueListenableBuilder<DashboardAvailability>(
    valueListenable: readiness ?? _unknownReadiness,
    builder: (context, availability, _) => StreamBuilder<AdminDashboardSummary>(
      stream: repository.watchDashboard(range),
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final summary = snapshot.requireData;
        return ListView(
          children: [
            _MetricLedger(
              key: const ValueKey('dashboard-summary-ledger'),
              metrics: [
                _MetricData(
                  label: '결제 완료',
                  value: '${summary.completedOrders}건',
                ),
                _MetricData(label: '결제 금액', value: _krw(summary.grossKrw)),
                _MetricData(
                  label: '확인 필요',
                  value: '${summary.unresolvedAttentionCount}건',
                  tone: _Tone.attention,
                ),
                _MetricData(
                  label: '시스템 상태',
                  value: _availabilityLabel(availability),
                  tone: _availabilityTone(availability),
                ),
              ],
            ),
            const SizedBox(height: 32),
            Text('운영 지표', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            _RateLedger(
              key: const ValueKey('dashboard-rate-ledger'),
              rates: [
                ('재촬영', summary.retakeRate),
                ('AI 미확정', summary.unknownRate),
                ('자동 결과 변경', summary.overrideRate),
                ('직접 담기', summary.manualEntryRate),
                ('실패', summary.failureRate),
              ],
            ),
            const SizedBox(height: 32),
            Text('최근 확인 필요', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            FutureBuilder<List<AttentionItem>>(
              future: repository.recentAttentionItems(limit: 5),
              builder: (context, snapshot) {
                final items = snapshot.data ?? const <AttentionItem>[];
                if (items.isEmpty) return const Text('확인이 필요한 최근 기록이 없습니다.');
                return DecoratedBox(
                  decoration: BoxDecoration(
                    border: Border.symmetric(
                      horizontal: BorderSide(
                        color: BixolonThemeExtension.of(context).divider,
                      ),
                    ),
                  ),
                  child: Column(
                    children: [
                      for (var index = 0; index < items.length; index++) ...[
                        if (index > 0) const Divider(),
                        ListTile(
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 4,
                          ),
                          title: Text(items[index].label),
                          subtitle: Text(items[index].sessionId),
                          trailing: const Icon(Icons.chevron_right, size: 20),
                          onTap: onAttentionSelected == null
                              ? null
                              : () => onAttentionSelected!(items[index]),
                        ),
                      ],
                    ],
                  ),
                );
              },
            ),
          ],
        );
      },
    ),
  );
}

enum _Tone { normal, ok, attention }

/// Bridges immutable diagnostics refreshes into the dashboard's live status.
/// The controller only renders readiness; it exposes no model or policy
/// mutation surface. A scanner/worker transition triggers a new read so the
/// administrator never mistakes the default placeholder for live state.
final class DashboardReadinessController
    extends ValueNotifier<DashboardAvailability> {
  factory DashboardReadinessController.watch({
    required Future<DashboardAvailability> Function() load,
    required Listenable liveChanges,
  }) => DashboardReadinessController._(load, liveChanges);

  DashboardReadinessController._(this._load, this._liveChanges)
    : super(DashboardAvailability.unknown) {
    _liveChanges.addListener(_onLiveChange);
    unawaited(refresh());
  }

  final Future<DashboardAvailability> Function() _load;
  final Listenable _liveChanges;
  var _disposed = false;
  var _refreshGeneration = 0;

  Future<void> refresh() async {
    final generation = ++_refreshGeneration;
    try {
      final next = await _load();
      if (_disposed || generation != _refreshGeneration) return;
      value = next;
    } on Object {
      if (_disposed || generation != _refreshGeneration) return;
      value = DashboardAvailability.unavailable;
    }
  }

  void _onLiveChange() => unawaited(refresh());

  @override
  void dispose() {
    _disposed = true;
    _liveChanges.removeListener(_onLiveChange);
    super.dispose();
  }
}

final ValueNotifier<DashboardAvailability> _unknownReadiness = ValueNotifier(
  DashboardAvailability.unknown,
);

String _availabilityLabel(DashboardAvailability availability) =>
    switch (availability) {
      DashboardAvailability.unknown => '진단 전',
      DashboardAvailability.ready => '정상',
      DashboardAvailability.unavailable => '점검 필요',
    };

_Tone _availabilityTone(DashboardAvailability availability) =>
    switch (availability) {
      DashboardAvailability.unknown => _Tone.attention,
      DashboardAvailability.ready => _Tone.ok,
      DashboardAvailability.unavailable => _Tone.attention,
    };

class _MetricData {
  const _MetricData({
    required this.label,
    required this.value,
    this.tone = _Tone.normal,
  });

  final String label;
  final String value;
  final _Tone tone;
}

class _MetricLedger extends StatelessWidget {
  const _MetricLedger({required this.metrics, super.key});

  final List<_MetricData> metrics;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return LayoutBuilder(
      builder: (context, constraints) {
        final columnCount = constraints.maxWidth < 760 ? 2 : metrics.length;
        final rows = <Widget>[];
        for (var start = 0; start < metrics.length; start += columnCount) {
          final end = (start + columnCount).clamp(0, metrics.length);
          if (rows.isNotEmpty) rows.add(const Divider());
          rows.add(
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  for (var index = start; index < end; index++) ...[
                    if (index > start)
                      VerticalDivider(width: 1, color: tokens.divider),
                    Expanded(child: _MetricCell(metric: metrics[index])),
                  ],
                  for (var index = end; index < start + columnCount; index++)
                    const Expanded(child: SizedBox.shrink()),
                ],
              ),
            ),
          );
        }
        return DecoratedBox(
          decoration: BoxDecoration(
            color: tokens.paper,
            border: Border.symmetric(
              horizontal: BorderSide(color: tokens.divider),
            ),
          ),
          child: Column(children: rows),
        );
      },
    );
  }
}

class _MetricCell extends StatelessWidget {
  const _MetricCell({required this.metric});

  final _MetricData metric;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final color = switch (metric.tone) {
      _Tone.ok => tokens.confirmed,
      _Tone.attention => tokens.uncertainty,
      _ => tokens.ink,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            metric.label,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: tokens.mutedInk),
          ),
          const SizedBox(height: 6),
          Text(
            metric.value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              color: color,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

class _RateLedger extends StatelessWidget {
  const _RateLedger({required this.rates, super.key});

  final List<(String, MetricRate)> rates;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.symmetric(horizontal: BorderSide(color: tokens.divider)),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) => Wrap(
          children: [
            for (final rate in rates)
              SizedBox(
                width: constraints.maxWidth < 760
                    ? constraints.maxWidth / 2
                    : constraints.maxWidth / rates.length,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 14,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        rate.$1,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: tokens.mutedInk,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${rate.$2.numerator} / ${rate.$2.denominator}',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(
                              fontFeatures: const [
                                FontFeature.tabularFigures(),
                              ],
                            ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

String _krw(int value) {
  final digits = value.toString();
  final chunks = <String>[];
  for (var end = digits.length; end > 0; end -= 3) {
    chunks.add(digits.substring(end >= 3 ? end - 3 : 0, end));
  }
  return '${chunks.reversed.join(',')}원';
}
