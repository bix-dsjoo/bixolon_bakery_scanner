import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses a deterministic fail-closed result contract', () {
    final result = InferenceResult.fromJson(
      _resultJson(
        requestId: 'analysis-7',
        objects: [
          _confirmedObject('object-1', skuId: 6),
          _unknownObject('object-2'),
        ],
        counts: {'6': 1},
        unknownCount: 1,
      ),
    );

    expect(result.requestId, 'analysis-7');
    expect(result.imageWidth, 640);
    expect(result.imageHeight, 480);
    expect(result.registeredCount + result.unknownCount, result.objects.length);
    expect(result.objects.first.candidates, isEmpty);
    expect(result.objects.last.candidates, hasLength(3));
    expect(result.objects.last.isUnknown, isTrue);
    expect(result.timings.totalMs, 42.0);
  });

  test('requires eight timing stages and exact object diagnostics', () {
    final json = _resultJson();
    json['timings_ms'] = {
      'decode_preprocess': 1.0,
      'detector': 20.0,
      'crop': 3.0,
      'repvit': 8.0,
      'dinov3': 5.0,
      'fusion': 2.0,
      'postprocess': 8.0,
      'total': 42.0,
    };
    json['diagnostics'] = {'object_count': 1, 'dino_object_count': 0};

    final result = InferenceResult.fromJson(json);

    expect(result.timings.cropMs, 3.0);
    expect(result.timings.fusionMs, 2.0);
    expect(result.diagnostics.objectCount, result.objects.length);
    expect(result.diagnostics.dinoObjectCount, 0);
  });

  test('accepts camera action state v2 while preserving exact Top3', () {
    final presentation = _presentationJson(
      state: 'unknown',
      candidateObjectIds: const ['object-1'],
      policyId: 'camera_action_state_v2',
    );
    final result = InferenceResult.fromJson(
      _resultJson(
        objects: [_unknownObject('object-1')],
        counts: const {},
        unknownCount: 1,
        presentation: presentation,
      ),
    );

    expect(result.presentation.policyId, 'camera_action_state_v2');
    expect(result.objects.single.candidates, hasLength(3));
    expect(result.objects.single.candidates.map((row) => row.rank), [1, 2, 3]);
  });

  test('camera action state v2 rejects candidate evidence weak retake', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          objects: [_unknownObject('object-1')],
          counts: const {},
          unknownCount: 1,
          presentation: _presentationJson(
            state: 'needs_retake',
            finalCountUsable: false,
            retakeScope: 'object',
            retakeObjectIds: const ['object-1'],
            instructionCode: 'candidate_evidence_weak',
            policyId: 'camera_action_state_v2',
          ),
        ),
      ),
      throwsFormatException,
    );
  });

  test('parses object retake without changing canonical counts', () {
    final result = InferenceResult.fromJson(
      _resultJson(
        objects: [
          _confirmedObject('object-1', skuId: 6),
          _unknownObject('object-2'),
        ],
        counts: {'6': 1},
        unknownCount: 1,
        presentation: _presentationJson(
          state: 'needs_retake',
          finalCountUsable: false,
          retakeScope: 'object',
          retakeObjectIds: const ['object-2'],
          instructionCode: 'candidate_evidence_weak',
        ),
      ),
    );

    expect(result.counts, {6: 1});
    expect(result.unknownCount, 1);
    expect(result.presentation.state, InferencePresentationState.needsRetake);
    expect(result.presentation.retakeScope, RetakeScope.object);
    expect(result.presentation.retakeObjectIds, ['object-2']);
    expect(
      result.presentation.instruction,
      RetakeInstruction.candidateEvidenceWeak,
    );
  });

  test('normal presentation keeps canonical count equality', () {
    final result = InferenceResult.fromJson(_resultJson());

    expect(result.presentation.state, InferencePresentationState.normal);
    expect(result.presentation.finalCountUsable, isTrue);
    expect(result.registeredCount, result.objects.length);
    expect(result.counts, {6: 1});
  });

  test('rejects a missing presentation map', () {
    final json = _resultJson()..remove('presentation');

    expect(() => InferenceResult.fromJson(json), throwsFormatException);
  });

  test('rejects a presentation policy hash outside lowercase SHA-256', () {
    for (final invalidHash in ['a' * 63, 'A' * 64, 'g' * 64]) {
      final presentation = _presentationJson();
      presentation['policy_sha256'] = invalidHash;

      expect(
        () => InferenceResult.fromJson(_resultJson(presentation: presentation)),
        throwsFormatException,
      );
    }
  });

  test('rejects missing, duplicate, and non-Unknown named object IDs', () {
    final objects = [
      _confirmedObject('object-1', skuId: 6),
      _unknownObject('object-2'),
    ];
    for (final candidateIds in [
      const ['object-3'],
      const ['object-2', 'object-2'],
      const ['object-1'],
    ]) {
      expect(
        () => InferenceResult.fromJson(
          _resultJson(
            objects: objects,
            counts: const {'6': 1},
            unknownCount: 1,
            presentation: _presentationJson(
              state: 'unknown',
              candidateObjectIds: candidateIds,
            ),
          ),
        ),
        throwsFormatException,
      );
    }

    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          objects: objects,
          counts: const {'6': 1},
          unknownCount: 1,
          presentation: _presentationJson(
            state: 'needs_retake',
            finalCountUsable: false,
            retakeScope: 'object',
            retakeObjectIds: const ['object-3'],
            instructionCode: 'separate_breads',
          ),
        ),
      ),
      throwsFormatException,
    );
  });

  test('rejects every contradictory presentation state shape', () {
    final objects = [
      _confirmedObject('object-1', skuId: 6),
      _unknownObject('object-2'),
    ];
    final invalidPresentations = <Map<String, Object?>>[
      _presentationJson(finalCountUsable: false),
      _presentationJson(retakeScope: 'scan'),
      _presentationJson(instructionCode: 'no_bread_detected'),
      _presentationJson(retakeObjectIds: const ['object-1']),
      _presentationJson(candidateObjectIds: const ['object-2']),
      _presentationJson(state: 'unknown'),
      _presentationJson(
        state: 'unknown',
        finalCountUsable: false,
        candidateObjectIds: const ['object-2'],
      ),
      _presentationJson(
        state: 'unknown',
        retakeScope: 'object',
        candidateObjectIds: const ['object-2'],
      ),
      _presentationJson(
        state: 'unknown',
        instructionCode: 'candidate_evidence_weak',
        candidateObjectIds: const ['object-2'],
      ),
      _presentationJson(
        state: 'unknown',
        retakeObjectIds: const ['object-1'],
        candidateObjectIds: const ['object-2'],
      ),
      _presentationJson(
        state: 'needs_retake',
        finalCountUsable: true,
        retakeScope: 'scan',
        instructionCode: 'no_bread_detected',
      ),
      _presentationJson(
        state: 'needs_retake',
        finalCountUsable: false,
        retakeScope: 'scan',
        retakeObjectIds: const ['object-1'],
        instructionCode: 'no_bread_detected',
      ),
      _presentationJson(
        state: 'needs_retake',
        finalCountUsable: false,
        retakeScope: 'scan',
        instructionCode: 'separate_breads',
      ),
      _presentationJson(
        state: 'needs_retake',
        finalCountUsable: false,
        retakeScope: 'scan',
        instructionCode: 'no_bread_detected',
        candidateObjectIds: const ['object-2'],
      ),
      _presentationJson(
        state: 'needs_retake',
        finalCountUsable: false,
        retakeScope: 'object',
        instructionCode: 'separate_breads',
      ),
      _presentationJson(
        state: 'needs_retake',
        finalCountUsable: false,
        retakeScope: 'object',
        retakeObjectIds: const ['object-1'],
        instructionCode: 'no_bread_detected',
      ),
      _presentationJson(
        state: 'needs_retake',
        finalCountUsable: false,
        retakeScope: 'object',
        retakeObjectIds: const ['object-1'],
        instructionCode: 'separate_breads',
        candidateObjectIds: const ['object-2'],
      ),
    ];

    for (final presentation in invalidPresentations) {
      expect(
        () => InferenceResult.fromJson(
          _resultJson(
            objects: objects,
            counts: const {'6': 1},
            unknownCount: 1,
            presentation: presentation,
          ),
        ),
        throwsFormatException,
        reason: '$presentation',
      );
    }
  });

  test('needs_retake rejects a null retake scope', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          presentation: _presentationJson(
            state: 'needs_retake',
            finalCountUsable: false,
            instructionCode: 'no_bread_detected',
          ),
        ),
      ),
      throwsFormatException,
    );
  });

  test('scan retake rejects a null instruction', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          presentation: _presentationJson(
            state: 'needs_retake',
            finalCountUsable: false,
            retakeScope: 'scan',
          ),
        ),
      ),
      throwsFormatException,
    );
  });

  test('object retake with named objects rejects a null instruction', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          presentation: _presentationJson(
            state: 'needs_retake',
            finalCountUsable: false,
            retakeScope: 'object',
            retakeObjectIds: const ['object-1'],
          ),
        ),
      ),
      throwsFormatException,
    );
  });

  test('object retake rejects duplicate retake object IDs', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          presentation: _presentationJson(
            state: 'needs_retake',
            finalCountUsable: false,
            retakeScope: 'object',
            retakeObjectIds: const ['object-1', 'object-1'],
            instructionCode: 'separate_breads',
          ),
        ),
      ),
      throwsFormatException,
    );
  });

  test('rejects non-finite or non-positive image geometry', () {
    for (final dimensions in [
      {'width': double.nan, 'height': 480},
      {'width': double.infinity, 'height': 480},
      {'width': 640, 'height': 0},
    ]) {
      final json = _resultJson();
      json['image'] = dimensions;
      expect(() => InferenceResult.fromJson(json), throwsFormatException);
    }
  });

  test('rejects duplicate or non-deterministic object IDs', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          objects: [
            _confirmedObject('object-1', skuId: 6),
            _confirmedObject('object-1', skuId: 10),
          ],
          counts: {'6': 1, '10': 1},
        ),
      ),
      throwsFormatException,
    );

    expect(
      () => InferenceResult.fromJson(
        _resultJson(objects: [_confirmedObject('detector-7')]),
      ),
      throwsFormatException,
    );
  });

  test('rejects boxes outside the canonical image or with invalid edges', () {
    for (final box in [
      [-1.0, 10.0, 20.0, 30.0],
      [10.0, 10.0, 10.0, 30.0],
      [10.0, 10.0, 641.0, 30.0],
      [10.0, double.nan, 20.0, 30.0],
    ]) {
      final object = _confirmedObject('object-1');
      object['bbox_xyxy'] = box;
      expect(
        () => InferenceResult.fromJson(_resultJson(objects: [object])),
        throwsFormatException,
      );
    }
  });

  test('Unknown requires exactly three ranked candidates', () {
    for (final candidateCount in [0, 2, 4]) {
      final object = _unknownObject('object-1');
      object['top3'] = (_unknownObject('object-1')['top3'] as List<Object?>)
          .take(candidateCount)
          .toList();
      if (candidateCount == 4) {
        (object['top3'] as List<Object?>).add({
          'rank': 4,
          'sku_id': 13,
          'sku_name': 'Muffin',
          'score': 0.1,
        });
      }
      expect(
        () => InferenceResult.fromJson(
          _resultJson(objects: [object], counts: const {}, unknownCount: 1),
        ),
        throwsFormatException,
      );
    }
  });

  test(
    'Unknown accepts an omitted reason while preserving ranked evidence',
    () {
      final object = _unknownObject('object-1');
      object['unknown_reason'] = null;

      final result = InferenceResult.fromJson(
        _resultJson(objects: [object], counts: const {}, unknownCount: 1),
      );

      expect(result.objects.single.unknownReason, isNull);
      expect(result.objects.single.candidates, hasLength(3));
    },
  );

  test('confirmed objects reject candidate evidence', () {
    final object = _confirmedObject('object-1');
    object['top3'] = _unknownObject('object-1')['top3'];

    expect(
      () => InferenceResult.fromJson(_resultJson(objects: [object])),
      throwsFormatException,
    );
  });

  test('rejects inconsistent registered and Unknown aggregation', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          objects: [
            _confirmedObject('object-1', skuId: 6),
            _unknownObject('object-2'),
          ],
          counts: {'6': 2},
          unknownCount: 0,
        ),
      ),
      throwsFormatException,
    );
  });

  test('rejects registered object SKU IDs outside 1 through 20', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(
          objects: [_confirmedObject('object-1', skuId: 21)],
          counts: {'21': 1},
        ),
      ),
      throwsFormatException,
    );
  });

  test('rejects Unknown candidate SKU IDs outside 1 through 20', () {
    final object = _unknownObject('object-1');
    final candidates = object['top3'] as List<Object?>;
    candidates[0] = {
      'rank': 1,
      'sku_id': 21,
      'sku_name': 'Out of contract',
      'score': 0.41,
    };

    expect(
      () => InferenceResult.fromJson(
        _resultJson(objects: [object], counts: const {}, unknownCount: 1),
      ),
      throwsFormatException,
    );
  });

  test('rejects non-canonical count keys even when they parse in range', () {
    expect(
      () => InferenceResult.fromJson(
        _resultJson(objects: [_confirmedObject('object-1')], counts: {'06': 1}),
      ),
      throwsFormatException,
    );
  });

  test('strict event parser rejects unknown types and malformed fields', () {
    expect(
      () => WorkerEvent.fromJson(const {'type': 'surprise'}),
      throwsFormatException,
    );
    expect(
      () => WorkerEvent.fromJson(const {
        'type': 'progress',
        'request_id': 'analysis-1',
        'phase': 'rendering',
      }),
      throwsFormatException,
    );
    expect(
      () => WorkerEvent.fromJson(const {
        'type': 'ready',
        'device': 'cpu',
        'unexpected': true,
      }),
      throwsFormatException,
    );
  });

  test('parses typed startup, progress, and result events', () {
    final loading = WorkerEvent.fromJson(const {'type': 'loading'});
    final warming = WorkerEvent.fromJson(const {
      'type': 'warming',
      'device': 'cuda:0',
    });
    final ready = WorkerEvent.fromJson({
      'type': 'ready',
      'device': 'cpu',
      'startup_metrics': _startupMetricsJson(),
    });
    final progress = WorkerEvent.fromJson(const {
      'type': 'progress',
      'request_id': 'analysis-1',
      'phase': 'detecting',
    });
    final result = WorkerEvent.fromJson(_resultJson());

    expect((loading as StartupWorkerEvent).status, WorkerStatus.loading);
    expect((warming as StartupWorkerEvent).device, 'cuda:0');
    final metrics = (ready as ReadyWorkerEvent).metrics!;
    expect(metrics.loadMs, 12.5);
    expect(metrics.detectorId, 'rfdetr_large_bakery_v1');
    expect(metrics.repvitId, 'repvit_m1_15plus5_v1');
    expect(metrics.dinov3Id, 'dinov3_vits16_15plus5_v1');
    expect(metrics.fusionPolicyId, 'fusion_local_or_global_v1');
    expect(metrics.detectorThreshold, 0.42);
    expect((progress as ProgressWorkerEvent).phase, WorkerPhase.detecting);
    expect((result as ResultWorkerEvent).result.requestId, 'analysis-1');
  });

  test('startup metrics reject malformed real-contract metadata', () {
    for (final mutation in <void Function(Map<String, Object?>)>[
      (metrics) => metrics.remove('detector_id'),
      (metrics) => metrics['device'] = 'gpu',
      (metrics) => metrics['repvit_id'] = '',
      (metrics) => metrics['detector_threshold'] = 1.1,
    ]) {
      final metrics = _startupMetricsJson();
      mutation(metrics);
      expect(() => StartupMetrics.fromJson(metrics), throwsFormatException);
    }
  });
}

Map<String, Object?> _startupMetricsJson() {
  return {
    'device': 'cpu',
    'load_ms': 12.5,
    'warmup_ms': 7.0,
    'fallback_reason': null,
    'detector_id': 'rfdetr_large_bakery_v1',
    'repvit_id': 'repvit_m1_15plus5_v1',
    'dinov3_id': 'dinov3_vits16_15plus5_v1',
    'fusion_policy_id': 'fusion_local_or_global_v1',
    'detector_threshold': 0.42,
  };
}

Map<String, Object?> _resultJson({
  String requestId = 'analysis-1',
  List<Map<String, Object?>>? objects,
  Map<String, int>? counts,
  int unknownCount = 0,
  Map<String, Object?>? presentation,
}) {
  final resultObjects =
      objects ?? <Map<String, Object?>>[_confirmedObject('object-1')];
  final unknownIds = [
    for (final object in resultObjects)
      if (object['sku_id'] == null) object['object_id']! as String,
  ];
  return {
    'type': 'result',
    'request_id': requestId,
    'image': {'width': 640, 'height': 480},
    'device': 'cpu',
    'objects': resultObjects,
    'counts': counts ?? {'6': 1},
    'unknown_count': unknownCount,
    'presentation':
        presentation ??
        (unknownIds.isEmpty
            ? _presentationJson()
            : _presentationJson(
                state: 'unknown',
                candidateObjectIds: unknownIds,
              )),
    'timings_ms': {
      'decode_preprocess': 1.0,
      'detector': 20.0,
      'crop': 0.0,
      'repvit': 8.0,
      'dinov3': 5.0,
      'fusion': 0.0,
      'postprocess': 8.0,
      'total': 42.0,
    },
    'diagnostics': {
      'object_count': resultObjects.length,
      'dino_object_count': 0,
    },
  };
}

Map<String, Object?> _presentationJson({
  String state = 'normal',
  bool finalCountUsable = true,
  String? retakeScope,
  List<String> retakeObjectIds = const [],
  String? instructionCode,
  List<String> candidateObjectIds = const [],
  String policyId = 'camera_action_state_v1',
}) {
  return {
    'state': state,
    'final_count_usable': finalCountUsable,
    'retake_scope': retakeScope,
    'retake_object_ids': retakeObjectIds,
    'instruction_code': instructionCode,
    'candidate_object_ids': candidateObjectIds,
    'policy_id': policyId,
    'policy_sha256': '1' * 64,
  };
}

Map<String, Object?> _confirmedObject(String objectId, {int skuId = 6}) {
  return {
    'object_id': objectId,
    'sku_id': skuId,
    'sku_name': skuId == 6 ? 'Croissant' : 'Sugar Donut',
    'bbox_xyxy': [10.0, 20.0, 110.0, 120.0],
    'confidence': 0.92,
    'decision_path': 'repvit_direct',
    'top3': <Object?>[],
    'unknown_reason': null,
    'detector': {'source': 'rfdetr', 'score': 0.95},
    'provenance': _provenance(),
  };
}

Map<String, Object?> _unknownObject(String objectId) {
  return {
    'object_id': objectId,
    'sku_id': null,
    'sku_name': 'Unknown',
    'bbox_xyxy': [120.0, 30.0, 220.0, 130.0],
    'confidence': 0.41,
    'decision_path': 'unknown_top3',
    'top3': [
      {'rank': 1, 'sku_id': 4, 'sku_name': 'Scon', 'score': 0.41},
      {'rank': 2, 'sku_id': 2, 'sku_name': 'Flower Bread', 'score': 0.32},
      {'rank': 3, 'sku_id': 7, 'sku_name': 'Egg Tart', 'score': 0.27},
    ],
    'unknown_reason': 'fusion_rejected',
    'detector': {'source': 'rfdetr', 'score': 0.87},
    'provenance': _provenance(failureCode: 'fusion_rejected'),
  };
}

Map<String, Object?> _provenance({String? failureCode}) {
  return {
    'detector_id': 'rfdetr_large_bakery_v1',
    'repvit_artifact_id': 'repvit_m1_15plus5_v1',
    'repvit_sha256': 'a' * 64,
    'repvit_manifest_sha256': 'b' * 64,
    'repvit_prototype_sha256': 'c' * 64,
    'dinov3_artifact_id': 'dinov3_vits16_15plus5_v1',
    'dinov3_sha256': 'd' * 64,
    'dinov3_support_sha256': 'e' * 64,
    'calibration_id': 'policy-v1',
    'calibration_sha256': 'f' * 64,
    'preprocess_sha256': '0' * 64,
    'canonical_frame_version': 'exif_visual_rgb_v1',
    'exif_orientation': 1,
    'failure_code': failureCode,
  };
}
