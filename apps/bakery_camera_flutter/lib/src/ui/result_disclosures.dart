import 'package:flutter/material.dart';

import '../inference/inference_models.dart';
import 'app_theme.dart';
import 'bixolon_brand.dart';
import 'evaluation_view_data.dart';

final class QuantityDisclosure extends StatelessWidget {
  const QuantityDisclosure({super.key, required this.data});

  final EvaluationPanelData data;

  @override
  Widget build(BuildContext context) => _FlatDisclosure(
    title: '품목별 수량',
    children: data.quantityRows.isEmpty
        ? const [_EmptyValue('확정된 품목이 없습니다.')]
        : [
            for (final row in data.quantityRows)
              DisclosureMetric(label: row.name, value: '${row.count}'),
          ],
  );
}

final class StageTimingDisclosure extends StatelessWidget {
  const StageTimingDisclosure({super.key, required this.data});

  final EvaluationPanelData data;

  @override
  Widget build(BuildContext context) => _FlatDisclosure(
    title: '단계별 시간',
    children: [
      for (final timing in data.stageTimings)
        DisclosureMetric(label: timing.label, value: timing.displayValue),
    ],
  );
}

final class ModelInfoDisclosure extends StatelessWidget {
  const ModelInfoDisclosure({
    super.key,
    required this.metrics,
    required this.selectedObject,
  });

  final StartupMetrics metrics;
  final InferenceObject? selectedObject;

  @override
  Widget build(BuildContext context) => _FlatDisclosure(
    title: '모델 정보',
    children: [
      DisclosureMetric(label: '모델 로드', value: '${metrics.loadMs.round()} ms'),
      DisclosureMetric(label: '워밍업', value: '${metrics.warmupMs.round()} ms'),
      DisclosureMetric(label: '빵 위치 찾기 · Detector', value: metrics.detectorId),
      DisclosureMetric(label: '1차 품목 분류 · RepViT', value: metrics.repvitId),
      DisclosureMetric(label: '재확인 · DINOv3', value: metrics.dinov3Id),
      DisclosureMetric(label: '정책', value: metrics.fusionPolicyId),
      DisclosureMetric(
        label: 'Detector 임계값',
        value: evaluationPercent(metrics.detectorThreshold),
      ),
      if (metrics.fallbackReason != null)
        DisclosureMetric(
          label: 'CPU로 전환',
          value: _fallbackLabel(metrics.fallbackReason!),
        ),
      if (selectedObject?.isUnknown ?? false)
        DisclosureMetric(
          label: '기술 사유',
          value: selectedObject!.unknownReason ?? '사유 코드 없음',
        ),
      const Padding(
        padding: EdgeInsets.only(top: 10, bottom: 4),
        child: Text(
          '판정 점수는 모델이 품목을 선택한 상대 점수이며 '
          '실제 정확도를 의미하지 않습니다.',
          style: TextStyle(color: bixolonMutedInk, fontSize: 12, height: 1.45),
        ),
      ),
    ],
  );
}

final class _FlatDisclosure extends StatelessWidget {
  const _FlatDisclosure({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: const BoxDecoration(
      border: Border(top: BorderSide(color: bixolonDivider)),
    ),
    child: ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 8),
      shape: const Border(),
      collapsedShape: const Border(),
      title: Text(title),
      children: children,
    ),
  );
}

final class DisclosureMetric extends StatelessWidget {
  const DisclosureMetric({
    super.key,
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(label)),
        const SizedBox(width: 12),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(fontFeatures: tabularFigures),
          ),
        ),
      ],
    ),
  );
}

final class _EmptyValue extends StatelessWidget {
  const _EmptyValue(this.value);

  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Align(
      alignment: Alignment.centerLeft,
      child: Text(
        value,
        style: Theme.of(
          context,
        ).textTheme.bodyMedium?.copyWith(color: bixolonMutedInk),
      ),
    ),
  );
}

String _fallbackLabel(String reason) => switch (reason) {
  'cuda_unavailable' => 'GPU를 사용할 수 없음',
  'cuda_load_failed' => 'GPU 모델 로드 실패',
  'cuda_warmup_failed' => 'GPU 워밍업 실패',
  _ => reason,
};
