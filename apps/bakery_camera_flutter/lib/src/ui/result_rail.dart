import 'package:flutter/material.dart';

import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'app_theme.dart';
import 'bixolon_brand.dart';
import 'evaluation_object_list.dart';
import 'evaluation_summary.dart';
import 'evaluation_view_data.dart';

final class ResultRail extends StatelessWidget {
  const ResultRail({
    super.key,
    required this.state,
    required this.elapsedMs,
    required this.onSelectObject,
  });

  final ScannerState state;
  final double elapsedMs;
  final ValueChanged<String?> onSelectObject;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    key: const Key('result-rail-surface'),
    decoration: const BoxDecoration(color: resultPaper),
    child: SingleChildScrollView(
      key: const Key('result-scroll'),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      child: _ResultContent(
        state: state,
        elapsedMs: elapsedMs,
        onSelectObject: onSelectObject,
      ),
    ),
  );
}

final class _ResultContent extends StatelessWidget {
  const _ResultContent({
    required this.state,
    required this.elapsedMs,
    required this.onSelectObject,
  });

  final ScannerState state;
  final double elapsedMs;
  final ValueChanged<String?> onSelectObject;

  @override
  Widget build(BuildContext context) {
    final result = state.result;
    if (result == null) {
      return _NonResultState(state: state, elapsedMs: elapsedMs);
    }

    final data = EvaluationPanelData.fromState(state);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        EvaluationSummary(data: data),
        const SizedBox(height: 18),
        if (data.rows.isEmpty)
          const _EmptyDetection()
        else ...[
          Text('대상별 결과', style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          EvaluationObjectList(
            rows: data.rows,
            selectedObjectId: state.selectedObjectId,
            onSelectObject: onSelectObject,
          ),
        ],
        const SizedBox(height: 10),
        _QuantityDisclosure(data: data),
        _TimingDisclosure(data: data),
        if (data.startupMetrics case final metrics?)
          _ModelDisclosure(metrics: metrics),
      ],
    );
  }
}

final class _NonResultState extends StatelessWidget {
  const _NonResultState({required this.state, required this.elapsedMs});

  final ScannerState state;
  final double elapsedMs;

  @override
  Widget build(BuildContext context) {
    if (state.workerStatus == WorkerStatus.fatal) {
      return _FailureState(
        title: '모델을 준비하지 못했어요.',
        action: '앱을 다시 시작해 주세요.',
      );
    }
    if (state.analysisError != null) {
      return _FailureState(
        title: state.analysisError!,
        action: '트레이 위치를 확인하고 다시 촬영해 주세요.',
      );
    }
    if (!state.cameraReady && state.cameraError != null) {
      return const _FailureState(
        title: '카메라를 찾지 못했어요.',
        action: '연결을 확인한 뒤 다시 연결해 주세요.',
      );
    }
    if (state.isAnalyzing) {
      return _ProgressState(label: state.phaseLabel, elapsedMs: elapsedMs);
    }
    if (!state.cameraReady) {
      return _ProgressState(label: '카메라를 연결하고 있어요.', elapsedMs: elapsedMs);
    }
    if (state.workerStatus != WorkerStatus.ready) {
      return _ProgressState(label: '모델을 준비하고 있어요.', elapsedMs: elapsedMs);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('분석 준비', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          '트레이를 카메라 아래에 놓고 분석하기를 눌러주세요.',
          style: Theme.of(
            context,
          ).textTheme.bodyMedium?.copyWith(color: bixolonMutedInk),
        ),
      ],
    );
  }
}

final class _ProgressState extends StatelessWidget {
  const _ProgressState({required this.label, required this.elapsedMs});

  final String label;
  final double elapsedMs;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 8),
      Text(
        '${elapsedMs.round()} ms',
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: bixolonMutedInk,
          fontFeatures: tabularFigures,
        ),
      ),
    ],
  );
}

final class _FailureState extends StatelessWidget {
  const _FailureState({required this.title, required this.action});

  final String title;
  final String action;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: Theme.of(
          context,
        ).textTheme.titleLarge?.copyWith(color: failureRed),
      ),
      const SizedBox(height: 8),
      Text(action),
    ],
  );
}

final class _EmptyDetection extends StatelessWidget {
  const _EmptyDetection();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '빵을 찾지 못했어요.',
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 5),
        const Text('트레이 위치를 확인하고 다시 촬영해 주세요.'),
      ],
    ),
  );
}

final class _QuantityDisclosure extends StatelessWidget {
  const _QuantityDisclosure({required this.data});

  final EvaluationPanelData data;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    tilePadding: EdgeInsets.zero,
    childrenPadding: const EdgeInsets.only(bottom: 8),
    title: const Text('품목별 수량'),
    children: [
      for (final row in data.quantityRows)
        _MetricRow(label: row.name, value: '${row.count}'),
    ],
  );
}

final class _TimingDisclosure extends StatelessWidget {
  const _TimingDisclosure({required this.data});

  final EvaluationPanelData data;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    tilePadding: EdgeInsets.zero,
    childrenPadding: const EdgeInsets.only(bottom: 8),
    title: const Text('단계별 시간'),
    children: [
      for (final timing in data.stageTimings)
        _MetricRow(label: timing.label, value: timing.displayValue),
    ],
  );
}

final class _ModelDisclosure extends StatelessWidget {
  const _ModelDisclosure({required this.metrics});

  final StartupMetrics metrics;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    tilePadding: EdgeInsets.zero,
    childrenPadding: const EdgeInsets.only(bottom: 8),
    title: const Text('모델 정보'),
    children: [
      _MetricRow(label: '모델 로드', value: '${metrics.loadMs.round()} ms'),
      _MetricRow(label: '워밍업', value: '${metrics.warmupMs.round()} ms'),
      _MetricRow(label: 'Detector', value: metrics.detectorId),
      _MetricRow(label: 'Classifier', value: metrics.repvitId),
      _MetricRow(label: '재확인', value: metrics.dinov3Id),
      _MetricRow(label: '정책', value: metrics.fusionPolicyId),
    ],
  );
}

final class _MetricRow extends StatelessWidget {
  const _MetricRow({required this.label, required this.value});

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
