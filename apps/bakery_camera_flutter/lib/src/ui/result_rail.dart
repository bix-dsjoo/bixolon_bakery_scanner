import 'package:flutter/material.dart';

import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'app_theme.dart';
import 'bixolon_brand.dart';

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
    decoration: const BoxDecoration(
      color: resultPaper,
      border: Border(top: BorderSide(color: bixolonOrange, width: 3)),
    ),
    child: Padding(
      padding: const EdgeInsets.fromLTRB(22, 16, 22, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'SCAN RESULT',
            style: TextStyle(
              color: bixolonMutedInk,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: SingleChildScrollView(
              key: const Key('result-scroll'),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _Headline(state: state, elapsedMs: elapsedMs),
                  if (state.result case final result?) ...[
                    const SizedBox(height: 22),
                    _Counts(result: result),
                    const SizedBox(height: 22),
                    Text(
                      '대상별 결과',
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                    const SizedBox(height: 6),
                    if (result.objects.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Text('감지된 빵이 없습니다'),
                      )
                    else
                      for (final object in result.objects)
                        _ObjectRow(
                          object: object,
                          selected: object.objectId == state.selectedObjectId,
                          onTap: () => onSelectObject(object.objectId),
                        ),
                    const Divider(height: 32),
                    _TimingDisclosure(state: state),
                  ],
                  if (state.startupMetrics != null) ...[
                    if (state.result == null) const Divider(height: 32),
                    _ModelDisclosure(metrics: state.startupMetrics!),
                  ],
                  const SizedBox(height: 18),
                ],
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

final class _Headline extends StatelessWidget {
  const _Headline({required this.state, required this.elapsedMs});

  final ScannerState state;
  final double elapsedMs;

  @override
  Widget build(BuildContext context) {
    final result = state.result;
    if (result != null) {
      final displayMs = state.pressToRenderedResultMs ?? result.timings.totalMs;
      return Text(
        '총 ${result.objects.length}개 · ${displayMs.round()} ms · '
        '${_deviceLabel(result.device)}',
        style: Theme.of(
          context,
        ).textTheme.headlineSmall?.copyWith(fontFeatures: tabularFigures),
      );
    }
    if (state.workerStatus == WorkerStatus.fatal) {
      return _FailureHeadline(
        title: '모델을 준비하지 못했습니다',
        detail: state.workerError,
      );
    }
    if (state.analysisError != null) {
      return _FailureHeadline(title: state.analysisError!, detail: null);
    }
    if (!state.cameraReady && state.cameraError != null) {
      return _FailureHeadline(
        title: '카메라를 찾지 못했습니다',
        detail: state.cameraError,
      );
    }
    if (!state.cameraReady) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '카메라를 연결하고 있습니다',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 6),
          _Elapsed(value: elapsedMs),
        ],
      );
    }
    if (state.isAnalyzing) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            state.phaseLabel,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 6),
          _Elapsed(value: elapsedMs),
        ],
      );
    }
    if (state.workerStatus != WorkerStatus.ready) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '모델을 준비하고 있습니다',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 6),
          _Elapsed(value: elapsedMs),
        ],
      );
    }
    return Text('분석 준비', style: Theme.of(context).textTheme.headlineSmall);
  }
}

final class _Elapsed extends StatelessWidget {
  const _Elapsed({required this.value});

  final double value;

  @override
  Widget build(BuildContext context) => Text(
    '${value.round()} ms',
    style: Theme.of(context).textTheme.titleMedium?.copyWith(
      color: const Color(0xFF67717C),
      fontFeatures: tabularFigures,
    ),
  );
}

final class _FailureHeadline extends StatelessWidget {
  const _FailureHeadline({required this.title, required this.detail});

  final String title;
  final String? detail;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: Theme.of(
          context,
        ).textTheme.headlineSmall?.copyWith(color: failureRed),
      ),
      if (detail != null && detail != title) ...[
        const SizedBox(height: 8),
        Text(detail!, style: Theme.of(context).textTheme.bodyMedium),
      ],
    ],
  );
}

final class _Counts extends StatelessWidget {
  const _Counts({required this.result});

  final InferenceResult result;

  @override
  Widget build(BuildContext context) {
    final names = <int, String>{
      for (final object in result.objects)
        if (object.skuId != null) object.skuId!: object.skuName,
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('품목별 수량', style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 8),
        for (final entry in result.counts.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: 5),
            child: Row(
              children: [
                Expanded(child: Text(names[entry.key] ?? 'SKU ${entry.key}')),
                Text(
                  '${entry.value}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontFeatures: tabularFigures,
                  ),
                ),
              ],
            ),
          ),
        if (result.unknownCount > 0)
          Row(
            children: [
              const Expanded(
                child: Text('Unknown', style: TextStyle(color: unknownAmber)),
              ),
              Text(
                '${result.unknownCount}',
                style: const TextStyle(
                  color: unknownAmber,
                  fontWeight: FontWeight.w700,
                  fontFeatures: tabularFigures,
                ),
              ),
            ],
          ),
      ],
    );
  }
}

final class _ObjectRow extends StatefulWidget {
  const _ObjectRow({
    required this.object,
    required this.selected,
    required this.onTap,
  });

  final InferenceObject object;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_ObjectRow> createState() => _ObjectRowState();
}

final class _ObjectRowState extends State<_ObjectRow> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final object = widget.object;
    final color = object.isUnknown ? unknownAmber : confirmedTeal;
    return Semantics(
      selected: widget.selected,
      button: true,
      label: '${object.skuName} 결과 보기',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          key: Key('object-row-${object.objectId}'),
          onTap: widget.onTap,
          onFocusChange: (focused) => setState(() => _focused = focused),
          focusColor: Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            key: Key('object-row-surface-${object.objectId}'),
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
            margin: const EdgeInsets.only(bottom: 4),
            decoration: BoxDecoration(
              color: _focused
                  ? actionBlue.withValues(alpha: 0.08)
                  : widget.selected
                  ? bixolonOrange.withValues(alpha: 0.08)
                  : null,
              border: _focused
                  ? Border.all(color: actionBlue, width: 2)
                  : Border(
                      left: BorderSide(
                        color: color,
                        width: widget.selected ? 4 : 2,
                      ),
                    ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        object.skuName,
                        style: Theme.of(
                          context,
                        ).textTheme.titleMedium?.copyWith(color: color),
                      ),
                    ),
                    Text(
                      _percentage(object.confidence),
                      style: const TextStyle(fontFeatures: tabularFigures),
                    ),
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  _decisionPath(object.decisionPath),
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: const Color(0xFF67717C),
                  ),
                ),
                if (object.isUnknown) ...[
                  const SizedBox(height: 10),
                  for (final candidate in object.candidates)
                    Padding(
                      padding: const EdgeInsets.only(top: 5),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 22,
                            child: Text(
                              '${candidate.rank}',
                              style: const TextStyle(
                                color: unknownAmber,
                                fontWeight: FontWeight.w800,
                                fontFeatures: tabularFigures,
                              ),
                            ),
                          ),
                          Expanded(child: Text(candidate.skuName)),
                          Text(
                            _percentage(candidate.score),
                            style: const TextStyle(
                              fontFeatures: tabularFigures,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

final class _TimingDisclosure extends StatelessWidget {
  const _TimingDisclosure({required this.state});

  final ScannerState state;

  @override
  Widget build(BuildContext context) {
    final timings = state.result!.timings;
    return ExpansionTile(
      title: const Text('소요 시간'),
      children: [
        _Metric('버튼→화면 표시', state.pressToRenderedResultMs),
        _Metric('촬영', state.captureMs),
        _Metric('전체 추론', timings.totalMs),
        _Metric('전처리', timings.decodePreprocessMs),
        _Metric('Detector', timings.detectorMs),
        _Metric('RepViT', timings.repvitMs),
        _Metric('DINOv3', timings.dinov3Ms),
        _Metric('후처리', timings.postprocessMs),
      ],
    );
  }
}

final class _ModelDisclosure extends StatelessWidget {
  const _ModelDisclosure({required this.metrics});

  final StartupMetrics metrics;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: const Text('모델 정보'),
    children: [
      _Metric('모델 로드', metrics.loadMs),
      _Metric('워밍업', metrics.warmupMs),
      _TextMetric('Detector', metrics.detectorId),
      _TextMetric('Classifier', metrics.repvitId),
      _TextMetric('재확인', metrics.dinov3Id),
      _TextMetric('정책', metrics.fusionPolicyId),
    ],
  );
}

final class _Metric extends StatelessWidget {
  const _Metric(this.label, this.value);

  final String label;
  final double? value;

  @override
  Widget build(BuildContext context) =>
      _TextMetric(label, value == null ? '—' : '${value!.round()} ms');
}

final class _TextMetric extends StatelessWidget {
  const _TextMetric(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
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

String _percentage(double value) => '${(value * 100).toStringAsFixed(1)}%';

String _decisionPath(String path) => switch (path) {
  'repvit_direct' => 'RepViT 직접 확정',
  'dinov3_confirmed' => 'DINOv3 재확인 확정',
  'fusion_ranked' => 'Fusion 확정',
  'unknown_top3' => 'Unknown · Top-3 후보',
  _ => path,
};

String _deviceLabel(String device) =>
    device.toLowerCase().startsWith('cuda') ? 'GPU' : 'CPU';
