import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('candidate retake preserves chain and increments attempts', () {
    final result = CandidateScanResult.fromJson(_candidateRetakeJson(attempt: 1));

    expect(result.objects, isEmpty);
    expect(result.skuTotals, isEmpty);
    expect(result.problemRegions, hasLength(1));
    expect(result.nextRetakeRequest.retakeChainId, 'chain-1');
    expect(result.nextRetakeRequest.attempt, 2);
  });

  test('candidate third retake requires manual catalog without partial inference', () {
    final result = CandidateScanResult.fromJson(_candidateRetakeJson(attempt: 3));

    expect(result.manualCatalogRequired, isTrue);
    expect(() => result.nextRetakeRequest, throwsStateError);

    final partial = _candidateRetakeJson(attempt: 3);
    partial['objects'] = [<String, Object?>{'partial': true}];
    expect(() => CandidateScanResult.fromJson(partial), throwsFormatException);
  });

  test('candidate schema rejects unknown fields and non-finite timings', () {
    final unknown = _candidateRetakeJson()..['extra'] = true;
    expect(() => CandidateScanResult.fromJson(unknown), throwsFormatException);

    final nonFinite = _candidateRetakeJson();
    (nonFinite['timings_ms']! as Map<String, Object?>)['detector'] = double.nan;
    expect(() => CandidateScanResult.fromJson(nonFinite), throwsFormatException);
  });

  test('candidate parser rejects noncanonical object and Top3 SKU names', () {
    final wrongObject = _candidateObjectJson()
      ..['sku_name'] = 'not canonical';
    expect(
      () => CandidateInferenceObject.fromJson(
        wrongObject,
        scanId: 'scan-1',
        expectedOrder: 1,
        imageWidth: 100,
        imageHeight: 100,
        runtimeProfileId: 'rtx5080_trt_fp16_static7_v1',
      ),
      throwsFormatException,
    );

    final wrongTop3 = _candidateObjectJson();
    ((wrongTop3['top3']! as List<Object?>).first! as Map<String, Object?>)
        ['sku_name'] = 'not canonical';
    expect(
      () => CandidateInferenceObject.fromJson(
        wrongTop3,
        scanId: 'scan-1',
        expectedOrder: 1,
        imageWidth: 100,
        imageHeight: 100,
        runtimeProfileId: 'rtx5080_trt_fp16_static7_v1',
      ),
      throwsFormatException,
    );
  });
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

  test('parses CUDA reference runtime evidence', () {
    final result = InferenceResult.fromJson(
      _resultJson(
        device: 'cuda:0',
        executionDevice: 'cuda:0',
        runtimeMode: 'gpu_reference',
        fallbackReason: 'rfdetr_engine_parity_missing',
      ),
    );

    expect(result.executionDevice, 'cuda:0');
    expect(result.runtimeMode, RuntimeMode.gpuReference);
    expect(result.fallbackReason, 'rfdetr_engine_parity_missing');
  });

  test('rejects mismatched runtime device mode and fallback evidence', () {
    for (final mutation in <void Function(Map<String, Object?>)>[
      (result) => result['runtime_mode'] = 'gpu_reference',
      (result) => result['fallback_reason'] = null,
      (result) {
        result['device'] = 'cuda:0';
        result['execution_device'] = 'cuda:0';
        result['runtime_mode'] = 'gpu_fast_verified';
        result['fallback_reason'] = 'unexpected_fallback';
      },
      (result) {
        result['execution_device'] = 'cuda:0';
        result['runtime_mode'] = 'gpu_reference';
        result['fallback_reason'] = 'rfdetr_engine_parity_missing';
      },
      (result) => result['fallback_reason'] = '',
      (result) => result['inference_ms'] = 43.0,
    ]) {
      final result = _resultJson();
      mutation(result);
      expect(() => InferenceResult.fromJson(result), throwsFormatException);
    }
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

  test('rejects a total shorter than an individual timing stage', () {
    final json = _resultJson();
    (json['timings_ms'] as Map<String, Object?>)['detector'] = 200.0;
    (json['timings_ms'] as Map<String, Object?>)['total'] = 1.0;

    expect(() => InferenceResult.fromJson(json), throwsFormatException);
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

  test('Unknown candidates require descending scores and ascending SKU ties', () {
    final object = _unknownObject('object-1');
    object['top3'] = [
      {'rank': 1, 'sku_id': 7, 'sku_name': 'Flower Bread', 'score': 0.41},
      {'rank': 2, 'sku_id': 2, 'sku_name': 'Croffle', 'score': 0.41},
      {'rank': 3, 'sku_id': 4, 'sku_name': 'Scon', 'score': 0.27},
    ];

    expect(
      () => InferenceResult.fromJson(
        _resultJson(objects: [object], counts: const {}, unknownCount: 1),
      ),
      throwsFormatException,
    );
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

  test('parses optional lifecycle code identity and rejects malformed values', () {
    final identity = {
      'code_commit': 'a' * 40,
      'code_identity_sha256': 'b' * 64,
    };
    final ready = WorkerEvent.fromJson({
      'type': 'ready',
      'device': 'cuda:0',
      'code_identity': identity,
    }) as ReadyWorkerEvent;
    final stopped = WorkerEvent.fromJson({
      'type': 'stopped',
      'request_id': 'shutdown-1',
      'code_identity': identity,
    }) as StoppedWorkerEvent;

    expect(ready.codeIdentity!.codeCommit, 'a' * 40);
    expect(stopped.codeIdentity!.codeIdentitySha256, 'b' * 64);
    expect(
      () => WorkerEvent.fromJson({
        'type': 'ready',
        'device': 'cuda:0',
        'code_identity': {
          'code_commit': 'A' * 40,
          'code_identity_sha256': 'b' * 64,
        },
      }),
      throwsFormatException,
    );
  });

  test('startup metrics reject malformed real-contract metadata', () {
    for (final mutation in <void Function(Map<String, Object?>)>[
      (metrics) => metrics.remove('detector_id'),
      (metrics) => metrics['device'] = 'gpu',
      (metrics) => metrics['repvit_id'] = '',
      (metrics) => metrics['detector_threshold'] = 1.1,
      (metrics) => metrics['runtime_mode'] = 'gpu_reference',
      (metrics) => metrics['fallback_reason'] = null,
    ]) {
      final metrics = _startupMetricsJson();
      mutation(metrics);
      expect(() => StartupMetrics.fromJson(metrics), throwsFormatException);
    }
  });

  test('startup metrics constructor rejects impossible runtime admission', () {
    for (final build in <StartupMetrics Function()>[
      () => _startupMetrics(runtimeMode: RuntimeMode.gpuReference),
      () => _startupMetrics(fallbackReason: null),
      () => _startupMetrics(fallbackReason: ''),
    ]) {
      expect(build, throwsFormatException);
    }
  });
}

Map<String, Object?> _candidateRetakeJson({int attempt = 1}) => {
  'type': 'result',
  'request_id': 'scan-1',
  'scan_id': 'scan-1',
  'retake_chain_id': 'chain-1',
  'state': 'needs_retake',
  'object_total': 0,
  'registered_object_total': 0,
  'unknown_total': 0,
  'sku_totals': <String, Object?>{},
  'objects': <Object?>[],
  'reasons': <Object?>['overlap_or_occlusion'],
  'problem_regions': <Object?>[
    {
      'box_xyxy': <Object?>[1.0, 2.0, 5.0, 6.0],
      'center_normalized': <Object?>[0.15, 0.2],
      'object_order': 1,
    },
  ],
  'attempt': attempt,
  'canonical_frame': <String, Object?>{'width': 20, 'height': 20},
  'timings_ms': <String, Object?>{
    'decode_canonical': 1.0,
    'detector': 2.0,
    'completeness': 3.0,
    'crop': 0.0,
    'repvit': 0.0,
    'direct_gate': 0.0,
    'dinov3': 0.0,
    'fusion_payload': 0.0,
    'total': 6.0,
  },
  'provenance': <String, Object?>{
    'pipeline_id': 'rtx5080_15plus5_single_frame_v1',
    'runtime_profile_id': 'rtx5080_trt_fp16_static7_v1',
    'admission_receipt_sha256': 'a' * 64,
    'artifact_hashes': <String, Object?>{'detector': 'b' * 64},
  },
  'manual_catalog_required': attempt >= 3,
  'runtime_profile_id': 'rtx5080_trt_fp16_static7_v1',
  'receipt_id': 'a' * 64,
};

Map<String, Object?> _candidateObjectJson() => {
  'object_id': 'scan-1#0001',
  'sku_id': 1,
  'sku_name': 'Walnut Donut',
  'decision_path': 'direct_approved',
  'location': <String, Object?>{
    'box_xyxy': <Object?>[10.0, 10.0, 30.0, 30.0],
    'center_normalized': <Object?>[0.2, 0.2],
    'object_order': 1,
  },
  'confidence': <String, Object?>{
    'detector_calibrated': 0.9,
    'sku_acceptance_calibrated': 0.8,
    'fusion_margin': null,
  },
  'top3': <Object?>[
    {'rank': 1, 'sku_id': 1, 'sku_name': 'Walnut Donut', 'score': 0.8},
    {'rank': 2, 'sku_id': 2, 'sku_name': 'Croffle', 'score': 0.15},
    {'rank': 3, 'sku_id': 3, 'sku_name': 'Waffle', 'score': 0.05},
  ],
  'provenance': <String, Object?>{
    'detector_artifact_id': 'detector',
    'detector_sha256': 'a' * 64,
    'repvit_artifact_id': 'repvit',
    'repvit_sha256': 'b' * 64,
    'dinov3_artifact_id': 'dinov3',
    'dinov3_sha256': 'c' * 64,
    'fusion_policy_id': 'fusion',
    'fusion_policy_sha256': 'd' * 64,
    'runtime_profile_id': 'rtx5080_trt_fp16_static7_v1',
  },
};

StartupMetrics _startupMetrics({
  RuntimeMode runtimeMode = RuntimeMode.cpuReference,
  String? fallbackReason = 'CPU reference runtime selected',
}) => StartupMetrics(
  device: 'cpu',
  runtimeMode: runtimeMode,
  loadMs: 12.5,
  warmupMs: 7,
  fallbackReason: fallbackReason,
  detectorId: 'rfdetr_large_bakery_v1',
  repvitId: 'repvit_m1_15plus5_v1',
  dinov3Id: 'dinov3_vits16_15plus5_v1',
  fusionPolicyId: 'fusion_local_or_global_v1',
  detectorThreshold: .42,
);

Map<String, Object?> _startupMetricsJson() {
  return {
    'device': 'cpu',
    'runtime_mode': 'cpu_reference',
    'load_ms': 12.5,
    'warmup_ms': 7.0,
    'fallback_reason': 'CPU reference runtime selected',
    'detector_id': 'rfdetr_large_bakery_v1',
    'repvit_id': 'repvit_m1_15plus5_v1',
    'dinov3_id': 'dinov3_vits16_15plus5_v1',
    'fusion_policy_id': 'fusion_local_or_global_v1',
    'detector_threshold': 0.42,
    'applied_artifact_hashes': {
      for (final key in const [
        'detector_checkpoint_sha256', 'detector_calibration_sha256',
        'detector_manifest_sha256', 'repvit_checkpoint_sha256',
        'repvit_manifest_sha256', 'repvit_prototype_sha256',
        'dinov3_weights_sha256', 'dinov3_support_sha256',
        'dinov3_local_bank_sha256', 'classifier_calibration_sha256',
        'preprocess_sha256', 'fusion_policy_sha256',
        'presentation_policy_sha256',
      ]) key: 'a' * 64,
    },
  };
}

Map<String, Object?> _resultJson({
  String requestId = 'analysis-1',
  List<Map<String, Object?>>? objects,
  Map<String, int>? counts,
  int unknownCount = 0,
  Map<String, Object?>? presentation,
  String device = 'cpu',
  String executionDevice = 'cpu',
  String runtimeMode = 'cpu_reference',
  String? fallbackReason = 'CPU reference runtime selected',
  double scanToResultMs = 42.0,
  double inferenceMs = 34.0,
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
    'device': device,
    'execution_device': executionDevice,
    'runtime_mode': runtimeMode,
    'fallback_reason': fallbackReason,
    'scan_to_result_ms': scanToResultMs,
    'inference_ms': inferenceMs,
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
