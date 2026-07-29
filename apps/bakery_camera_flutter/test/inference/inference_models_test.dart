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
      'startup_metrics': {
        'device': 'cpu',
        'load_ms': 12.5,
        'warmup_ms': 7.0,
        'fallback_reason': null,
      },
    });
    final progress = WorkerEvent.fromJson(const {
      'type': 'progress',
      'request_id': 'analysis-1',
      'phase': 'detecting',
    });
    final result = WorkerEvent.fromJson(_resultJson());

    expect((loading as StartupWorkerEvent).status, WorkerStatus.loading);
    expect((warming as StartupWorkerEvent).device, 'cuda:0');
    expect((ready as ReadyWorkerEvent).metrics?.loadMs, 12.5);
    expect((progress as ProgressWorkerEvent).phase, WorkerPhase.detecting);
    expect((result as ResultWorkerEvent).result.requestId, 'analysis-1');
  });
}

Map<String, Object?> _resultJson({
  String requestId = 'analysis-1',
  List<Map<String, Object?>>? objects,
  Map<String, int>? counts,
  int unknownCount = 0,
}) {
  final resultObjects =
      objects ?? <Map<String, Object?>>[_confirmedObject('object-1')];
  return {
    'type': 'result',
    'request_id': requestId,
    'image': {'width': 640, 'height': 480},
    'device': 'cpu',
    'objects': resultObjects,
    'counts': counts ?? {'6': 1},
    'unknown_count': unknownCount,
    'timings_ms': {
      'decode_preprocess': 1.0,
      'detector': 20.0,
      'repvit': 8.0,
      'dinov3': 5.0,
      'postprocess': 8.0,
      'total': 42.0,
    },
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
