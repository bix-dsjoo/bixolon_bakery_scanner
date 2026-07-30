import 'package:bakery_camera_prototype/src/inference/inference_models.dart';

InferenceResult buildUiInferenceResult({
  double dinov3Ms = 90,
  double totalMs = 290,
  Map<String, Object?>? presentation,
}) =>
    InferenceResult.fromJson({
      'type': 'result',
      'request_id': 'analysis-1',
      'image': {'width': 1920, 'height': 1080},
      'device': 'cuda:0',
      'objects': [
        buildInferenceObjectJson(
          id: 'object-1',
          skuId: 6,
          name: 'Croissant',
          confidence: 0.92,
          decisionPath: 'repvit_direct',
          box: [10.0, 20.0, 500.0, 500.0],
        ),
        buildInferenceObjectJson(
          id: 'object-2',
          skuId: null,
          name: 'Unknown',
          confidence: 0.4,
          decisionPath: 'unknown_top3',
          box: [600.0, 100.0, 1000.0, 600.0],
          candidates: const [
            {
              'rank': 1,
              'sku_id': 10,
              'sku_name': 'Sugar Donut',
              'score': 0.88,
            },
            {
              'rank': 2,
              'sku_id': 11,
              'sku_name': 'Cream Donut',
              'score': 0.76,
            },
            {
              'rank': 3,
              'sku_id': 12,
              'sku_name': 'Glazed Donut',
              'score': 0.62,
            },
          ],
        ),
      ],
      'counts': {'6': 1},
      'unknown_count': 1,
      'presentation':
          presentation ??
          buildPresentationJson(
            state: 'unknown',
            candidateObjectIds: const ['object-2'],
          ),
      'timings_ms': {
        'decode_preprocess': 10.0,
        'detector': 120.0,
        'repvit': 50.0,
        'dinov3': dinov3Ms,
        'postprocess': 20.0,
        'total': totalMs,
      },
    });

InferenceResult buildOrderingInferenceResult({double dinov3Ms = 0}) =>
    InferenceResult.fromJson({
      'type': 'result',
      'request_id': 'analysis-ordering',
      'image': {'width': 1280, 'height': 720},
      'device': 'cpu',
      'objects': [
        buildInferenceObjectJson(
          id: 'object-1',
          skuId: 1,
          name: 'Pastry Bread',
          confidence: 0.91,
          decisionPath: 'fusion_ranked',
          box: [10.0, 20.0, 210.0, 220.0],
        ),
        buildInferenceObjectJson(
          id: 'object-2',
          skuId: null,
          name: 'Unknown',
          confidence: 0.31,
          decisionPath: 'unknown_top3',
          box: [240.0, 20.0, 440.0, 220.0],
          candidates: candidateJson(topScore: 0.45),
        ),
        buildInferenceObjectJson(
          id: 'object-3',
          skuId: null,
          name: 'Unknown',
          confidence: 0.18,
          decisionPath: 'unknown_top3',
          box: [470.0, 20.0, 670.0, 220.0],
          candidates: candidateJson(topScore: 0.21),
        ),
      ],
      'counts': {'1': 1},
      'unknown_count': 2,
      'presentation': buildPresentationJson(
        state: 'unknown',
        candidateObjectIds: const ['object-2', 'object-3'],
      ),
      'timings_ms': {
        'decode_preprocess': 12.0,
        'detector': 240.0,
        'repvit': 80.0,
        'dinov3': dinov3Ms,
        'postprocess': 20.0,
        'total': 352.0,
      },
    });

Map<String, Object?> buildPresentationJson({
  String state = 'normal',
  bool finalCountUsable = true,
  String? retakeScope,
  List<String> retakeObjectIds = const [],
  String? instructionCode,
  List<String> candidateObjectIds = const [],
}) =>
    {
      'state': state,
      'final_count_usable': finalCountUsable,
      'retake_scope': retakeScope,
      'retake_object_ids': retakeObjectIds,
      'instruction_code': instructionCode,
      'candidate_object_ids': candidateObjectIds,
      'policy_id': 'camera_action_state_v1',
      'policy_sha256': '1' * 64,
    };

List<Map<String, Object?>> candidateJson({required double topScore}) => [
  {'rank': 1, 'sku_id': 10, 'sku_name': 'Sugar Donut', 'score': topScore},
  {
    'rank': 2,
    'sku_id': 11,
    'sku_name': 'Cream Donut',
    'score': topScore / 2,
  },
  {
    'rank': 3,
    'sku_id': 12,
    'sku_name': 'Glazed Donut',
    'score': topScore / 4,
  },
];

Map<String, Object?> buildInferenceObjectJson({
  required String id,
  required int? skuId,
  required String name,
  required double confidence,
  required String decisionPath,
  required List<double> box,
  List<Map<String, Object?>> candidates = const [],
}) =>
    {
      'object_id': id,
      'sku_id': skuId,
      'sku_name': name,
      'bbox_xyxy': box,
      'confidence': confidence,
      'decision_path': decisionPath,
      'top3': candidates,
      'unknown_reason': skuId == null ? 'consensus_failed' : null,
      'detector': {'source': 'rfdetr', 'score': 0.95},
      'provenance': {
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
        'failure_code': skuId == null ? 'consensus_failed' : null,
      },
    };
