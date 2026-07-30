import 'package:flutter/material.dart';

import '../../admin/admin_models.dart';
import '../../admin/admin_repository.dart';
import '../bixolon_theme_extension.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({
    required this.repository,
    required this.range,
    this.onAttentionSelected,
    super.key,
  });

  final AdminRepository repository;
  final DateRange range;
  final ValueChanged<AttentionItem>? onAttentionSelected;

  @override
  Widget build(BuildContext context) => StreamBuilder<AdminDashboardSummary>(
    stream: repository.watchDashboard(range),
    builder: (context, snapshot) {
      if (!snapshot.hasData) {
        return const Center(child: CircularProgressIndicator());
      }
      final summary = snapshot.requireData;
      return ListView(
        children: [
          Wrap(
            spacing: 16,
            runSpacing: 16,
            children: [
              _MetricCard(
                label: '결제 완료',
                value: '${summary.completedOrders}건',
                icon: Icons.receipt_long_outlined,
              ),
              _MetricCard(
                label: '결제 금액',
                value: _krw(summary.grossKrw),
                icon: Icons.payments_outlined,
              ),
              _MetricCard(
                label: '확인 필요',
                value: '${summary.unresolvedAttentionCount}건',
                icon: Icons.priority_high_outlined,
                tone: _Tone.attention,
              ),
              const _MetricCard(
                label: '시스템 상태',
                value: '확인됨',
                icon: Icons.check_circle_outline,
                tone: _Tone.ok,
              ),
            ],
          ),
          const SizedBox(height: 32),
          Text('운영 지표', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _RateCard('재촬영', summary.retakeRate),
              _RateCard('AI 미확정', summary.unknownRate),
              _RateCard('자동 결과 변경', summary.overrideRate),
              _RateCard('직접 담기', summary.manualEntryRate),
              _RateCard('실패', summary.failureRate),
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
              return Card(
                child: Column(
                  children: [
                    for (final item in items)
                      ListTile(
                        leading: const Icon(Icons.arrow_forward),
                        title: Text(item.label),
                        subtitle: Text(item.sessionId),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: onAttentionSelected == null
                            ? null
                            : () => onAttentionSelected!(item),
                      ),
                  ],
                ),
              );
            },
          ),
        ],
      );
    },
  );
}

enum _Tone { normal, ok, attention }

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.label,
    required this.value,
    required this.icon,
    this.tone = _Tone.normal,
  });
  final String label;
  final String value;
  final IconData icon;
  final _Tone tone;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final color = switch (tone) {
      _Tone.ok => tokens.confirmed,
      _Tone.attention => tokens.uncertainty,
      _ => tokens.ink,
    };
    return SizedBox(
      width: 210,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color),
              const SizedBox(height: 20),
              Text(label),
              const SizedBox(height: 6),
              Text(
                value,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: color,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RateCard extends StatelessWidget {
  const _RateCard(this.label, this.rate);
  final String label;
  final MetricRate rate;
  @override
  Widget build(BuildContext context) => SizedBox(
    width: 180,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label),
            const SizedBox(height: 8),
            Text(
              '${rate.numerator} / ${rate.denominator}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
        ),
      ),
    ),
  );
}

String _krw(int value) {
  final digits = value.toString();
  final chunks = <String>[];
  for (var end = digits.length; end > 0; end -= 3) {
    chunks.add(digits.substring(end >= 3 ? end - 3 : 0, end));
  }
  return '${chunks.reversed.join(',')}원';
}
