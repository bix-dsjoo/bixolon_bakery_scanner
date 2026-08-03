import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'bixolon_brand.dart';
import 'evaluation_view_data.dart';

final class EvaluationSummary extends StatelessWidget {
  const EvaluationSummary({super.key, required this.data});

  final EvaluationPanelData data;

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    label:
        '대상 ${data.totalCount}, 확정 ${data.confirmedCount}, '
        '알 수 없음 ${data.unknownCount}, '
        '화면 표시까지 ${data.pressToRenderMs.round()} 밀리초, '
        '모델 추론 ${data.modelInferenceMs.round()} 밀리초, '
        '${data.deviceLabel}',
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 16,
          runSpacing: 6,
          children: [
            _Count(label: '대상', value: data.totalCount),
            _Count(label: '확정', value: data.confirmedCount),
            _Count(
              label: '알 수 없음',
              value: data.unknownCount,
              color: data.unknownCount == 0 ? bixolonInk : unknownAmber,
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 16,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            _Latency(label: '화면 표시까지', milliseconds: data.pressToRenderMs),
            _Latency(label: '모델 추론', milliseconds: data.modelInferenceMs),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                color: bixolonCanvas,
                border: Border.all(color: bixolonDivider),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                data.deviceLabel,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ],
    ),
  );
}

final class _Count extends StatelessWidget {
  const _Count({
    required this.label,
    required this.value,
    this.color = bixolonInk,
  });

  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) => Text(
    '$label $value',
    style: Theme.of(context).textTheme.titleMedium?.copyWith(
      color: color,
      fontWeight: FontWeight.w700,
      fontFeatures: tabularFigures,
    ),
  );
}

final class _Latency extends StatelessWidget {
  const _Latency({required this.label, required this.milliseconds});

  final String label;
  final double milliseconds;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        label,
        style: Theme.of(
          context,
        ).textTheme.bodySmall?.copyWith(color: bixolonMutedInk),
      ),
      const SizedBox(height: 1),
      Text(
        '${milliseconds.round()} ms',
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          fontWeight: FontWeight.w700,
          fontFeatures: tabularFigures,
        ),
      ),
    ],
  );
}
