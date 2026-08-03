import 'dart:collection';

enum WorkerStatus {
  notStarted,
  starting,
  loading,
  warming,
  ready,
  fatal,
  stopped,
}

enum WorkerPhase {
  detecting,
  classifying,
  rechecking,
  aggregating;

  static WorkerPhase parse(Object? value) {
    if (value is! String) {
      throw const FormatException('worker phase must be a string');
    }
    return switch (value) {
      'detecting' => WorkerPhase.detecting,
      'classifying' => WorkerPhase.classifying,
      'rechecking' => WorkerPhase.rechecking,
      'aggregating' => WorkerPhase.aggregating,
      _ => throw FormatException('unsupported worker phase: $value'),
    };
  }
}

final class InferenceCandidate {
  const InferenceCandidate({
    required this.rank,
    required this.skuId,
    required this.skuName,
    required this.score,
  });

  factory InferenceCandidate.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {'rank', 'sku_id', 'sku_name', 'score'});
    final rank = _positiveInt(json['rank'], 'candidate rank');
    final skuId = _skuId(json['sku_id'], 'candidate sku_id');
    final skuName = _requiredString(json['sku_name'], 'candidate sku_name');
    final score = _probability(json['score'], 'candidate score');
    return InferenceCandidate(
      rank: rank,
      skuId: skuId,
      skuName: skuName,
      score: score,
    );
  }

  final int rank;
  final int skuId;
  final String skuName;
  final double score;
}

final class InferenceObject {
  InferenceObject._({
    required this.objectId,
    required this.skuId,
    required this.skuName,
    required List<double> bboxXyxy,
    required this.confidence,
    required this.decisionPath,
    required List<InferenceCandidate> candidates,
    required this.unknownReason,
    required this.detectorSource,
    required this.detectorScore,
    required Map<String, Object?> provenance,
  }) : bboxXyxy = List.unmodifiable(bboxXyxy),
       candidates = List.unmodifiable(candidates),
       provenance = UnmodifiableMapView(provenance);

  factory InferenceObject.fromJson(
    Map<String, Object?> json, {
    required int index,
    required double imageWidth,
    required double imageHeight,
  }) {
    _expectFields(json, const {
      'object_id',
      'sku_id',
      'sku_name',
      'bbox_xyxy',
      'confidence',
      'decision_path',
      'top3',
      'unknown_reason',
      'detector',
      'provenance',
    });

    final objectId = _requiredString(json['object_id'], 'object_id');
    if (objectId != 'object-$index') {
      throw FormatException(
        'object_id must be deterministic: expected object-$index',
      );
    }
    final skuIdValue = json['sku_id'];
    final skuId = skuIdValue == null ? null : _skuId(skuIdValue, 'sku_id');
    final skuName = _requiredString(json['sku_name'], 'sku_name');
    final bbox = _box(
      json['bbox_xyxy'],
      imageWidth: imageWidth,
      imageHeight: imageHeight,
    );
    final confidence = _probability(json['confidence'], 'confidence');
    final decisionPath = _requiredString(
      json['decision_path'],
      'decision_path',
    );
    const registeredPaths = {
      'repvit_direct',
      'dinov3_confirmed',
      'fusion_ranked',
    };
    if (skuId == null) {
      if (skuName != 'Unknown' || decisionPath != 'unknown_top3') {
        throw const FormatException(
          'Unknown object identity and decision path are inconsistent',
        );
      }
    } else if (skuName == 'Unknown' ||
        !registeredPaths.contains(decisionPath)) {
      throw const FormatException(
        'registered object identity and decision path are inconsistent',
      );
    }

    final candidateValues = _list(json['top3'], 'top3');
    final candidates = <InferenceCandidate>[
      for (final value in candidateValues)
        InferenceCandidate.fromJson(_map(value, 'top3 candidate')),
    ];
    final unknownReasonValue = json['unknown_reason'];
    final String? unknownReason;
    if (unknownReasonValue == null) {
      unknownReason = null;
    } else {
      unknownReason = _requiredString(unknownReasonValue, 'unknown_reason');
    }
    if (skuId == null) {
      _requireExactTop3(candidates);
    } else if (candidates.isNotEmpty || unknownReason != null) {
      throw const FormatException(
        'registered objects must not include Unknown evidence',
      );
    }

    final detector = _map(json['detector'], 'detector');
    _expectFields(detector, const {'source', 'score'});
    final detectorSource = _requiredString(
      detector['source'],
      'detector source',
    );
    final detectorScore = _probability(detector['score'], 'detector score');
    final provenance = _parseProvenance(_map(json['provenance'], 'provenance'));

    return InferenceObject._(
      objectId: objectId,
      skuId: skuId,
      skuName: skuName,
      bboxXyxy: bbox,
      confidence: confidence,
      decisionPath: decisionPath,
      candidates: candidates,
      unknownReason: unknownReason,
      detectorSource: detectorSource,
      detectorScore: detectorScore,
      provenance: provenance,
    );
  }

  final String objectId;
  final int? skuId;
  final String skuName;
  final List<double> bboxXyxy;
  final double confidence;
  final String decisionPath;
  final List<InferenceCandidate> candidates;
  final String? unknownReason;
  final String detectorSource;
  final double detectorScore;
  final Map<String, Object?> provenance;

  bool get isUnknown => skuId == null;
}

void _requireExactTop3(List<InferenceCandidate> candidates) {
  if (candidates.length != 3 ||
      candidates.asMap().entries.any(
        (entry) => entry.value.rank != entry.key + 1,
      ) ||
      candidates.map((candidate) => candidate.skuId).toSet().length != 3) {
    throw const FormatException(
      'Unknown objects require exactly three ranked candidates',
    );
  }
  for (var index = 1; index < candidates.length; index += 1) {
    final previous = candidates[index - 1];
    final current = candidates[index];
    if (previous.score < current.score ||
        (previous.score == current.score && previous.skuId > current.skuId)) {
      throw const FormatException(
        'Unknown candidates must descend by score with SKU-ID ties ascending',
      );
    }
  }
}

final class StageTimings {
  const StageTimings({
    required this.decodePreprocessMs,
    required this.detectorMs,
    required this.cropMs,
    required this.repvitMs,
    required this.dinov3Ms,
    required this.fusionMs,
    required this.postprocessMs,
    required this.totalMs,
  });

  factory StageTimings.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {
      'decode_preprocess',
      'detector',
      'crop',
      'repvit',
      'dinov3',
      'fusion',
      'postprocess',
      'total',
    });
    final timings = StageTimings(
      decodePreprocessMs: _nonNegativeFinite(
        json['decode_preprocess'],
        'decode_preprocess timing',
      ),
      detectorMs: _nonNegativeFinite(json['detector'], 'detector timing'),
      cropMs: _nonNegativeFinite(json['crop'], 'crop timing'),
      repvitMs: _nonNegativeFinite(json['repvit'], 'repvit timing'),
      dinov3Ms: _nonNegativeFinite(json['dinov3'], 'dinov3 timing'),
      fusionMs: _nonNegativeFinite(json['fusion'], 'fusion timing'),
      postprocessMs: _nonNegativeFinite(
        json['postprocess'],
        'postprocess timing',
      ),
      totalMs: _nonNegativeFinite(json['total'], 'total timing'),
    );
    if (timings.totalMs <
        [
          timings.decodePreprocessMs,
          timings.detectorMs,
          timings.cropMs,
          timings.repvitMs,
          timings.dinov3Ms,
          timings.fusionMs,
          timings.postprocessMs,
        ].reduce((maximum, value) => value > maximum ? value : maximum)) {
      throw const FormatException('total timing must cover every stage');
    }
    return timings;
  }

  final double decodePreprocessMs;
  final double detectorMs;
  final double cropMs;
  final double repvitMs;
  final double dinov3Ms;
  final double fusionMs;
  final double postprocessMs;
  final double totalMs;
}

final class InferenceDiagnostics {
  const InferenceDiagnostics({
    required this.objectCount,
    required this.dinoObjectCount,
  });

  factory InferenceDiagnostics.fromJson(
    Map<String, Object?> json, {
    required int actualObjectCount,
  }) {
    _expectFields(json, const {'object_count', 'dino_object_count'});
    final objectCount = _nonNegativeInt(json['object_count'], 'object_count');
    final dinoObjectCount = _nonNegativeInt(
      json['dino_object_count'],
      'dino_object_count',
    );
    if (objectCount != actualObjectCount || dinoObjectCount > objectCount) {
      throw const FormatException('inference diagnostics are inconsistent');
    }
    return InferenceDiagnostics(
      objectCount: objectCount,
      dinoObjectCount: dinoObjectCount,
    );
  }

  final int objectCount;
  final int dinoObjectCount;
}

final class StartupMetrics {
  StartupMetrics({
    required this.device,
    required this.loadMs,
    required this.warmupMs,
    required this.fallbackReason,
    required this.detectorId,
    required this.repvitId,
    required this.dinov3Id,
    required this.fusionPolicyId,
    required this.detectorThreshold,
    Map<String, String> appliedArtifactHashes = const {},
  }) : appliedArtifactHashes = UnmodifiableMapView(
         Map<String, String>.from(appliedArtifactHashes),
       );

  factory StartupMetrics.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {
      'device',
      'load_ms',
      'warmup_ms',
      'fallback_reason',
      'detector_id',
      'repvit_id',
      'dinov3_id',
      'fusion_policy_id',
      'detector_threshold',
      'applied_artifact_hashes',
    });
    final device = _requiredString(json['device'], 'startup device');
    if (device != 'cpu' && device != 'cuda:0') {
      throw const FormatException('startup device must be cpu or cuda:0');
    }
    final fallbackValue = json['fallback_reason'];
    final rawHashes = _map(
      json['applied_artifact_hashes'],
      'startup applied_artifact_hashes',
    );
    const hashKeys = {
      'detector_checkpoint_sha256',
      'detector_calibration_sha256',
      'detector_manifest_sha256',
      'repvit_checkpoint_sha256',
      'repvit_manifest_sha256',
      'repvit_prototype_sha256',
      'dinov3_weights_sha256',
      'dinov3_support_sha256',
      'dinov3_local_bank_sha256',
      'classifier_calibration_sha256',
      'preprocess_sha256',
      'fusion_policy_sha256',
      'presentation_policy_sha256',
    };
    _expectFields(rawHashes, hashKeys);
    final appliedArtifactHashes = <String, String>{
      for (final key in hashKeys)
        key: _requiredString(rawHashes[key], 'startup $key'),
    };
    if (appliedArtifactHashes.values.any((value) => !_sha256(value))) {
      throw const FormatException(
        'startup applied_artifact_hashes must contain SHA-256 hashes',
      );
    }
    return StartupMetrics(
      device: device,
      loadMs: _nonNegativeFinite(json['load_ms'], 'startup load_ms'),
      warmupMs: _nonNegativeFinite(json['warmup_ms'], 'startup warmup_ms'),
      fallbackReason: fallbackValue == null
          ? null
          : _requiredString(fallbackValue, 'startup fallback_reason'),
      detectorId: _requiredString(json['detector_id'], 'startup detector_id'),
      repvitId: _requiredString(json['repvit_id'], 'startup repvit_id'),
      dinov3Id: _requiredString(json['dinov3_id'], 'startup dinov3_id'),
      fusionPolicyId: _requiredString(
        json['fusion_policy_id'],
        'startup fusion_policy_id',
      ),
      detectorThreshold: _probability(
        json['detector_threshold'],
        'startup detector_threshold',
      ),
      appliedArtifactHashes: appliedArtifactHashes,
    );
  }

  final String device;
  final double loadMs;
  final double warmupMs;
  final String? fallbackReason;
  final String detectorId;
  final String repvitId;
  final String dinov3Id;
  final String fusionPolicyId;
  final double detectorThreshold;
  final Map<String, String> appliedArtifactHashes;
}

enum InferencePresentationState {
  normal,
  unknown,
  needsRetake;

  static InferencePresentationState parse(Object? value) {
    return switch (value) {
      'normal' => InferencePresentationState.normal,
      'unknown' => InferencePresentationState.unknown,
      'needs_retake' => InferencePresentationState.needsRetake,
      _ => throw FormatException('unsupported presentation state: $value'),
    };
  }
}

enum RetakeScope {
  scan,
  object;

  static RetakeScope? parseNullable(Object? value) {
    return switch (value) {
      null => null,
      'scan' => RetakeScope.scan,
      'object' => RetakeScope.object,
      _ => throw FormatException('unsupported retake scope: $value'),
    };
  }
}

enum RetakeInstruction {
  noBreadDetected,
  separateBreads,
  candidateEvidenceWeak;

  static RetakeInstruction? parseNullable(Object? value) {
    return switch (value) {
      null => null,
      'no_bread_detected' => RetakeInstruction.noBreadDetected,
      'separate_breads' => RetakeInstruction.separateBreads,
      'candidate_evidence_weak' => RetakeInstruction.candidateEvidenceWeak,
      _ => throw FormatException('unsupported retake instruction: $value'),
    };
  }
}

final class InferencePresentation {
  InferencePresentation._({
    required this.state,
    required this.finalCountUsable,
    required this.retakeScope,
    required List<String> retakeObjectIds,
    required this.instruction,
    required List<String> candidateObjectIds,
    required this.policyId,
    required this.policySha256,
  }) : retakeObjectIds = List.unmodifiable(retakeObjectIds),
       candidateObjectIds = List.unmodifiable(candidateObjectIds);

  factory InferencePresentation.fromJson(
    Map<String, Object?> json, {
    required List<InferenceObject> objects,
  }) {
    _expectFields(json, const {
      'state',
      'final_count_usable',
      'retake_scope',
      'retake_object_ids',
      'instruction_code',
      'candidate_object_ids',
      'policy_id',
      'policy_sha256',
    });
    final state = InferencePresentationState.parse(json['state']);
    final finalCountUsableValue = json['final_count_usable'];
    if (finalCountUsableValue is! bool) {
      throw const FormatException(
        'presentation final_count_usable must be a boolean',
      );
    }
    final retakeScope = RetakeScope.parseNullable(json['retake_scope']);
    final retakeObjectIds = _objectIdList(
      json['retake_object_ids'],
      'presentation retake_object_ids',
    );
    final instruction = RetakeInstruction.parseNullable(
      json['instruction_code'],
    );
    final candidateObjectIds = _objectIdList(
      json['candidate_object_ids'],
      'presentation candidate_object_ids',
    );
    final policyId = _requiredString(
      json['policy_id'],
      'presentation policy_id',
    );
    if (policyId != 'camera_action_state_v1' &&
        policyId != 'camera_action_state_v2') {
      throw const FormatException('presentation policy_id is invalid');
    }
    final policySha256 = _requiredString(
      json['policy_sha256'],
      'presentation policy_sha256',
    );
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(policySha256)) {
      throw const FormatException(
        'presentation policy_sha256 must be a SHA-256 hash',
      );
    }

    final objectsById = {for (final object in objects) object.objectId: object};
    final namedObjectIds = [...retakeObjectIds, ...candidateObjectIds];
    if (namedObjectIds.toSet().length != namedObjectIds.length ||
        namedObjectIds.any((objectId) => !objectsById.containsKey(objectId))) {
      throw const FormatException(
        'presentation object IDs must be unique existing object IDs',
      );
    }
    if (candidateObjectIds.any(
      (objectId) => !objectsById[objectId]!.isUnknown,
    )) {
      throw const FormatException(
        'presentation candidate IDs must identify Unknown objects',
      );
    }

    switch (state) {
      case InferencePresentationState.normal:
        if (!finalCountUsableValue ||
            retakeScope != null ||
            instruction != null ||
            retakeObjectIds.isNotEmpty ||
            candidateObjectIds.isNotEmpty) {
          throw const FormatException(
            'normal presentation state is inconsistent',
          );
        }
      case InferencePresentationState.unknown:
        if (!finalCountUsableValue ||
            retakeScope != null ||
            instruction != null ||
            retakeObjectIds.isNotEmpty ||
            candidateObjectIds.isEmpty) {
          throw const FormatException(
            'unknown presentation state is inconsistent',
          );
        }
      case InferencePresentationState.needsRetake:
        if (finalCountUsableValue ||
            retakeScope == null ||
            candidateObjectIds.isNotEmpty) {
          throw const FormatException(
            'needs_retake presentation state is inconsistent',
          );
        }
        switch (retakeScope) {
          case RetakeScope.scan:
            if (retakeObjectIds.isNotEmpty ||
                instruction != RetakeInstruction.noBreadDetected) {
              throw const FormatException(
                'scan retake presentation state is inconsistent',
              );
            }
          case RetakeScope.object:
            if (retakeObjectIds.isEmpty ||
                (policyId == 'camera_action_state_v2'
                    ? instruction != RetakeInstruction.separateBreads
                    : instruction != RetakeInstruction.separateBreads &&
                          instruction !=
                              RetakeInstruction.candidateEvidenceWeak)) {
              throw const FormatException(
                'object retake presentation state is inconsistent',
              );
            }
        }
    }

    return InferencePresentation._(
      state: state,
      finalCountUsable: finalCountUsableValue,
      retakeScope: retakeScope,
      retakeObjectIds: retakeObjectIds,
      instruction: instruction,
      candidateObjectIds: candidateObjectIds,
      policyId: policyId,
      policySha256: policySha256,
    );
  }

  final InferencePresentationState state;
  final bool finalCountUsable;
  final RetakeScope? retakeScope;
  final List<String> retakeObjectIds;
  final RetakeInstruction? instruction;
  final List<String> candidateObjectIds;
  final String policyId;
  final String policySha256;
}

final class InferenceResult {
  InferenceResult._({
    required this.requestId,
    required this.imageWidth,
    required this.imageHeight,
    required this.device,
    required List<InferenceObject> objects,
    required Map<int, int> counts,
    required this.unknownCount,
    required this.presentation,
    required this.timings,
    required this.diagnostics,
  }) : objects = List.unmodifiable(objects),
       counts = UnmodifiableMapView(counts);

  factory InferenceResult.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {
      'type',
      'request_id',
      'image',
      'device',
      'objects',
      'counts',
      'unknown_count',
      'presentation',
      'timings_ms',
      'diagnostics',
    });
    if (json['type'] != 'result') {
      throw const FormatException('inference result type must be result');
    }
    final requestId = _requiredString(json['request_id'], 'request_id');
    final image = _map(json['image'], 'image');
    _expectFields(image, const {'width', 'height'});
    final imageWidth = _positiveFinite(image['width'], 'image width');
    final imageHeight = _positiveFinite(image['height'], 'image height');
    final device = _requiredString(json['device'], 'result device');
    final objectValues = _list(json['objects'], 'objects');
    final objects = <InferenceObject>[
      for (var index = 0; index < objectValues.length; index += 1)
        InferenceObject.fromJson(
          _map(objectValues[index], 'object'),
          index: index + 1,
          imageWidth: imageWidth,
          imageHeight: imageHeight,
        ),
    ];
    if (objects.map((object) => object.objectId).toSet().length !=
        objects.length) {
      throw const FormatException('object IDs must be unique');
    }

    final countsJson = _map(json['counts'], 'counts');
    final counts = <int, int>{};
    for (final entry in countsJson.entries) {
      final skuId = int.tryParse(entry.key);
      if (skuId == null || entry.key != '$skuId') {
        throw const FormatException(
          'count keys must be canonical integer SKU IDs',
        );
      }
      _skuId(skuId, 'count SKU ID');
      counts[skuId] = _positiveInt(entry.value, 'SKU count');
    }
    final unknownCount = _nonNegativeInt(
      json['unknown_count'],
      'unknown_count',
    );
    final expectedCounts = <int, int>{};
    for (final object in objects.where((object) => !object.isUnknown)) {
      final skuId = object.skuId!;
      expectedCounts[skuId] = (expectedCounts[skuId] ?? 0) + 1;
    }
    final expectedUnknown = objects.where((object) => object.isUnknown).length;
    if (!_equalIntMaps(counts, expectedCounts) ||
        unknownCount != expectedUnknown ||
        counts.values.fold<int>(0, (sum, count) => sum + count) +
                unknownCount !=
            objects.length) {
      throw const FormatException(
        'result counts do not match final registered and Unknown objects',
      );
    }

    return InferenceResult._(
      requestId: requestId,
      imageWidth: imageWidth,
      imageHeight: imageHeight,
      device: device,
      objects: objects,
      counts: counts,
      unknownCount: unknownCount,
      presentation: InferencePresentation.fromJson(
        _map(json['presentation'], 'presentation'),
        objects: objects,
      ),
      timings: StageTimings.fromJson(_map(json['timings_ms'], 'timings_ms')),
      diagnostics: InferenceDiagnostics.fromJson(
        _map(json['diagnostics'], 'diagnostics'),
        actualObjectCount: objects.length,
      ),
    );
  }

  final String requestId;
  final double imageWidth;
  final double imageHeight;
  final String device;
  final List<InferenceObject> objects;
  final Map<int, int> counts;
  final int unknownCount;
  final InferencePresentation presentation;
  final StageTimings timings;
  final InferenceDiagnostics diagnostics;

  int get registeredCount =>
      counts.values.fold<int>(0, (sum, count) => sum + count);
}

sealed class WorkerEvent {
  const WorkerEvent();

  factory WorkerEvent.fromJson(Map<String, Object?> json) {
    final type = _requiredString(json['type'], 'event type');
    return switch (type) {
      'loading' => StartupWorkerEvent.fromJson(json, WorkerStatus.loading),
      'warming' => StartupWorkerEvent.fromJson(json, WorkerStatus.warming),
      'ready' => ReadyWorkerEvent.fromJson(json),
      'progress' => ProgressWorkerEvent.fromJson(json),
      'result' => ResultWorkerEvent(InferenceResult.fromJson(json)),
      'error' => WorkerErrorEvent.fromJson(json),
      'fatal' => FatalWorkerEvent.fromJson(json),
      'pong' => PongWorkerEvent.fromJson(json),
      'stopped' => StoppedWorkerEvent.fromJson(json),
      _ => throw FormatException('unsupported worker event type: $type'),
    };
  }
}

final class StartupWorkerEvent extends WorkerEvent {
  const StartupWorkerEvent({required this.status, required this.device});

  factory StartupWorkerEvent.fromJson(
    Map<String, Object?> json,
    WorkerStatus status,
  ) {
    _expectFields(json, const {'type'}, optional: const {'device'});
    final expectedType = status == WorkerStatus.loading ? 'loading' : 'warming';
    if (json['type'] != expectedType) {
      throw const FormatException('startup event type does not match status');
    }
    final deviceValue = json['device'];
    return StartupWorkerEvent(
      status: status,
      device: deviceValue == null
          ? null
          : _requiredString(deviceValue, 'startup device'),
    );
  }

  final WorkerStatus status;
  final String? device;
}

final class ReadyWorkerEvent extends WorkerEvent {
  const ReadyWorkerEvent({
    required this.device,
    required this.metrics,
    this.codeIdentity,
  });

  factory ReadyWorkerEvent.fromJson(Map<String, Object?> json) {
    _expectFields(
      json,
      const {'type', 'device'},
      optional: const {'startup_metrics', 'code_identity'},
    );
    final metricsValue = json['startup_metrics'];
    final metrics = metricsValue == null
        ? null
        : StartupMetrics.fromJson(_map(metricsValue, 'startup_metrics'));
    final device = _requiredString(json['device'], 'ready device');
    if (metrics != null && metrics.device != device) {
      throw const FormatException(
        'ready device does not match startup metrics',
      );
    }
    final identityValue = json['code_identity'];
    return ReadyWorkerEvent(
      device: device,
      metrics: metrics,
      codeIdentity: identityValue == null
          ? null
          : WorkerCodeIdentity.fromJson(_map(identityValue, 'code_identity')),
    );
  }

  final String device;
  final StartupMetrics? metrics;
  final WorkerCodeIdentity? codeIdentity;
}

/// Optional for legacy workers; schema-v2 evidence workers require it upstream.
final class WorkerCodeIdentity {
  const WorkerCodeIdentity({
    required this.codeCommit,
    required this.codeIdentitySha256,
  });

  factory WorkerCodeIdentity.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {'code_commit', 'code_identity_sha256'});
    final commit = _requiredString(json['code_commit'], 'code commit');
    if (!_lowerHex(commit) || (commit.length != 40 && commit.length != 64)) {
      throw const FormatException('code commit must be lowercase Git hex');
    }
    final identity = _requiredString(
      json['code_identity_sha256'],
      'code identity SHA-256',
    );
    if (!_sha256(identity)) {
      throw const FormatException('code identity must be lowercase SHA-256');
    }
    return WorkerCodeIdentity(
      codeCommit: commit,
      codeIdentitySha256: identity,
    );
  }

  final String codeCommit;
  final String codeIdentitySha256;
}

final class ProgressWorkerEvent extends WorkerEvent {
  const ProgressWorkerEvent({required this.requestId, required this.phase});

  factory ProgressWorkerEvent.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {'type', 'request_id', 'phase'});
    return ProgressWorkerEvent(
      requestId: _requiredString(json['request_id'], 'progress request_id'),
      phase: WorkerPhase.parse(json['phase']),
    );
  }

  final String requestId;
  final WorkerPhase phase;
}

final class ResultWorkerEvent extends WorkerEvent {
  const ResultWorkerEvent(this.result);

  final InferenceResult result;
}

final class WorkerErrorEvent extends WorkerEvent {
  const WorkerErrorEvent({
    required this.requestId,
    required this.code,
    required this.message,
  });

  factory WorkerErrorEvent.fromJson(Map<String, Object?> json) {
    _expectFields(
      json,
      const {'type', 'code', 'message'},
      optional: const {'request_id'},
    );
    final requestIdValue = json['request_id'];
    return WorkerErrorEvent(
      requestId: requestIdValue == null
          ? null
          : _requiredString(requestIdValue, 'error request_id'),
      code: _requiredString(json['code'], 'error code'),
      message: _requiredString(json['message'], 'error message'),
    );
  }

  final String? requestId;
  final String code;
  final String message;
}

final class FatalWorkerEvent extends WorkerEvent {
  const FatalWorkerEvent({required this.code, required this.message});

  factory FatalWorkerEvent.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {'type', 'code', 'message'});
    return FatalWorkerEvent(
      code: _requiredString(json['code'], 'fatal code'),
      message: _requiredString(json['message'], 'fatal message'),
    );
  }

  final String code;
  final String message;
}

final class PongWorkerEvent extends WorkerEvent {
  const PongWorkerEvent(this.requestId);

  factory PongWorkerEvent.fromJson(Map<String, Object?> json) {
    _expectFields(json, const {'type', 'request_id'});
    return PongWorkerEvent(
      _requiredString(json['request_id'], 'pong request_id'),
    );
  }

  final String requestId;
}

final class StoppedWorkerEvent extends WorkerEvent {
  const StoppedWorkerEvent(this.requestId, {this.codeIdentity});

  factory StoppedWorkerEvent.fromJson(Map<String, Object?> json) {
    _expectFields(
      json,
      const {'type'},
      optional: const {'request_id', 'code_identity'},
    );
    final requestIdValue = json['request_id'];
    final identityValue = json['code_identity'];
    return StoppedWorkerEvent(
      requestIdValue == null
          ? null
          : _requiredString(requestIdValue, 'stopped request_id'),
      codeIdentity: identityValue == null
          ? null
          : WorkerCodeIdentity.fromJson(_map(identityValue, 'code_identity')),
    );
  }

  final String? requestId;
  final WorkerCodeIdentity? codeIdentity;
}

Map<String, Object?> _parseProvenance(Map<String, Object?> json) {
  const fields = {
    'detector_id',
    'repvit_artifact_id',
    'repvit_sha256',
    'repvit_manifest_sha256',
    'repvit_prototype_sha256',
    'dinov3_artifact_id',
    'dinov3_sha256',
    'dinov3_support_sha256',
    'calibration_id',
    'calibration_sha256',
    'preprocess_sha256',
    'canonical_frame_version',
    'exif_orientation',
    'failure_code',
  };
  _expectFields(json, fields);
  for (final field in const {
    'detector_id',
    'repvit_artifact_id',
    'dinov3_artifact_id',
    'calibration_id',
  }) {
    _requiredString(json[field], 'provenance $field');
  }
  final shaPattern = RegExp(r'^[0-9a-f]{64}$');
  for (final field in const {
    'repvit_sha256',
    'repvit_manifest_sha256',
    'repvit_prototype_sha256',
    'dinov3_sha256',
    'dinov3_support_sha256',
    'calibration_sha256',
    'preprocess_sha256',
  }) {
    final value = _requiredString(json[field], 'provenance $field');
    if (!shaPattern.hasMatch(value)) {
      throw FormatException('provenance $field must be a SHA-256 hash');
    }
  }
  if (json['canonical_frame_version'] != 'exif_visual_rgb_v1') {
    throw const FormatException('canonical frame version is invalid');
  }
  final orientation = _positiveInt(
    json['exif_orientation'],
    'EXIF orientation',
  );
  if (orientation > 8) {
    throw const FormatException('EXIF orientation must be between 1 and 8');
  }
  final failureCode = json['failure_code'];
  if (failureCode != null) {
    _requiredString(failureCode, 'provenance failure_code');
  }
  return Map<String, Object?>.from(json);
}

List<double> _box(
  Object? value, {
  required double imageWidth,
  required double imageHeight,
}) {
  final values = _list(value, 'bbox_xyxy');
  if (values.length != 4) {
    throw const FormatException('bbox_xyxy must contain four coordinates');
  }
  final box = <double>[
    for (var index = 0; index < values.length; index += 1)
      _finite(values[index], 'bbox coordinate $index'),
  ];
  if (box[0] < 0 ||
      box[1] < 0 ||
      box[2] > imageWidth ||
      box[3] > imageHeight ||
      box[0] >= box[2] ||
      box[1] >= box[3]) {
    throw const FormatException(
      'bbox_xyxy must be valid and inside the canonical image',
    );
  }
  return box;
}

void _expectFields(
  Map<String, Object?> json,
  Set<String> required, {
  Set<String> optional = const {},
}) {
  if (!json.keys.toSet().containsAll(required) ||
      json.keys.any(
        (key) => !required.contains(key) && !optional.contains(key),
      )) {
    throw const FormatException('JSON fields do not match the protocol');
  }
}

Map<String, Object?> _map(Object? value, String name) {
  if (value is! Map) {
    throw FormatException('$name must be a JSON object');
  }
  if (value.keys.any((key) => key is! String)) {
    throw FormatException('$name keys must be strings');
  }
  return Map<String, Object?>.from(value);
}

List<Object?> _list(Object? value, String name) {
  if (value is! List) {
    throw FormatException('$name must be a JSON array');
  }
  return List<Object?>.from(value);
}

List<String> _objectIdList(Object? value, String name) {
  final values = _list(value, name);
  final ids = [
    for (final value in values) _requiredString(value, '$name entry'),
  ];
  if (ids.toSet().length != ids.length) {
    throw FormatException('$name entries must be unique');
  }
  return ids;
}

String _requiredString(Object? value, String name) {
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('$name must be a non-empty string');
  }
  return value;
}

bool _lowerHex(String value) =>
    value.isNotEmpty && RegExp(r'^[0-9a-f]+$').hasMatch(value);

bool _sha256(String value) => value.length == 64 && _lowerHex(value);

int _positiveInt(Object? value, String name) {
  if (value is! int || value <= 0) {
    throw FormatException('$name must be a positive integer');
  }
  return value;
}

int _skuId(Object? value, String name) {
  if (value is! int || value < 1 || value > 20) {
    throw FormatException('$name must be between 1 and 20');
  }
  return value;
}

int _nonNegativeInt(Object? value, String name) {
  if (value is! int || value < 0) {
    throw FormatException('$name must be a non-negative integer');
  }
  return value;
}

double _finite(Object? value, String name) {
  if (value is! num || !value.isFinite) {
    throw FormatException('$name must be finite');
  }
  return value.toDouble();
}

double _positiveFinite(Object? value, String name) {
  final parsed = _finite(value, name);
  if (parsed <= 0) {
    throw FormatException('$name must be positive');
  }
  return parsed;
}

double _nonNegativeFinite(Object? value, String name) {
  final parsed = _finite(value, name);
  if (parsed < 0) {
    throw FormatException('$name must be non-negative');
  }
  return parsed;
}

double _probability(Object? value, String name) {
  final parsed = _finite(value, name);
  if (parsed < 0 || parsed > 1) {
    throw FormatException('$name must be between 0 and 1');
  }
  return parsed;
}

bool _equalIntMaps(Map<int, int> left, Map<int, int> right) {
  if (left.length != right.length) {
    return false;
  }
  return left.entries.every((entry) => right[entry.key] == entry.value);
}
