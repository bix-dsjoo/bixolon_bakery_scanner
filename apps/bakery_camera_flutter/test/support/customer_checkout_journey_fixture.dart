import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/audit/audit_file_store.dart';
import 'package:bakery_camera_prototype/src/camera/camera_service.dart';
import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_controller.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_catalog_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_checkout_audit_store.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:camera/camera.dart';
import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart' show Value;

import 'inference_fixtures.dart';

/// Real database, audit-files, camera and worker seams for the customer
/// journey. The only fakes are physical capture and worker protocol edges.
final class CustomerCheckoutJourneyFixture {
  CustomerCheckoutJourneyFixture._({
    required this.database,
    required this.files,
    required this.controller,
    required this.captureSha256,
    required this.inferenceReceiptSha256,
    required this._temporaryDirectory,
  });

  final BakeryDatabase database;
  final AuditFileStore files;
  final CheckoutController controller;
  final String captureSha256;
  final String inferenceReceiptSha256;
  final Directory _temporaryDirectory;
  bool customerReturnedToReady = false;

  static Future<CustomerCheckoutJourneyFixture> create({
    bool includeUnchangedRegisteredObject = false,
  }) async {
    final temporaryDirectory = await Directory.systemTemp.createTemp(
      'customer-checkout-journey-',
    );
    final capture = File(
      '${temporaryDirectory.path}${Platform.pathSeparator}capture.jpg',
    );
    await capture.writeAsBytes(const [9, 4, 2, 7], flush: true);
    final database = openInMemoryBakeryDatabase();
    final revision = CatalogRevision(
      revisionId: 'catalog-v1',
      sha256: _hash('9'),
      createdAt: DateTime.utc(2026, 7, 30),
    );
    await _seedCatalog(database, revision);
    final files = AuditFileStore(
      Directory('${temporaryDirectory.path}${Platform.pathSeparator}audit'),
    );
    final runtime = _runtimeSnapshot();
    var nextId = 0;
    final audit = DatabaseCheckoutAuditStore(
      database: database,
      runtimeSnapshot: runtime,
      references: AuditFileStoreReferenceVerifier(files),
      createId: (_) => _uuid(++nextId),
      now: () => DateTime.utc(2026, 7, 30, 12),
    );
    final result = buildUiInferenceResult(
      includeUnchangedRegisteredObject: includeUnchangedRegisteredObject,
    );
    final receiptJson = canonicalInferenceReceiptJson(
      result: result,
      runtimeSnapshot: runtime,
    );
    final controller = CheckoutController(
      scanner: ScannerController(
        camera: _JourneyCamera(capture.path),
        worker: _JourneyWorker(result),
        readImageSize: (_) async =>
            const CapturedImageSize(width: 1920, height: 1080),
      ),
      auditStore: audit,
      evidenceStore: AuditFileCheckoutEvidenceStore(files),
      displayPathResolver: files,
      catalogRepository: DatabaseCatalogRepository(database),
      createInferenceReceipt: (_) => ImmutableJsonReceipt(
        canonicalJson: receiptJson,
        sha256: sha256.convert(utf8.encode(receiptJson)).toString(),
      ),
      now: () => DateTime.utc(2026, 7, 30, 12),
    );
    return CustomerCheckoutJourneyFixture._(
      database: database,
      files: files,
      controller: controller,
      captureSha256: sha256.convert(const [9, 4, 2, 7]).toString(),
      inferenceReceiptSha256: sha256
          .convert(utf8.encode(receiptJson))
          .toString(),
      temporaryDirectory: temporaryDirectory,
    );
  }

  Future<void> completeRegisteredUnknownAndManualCartPurchase() async {
    await controller.initialize();
    await controller.scan();
    await controller.chooseTop3('object-2', 10);
    await controller.continueToOrderReview();
    await controller.addManualProduct('milk-bread');
    await controller.setQuantity('milk-bread', 2);
    await controller.pay();
    await controller.startNextCustomer();
    customerReturnedToReady = controller.state.phase == CheckoutPhase.ready;
  }

  Future<bool> hasVerifiedAuditEvidence(ScanAttemptRow attempt) async {
    final receiptPath = attempt.receiptRelativePath;
    final receiptSha = attempt.receiptSha256;
    if (receiptPath == null || receiptSha == null) return false;
    await files.verifyExisting(
      relativePath: attempt.imageRelativePath,
      byteSize: attempt.imageByteSize,
      sha256: attempt.imageSha256,
    );
    await files.verifyExisting(
      relativePath: receiptPath,
      byteSize: attempt.receiptByteSize,
      sha256: receiptSha,
    );
    return true;
  }

  Future<void> dispose() async {
    await controller.close();
    await database.close();
    if (await _temporaryDirectory.exists()) {
      await _temporaryDirectory.delete(recursive: true);
    }
  }
}

Future<void> _seedCatalog(
  BakeryDatabase database,
  CatalogRevision revision,
) async {
  await database
      .into(database.catalogRevisions)
      .insert(
        CatalogRevisionsCompanion.insert(
          revisionId: revision.revisionId,
          sha256: revision.sha256,
          createdAtUs: revision.createdAt.microsecondsSinceEpoch,
          isActive: true,
        ),
      );
  const products = [
    ('croissant', '크루아상', 2800, 6, 'pastry', 1),
    ('sugar-donut', '슈가 도넛', 2500, 10, 'donut', 2),
    ('milk-bread', '우유 식빵', 1300, null, 'bread', 3),
  ];
  for (final product in products) {
    await database
        .into(database.products)
        .insert(
          ProductsCompanion.insert(
            productRevisionId: '${revision.revisionId}/${product.$1}',
            catalogRevisionId: revision.revisionId,
            productId: product.$1,
            displayName: product.$2,
            unitPriceKrw: product.$3,
            recognitionSkuId: Value(product.$4),
            categoryId: product.$5,
            active: true,
            sortOrder: product.$6,
          ),
        );
  }
}

AuditRuntimeSnapshot _runtimeSnapshot() => AuditRuntimeSnapshot(
  detectorId: 'rfdetr_large_bakery_v1',
  detectorSha256: _hash('b'),
  repvitArtifactId: 'repvit_m1_15plus5_v1',
  repvitSha256: _hash('a'),
  repvitManifestSha256: _hash('b'),
  repvitPrototypeSha256: _hash('c'),
  dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
  dinov3Sha256: _hash('d'),
  dinov3SupportSha256: _hash('e'),
  calibrationId: 'policy-v1',
  calibrationSha256: _hash('f'),
  preprocessSha256: _hash('0'),
  fusionPolicyId: 'fusion-v1',
  fusionPolicySha256: _hash('3'),
  configSnapshotJson: '{"pipeline":"canonical_cpu"}',
  startupDevice: 'cpu',
  startupLoadMs: 1,
  startupWarmupMs: 1,
);

String _hash(String value) => value * 64;
String _uuid(int value) =>
    '00000000-0000-4000-8000-${value.toString().padLeft(12, '0')}';

final class _JourneyCamera implements CameraSession {
  _JourneyCamera(this._capturePath);

  final String _capturePath;
  final _errors = StreamController<String>.broadcast(sync: true);
  bool _ready = false;

  @override
  Stream<String> get errors => _errors.stream;
  @override
  bool get isReady => _ready;
  @override
  String? get lastError => _ready ? null : 'camera unavailable';
  @override
  CameraController? get previewController => null;
  @override
  Future<bool> initialize() async => _ready = true;
  @override
  Future<CapturedFrame> captureStill() async => CapturedFrame(_capturePath);
  @override
  Future<void> releaseCapture(String absolutePath) async {}
  @override
  Future<bool> reconnect() async => _ready;
  @override
  Future<void> close() => _errors.close();
}

final class _JourneyWorker implements InferenceSession {
  _JourneyWorker(this._result);

  final InferenceResult _result;
  final _events = StreamController<WorkerEvent>.broadcast(sync: true);
  WorkerStatus _status = WorkerStatus.notStarted;

  @override
  Stream<WorkerEvent> get events => _events.stream;
  @override
  WorkerStatus get status => _status;
  @override
  Future<void> start() async => _status = WorkerStatus.ready;
  @override
  Future<InferenceResult> analyze(String imagePath) async => _result;
  @override
  Future<void> shutdown() async {
    _status = WorkerStatus.stopped;
    await _events.close();
  }
}
