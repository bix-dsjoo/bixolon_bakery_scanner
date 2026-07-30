import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:bakery_camera_prototype/src/ui/evaluation_view_data.dart';
import 'package:bakery_camera_prototype/src/ui/presentation_state.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  test(
    'unresolved objects are risk ordered without renumbering image objects',
    () {
      final data = EvaluationPanelData.fromState(
        _state(result: buildOrderingInferenceResult()),
      );

      expect(data.rows.map((row) => row.object.isUnknown), [true, true, false]);
      expect(data.rows.map((row) => row.displayNumber), [3, 2, 1]);
      expect(data.rows.map((row) => row.decisionScore), [0.21, 0.45, 0.91]);
      expect(data.confirmedCount + data.unknownCount, data.totalCount);
    },
  );

  test('quantity rows omit unresolved objects and retain confirmed names', () {
    final data = EvaluationPanelData.fromState(
      _state(result: buildOrderingInferenceResult()),
    );

    expect(data.quantityRows, [
      const EvaluationQuantityRow(skuId: 1, name: 'Pastry Bread', count: 1),
    ]);
  });

  test('worker candidate IDs alone control candidate visibility', () {
    final data = EvaluationPanelData.fromState(
      _state(result: buildUiInferenceResult()),
    );

    expect(
      data.rows
          .singleWhere((row) => row.object.objectId == 'object-1')
          .showCandidates,
      isFalse,
    );
    expect(
      data.rows
          .singleWhere((row) => row.object.objectId == 'object-2')
          .showCandidates,
      isTrue,
    );
  });

  test('weak Unknown hides candidates without Dart confidence tests', () {
    final data = EvaluationPanelData.fromState(
      _state(
        result: buildUiInferenceResult(
          presentation: buildPresentationJson(
            state: 'needs_retake',
            finalCountUsable: false,
            retakeScope: 'object',
            retakeObjectIds: const ['object-2'],
            instructionCode: 'candidate_evidence_weak',
          ),
        ),
      ),
    );
    final unknownRow = data.rows.singleWhere(
      (row) => row.object.objectId == 'object-2',
    );

    expect(data.presentation.finalCountUsable, isFalse);
    expect(unknownRow.object.candidates, hasLength(3));
    expect(unknownRow.showCandidates, isFalse);
    expect(data.presentation.primaryInstruction, '빵이 잘 보이도록 다시 촬영해 주세요');
  });

  test('retake instructions map to exact UI-only Korean copy', () {
    expect(
      instructionFor(RetakeInstruction.noBreadDetected),
      '빵을 찾지 못했어요. 빵이 모두 보이도록 다시 촬영해 주세요',
    );
    expect(
      instructionFor(RetakeInstruction.separateBreads),
      '빵 사이 간격을 두고 다시 촬영해 주세요',
    );
    expect(
      instructionFor(RetakeInstruction.candidateEvidenceWeak),
      '빵이 잘 보이도록 다시 촬영해 주세요',
    );
  });

  test(
    'decision paths use evaluator language and reject unknown contracts',
    () {
      expect(decisionPathLabel('repvit_direct'), '첫 분석에서 확정');
      expect(decisionPathLabel('dinov3_confirmed'), '추가 확인 후 확정');
      expect(decisionPathLabel('fusion_ranked'), '추가 확인 후 확정');
      expect(decisionPathLabel('unknown_top3'), '알 수 없음');
      expect(() => decisionPathLabel('silent_guess'), throwsArgumentError);
    },
  );

  test('zero conditional recheck time is shown as not invoked', () {
    final data = EvaluationPanelData.fromState(
      _state(result: buildOrderingInferenceResult()),
    );

    final dino = data.stageTimings.singleWhere(
      (timing) => timing.label == '재확인 · DINOv3',
    );
    expect(dino.displayValue, '실행 안 함');
  });
}

ScannerState _state({required InferenceResult result}) =>
    ScannerState.initial().copyWith(
      cameraReady: true,
      workerStatus: WorkerStatus.ready,
      device: result.device,
      result: result,
      captureMs: 18.0,
      pressToRenderedResultMs: 420.0,
      selectedObjectId: 'object-3',
      phase: ScannerPhase.result,
    );
