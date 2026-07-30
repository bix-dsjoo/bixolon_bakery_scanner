import 'dart:collection';

import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'presentation_state.dart';

final class EvaluationPanelData {
  EvaluationPanelData._({
    required List<EvaluationObjectRow> rows,
    required this.totalCount,
    required this.confirmedCount,
    required this.unknownCount,
    required List<EvaluationQuantityRow> quantityRows,
    required List<EvaluationStageTiming> stageTimings,
    required this.pressToRenderMs,
    required this.modelInferenceMs,
    required this.deviceLabel,
    required this.startupMetrics,
    required this.presentation,
  }) : rows = UnmodifiableListView(rows),
       quantityRows = UnmodifiableListView(quantityRows),
       stageTimings = UnmodifiableListView(stageTimings);

  factory EvaluationPanelData.fromState(ScannerState state) {
    final result = state.result;
    if (result == null) {
      throw StateError('evaluation data requires an inference result');
    }
    final presentation = CameraPresentationState.fromInference(
      result.presentation,
    );

    final rows = <EvaluationObjectRow>[
      for (var index = 0; index < result.objects.length; index += 1)
        EvaluationObjectRow(
          displayNumber: index + 1,
          object: result.objects[index],
          decisionLabel: decisionPathLabel(result.objects[index].decisionPath),
          decisionScore: result.objects[index].isUnknown
              ? result.objects[index].candidates.first.score
              : result.objects[index].confidence,
          showCandidates: presentation.candidateObjectIds.contains(
            result.objects[index].objectId,
          ),
        ),
    ];
    rows.sort((a, b) {
      if (a.object.isUnknown != b.object.isUnknown) {
        return a.object.isUnknown ? -1 : 1;
      }
      if (a.object.isUnknown) {
        final scoreOrder = a.decisionScore.compareTo(b.decisionScore);
        if (scoreOrder != 0) {
          return scoreOrder;
        }
      }
      return a.displayNumber.compareTo(b.displayNumber);
    });

    final names = <int, String>{
      for (final object in result.objects)
        if (!object.isUnknown) object.skuId!: object.skuName,
    };
    final quantityRows = [
      for (final entry in result.counts.entries)
        EvaluationQuantityRow(
          skuId: entry.key,
          name: names[entry.key] ?? 'SKU ${entry.key}',
          count: entry.value,
        ),
    ];
    final timings = result.timings;
    final stageTimings = [
      EvaluationStageTiming(label: '촬영', milliseconds: state.captureMs),
      EvaluationStageTiming(
        label: '이미지 준비',
        milliseconds: timings.decodePreprocessMs,
      ),
      EvaluationStageTiming(
        label: '빵 위치 찾기 · Detector',
        milliseconds: timings.detectorMs,
      ),
      EvaluationStageTiming(
        label: '1차 품목 분류 · RepViT',
        milliseconds: timings.repvitMs,
      ),
      EvaluationStageTiming.dinov3(timings.dinov3Ms),
      EvaluationStageTiming(
        label: '결과 정리',
        milliseconds: timings.postprocessMs,
      ),
    ];

    return EvaluationPanelData._(
      rows: rows,
      totalCount: result.objects.length,
      confirmedCount: result.registeredCount,
      unknownCount: result.unknownCount,
      quantityRows: quantityRows,
      stageTimings: stageTimings,
      pressToRenderMs: state.pressToRenderedResultMs ?? result.timings.totalMs,
      modelInferenceMs: result.timings.totalMs,
      deviceLabel: inferenceDeviceLabel(result.device),
      startupMetrics: state.startupMetrics,
      presentation: presentation,
    );
  }

  final List<EvaluationObjectRow> rows;
  final int totalCount;
  final int confirmedCount;
  final int unknownCount;
  final List<EvaluationQuantityRow> quantityRows;
  final List<EvaluationStageTiming> stageTimings;
  final double pressToRenderMs;
  final double modelInferenceMs;
  final String deviceLabel;
  final StartupMetrics? startupMetrics;
  final CameraPresentationState presentation;
}

final class EvaluationObjectRow {
  const EvaluationObjectRow({
    required this.displayNumber,
    required this.object,
    required this.decisionLabel,
    required this.decisionScore,
    required this.showCandidates,
  });

  final int displayNumber;
  final InferenceObject object;
  final String decisionLabel;
  final double decisionScore;
  final bool showCandidates;
}

final class EvaluationQuantityRow {
  const EvaluationQuantityRow({
    required this.skuId,
    required this.name,
    required this.count,
  });

  final int skuId;
  final String name;
  final int count;

  @override
  bool operator ==(Object other) =>
      other is EvaluationQuantityRow &&
      other.skuId == skuId &&
      other.name == name &&
      other.count == count;

  @override
  int get hashCode => Object.hash(skuId, name, count);
}

final class EvaluationStageTiming {
  const EvaluationStageTiming({
    required this.label,
    required this.milliseconds,
    this.zeroMeansNotRun = false,
  });

  const EvaluationStageTiming.dinov3(double milliseconds)
    : this(
        label: '재확인 · DINOv3',
        milliseconds: milliseconds,
        zeroMeansNotRun: true,
      );

  final String label;
  final double? milliseconds;
  final bool zeroMeansNotRun;

  String get displayValue {
    final value = milliseconds;
    if (value == null) {
      return '—';
    }
    if (zeroMeansNotRun && value == 0) {
      return '실행 안 함';
    }
    return '${value.round()} ms';
  }
}

String decisionPathLabel(String path) => switch (path) {
  'repvit_direct' => '첫 분석에서 확정',
  'dinov3_confirmed' => '추가 확인 후 확정',
  'fusion_ranked' => '추가 확인 후 확정',
  'unknown_top3' => '알 수 없음',
  _ => throw ArgumentError.value(path, 'path', '지원하지 않는 판정 경로'),
};

String inferenceDeviceLabel(String device) =>
    device.toLowerCase().startsWith('cuda') ? 'GPU' : 'CPU';

String evaluationPercent(double value) =>
    '${(value * 100).toStringAsFixed(1)}%';
