import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../audit/audit_file_store.dart';
import '../camera/camera_service.dart';
import '../catalog/catalog_seed.dart';
import '../checkout/checkout_controller.dart';
import '../checkout/checkout_models.dart';
import '../checkout/simulated_payment_service.dart';
import '../inference/inference_launch_config.dart';
import '../inference/inference_worker_client.dart';
import '../persistence/database_catalog_repository.dart';
import '../persistence/database_checkout_audit_store.dart';
import '../persistence/database_factory.dart';
import '../scanner/scanner_controller.dart';
import '../ui/app_theme.dart';
import '../ui/customer/customer_checkout_screen.dart';

/// Production composition root. Customer screens never receive the model
/// transport or artifact details; those remain in the audited persistence path.
class BakeryApp extends StatefulWidget {
  const BakeryApp({super.key});

  @override
  State<BakeryApp> createState() => _BakeryAppState();
}

class _BakeryAppState extends State<BakeryApp> {
  Future<CheckoutController>? _bootstrap;

  @override
  void initState() {
    super.initState();
    _bootstrap = _createCheckout();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'BIXOLON Bakery',
    debugShowCheckedModeBanner: false,
    theme: buildBakeryTheme(),
    home: FutureBuilder<CheckoutController>(
      future: _bootstrap,
      builder: (context, snapshot) {
        if (snapshot.hasData) {
          return CustomerCheckoutScreen(controller: snapshot.requireData);
        }
        if (snapshot.hasError) return const _UnavailableBootstrapScreen();
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      },
    ),
  );

  Future<CheckoutController> _createCheckout() async {
    final database = openProductionBakeryDatabase();
    try {
      await CatalogSeed(database).installIfEmpty();
      final support = await getApplicationSupportDirectory();
      final auditFiles = AuditFileStore(
        Directory(path.join(support.path, 'audit')),
      );
      final config = InferenceLaunchConfig.resolve(
        environment: Platform.environment,
        executablePath: Platform.resolvedExecutable,
      );
      final scanner = ScannerController(
        camera: CameraService(),
        worker: InferenceWorkerSession(InferenceWorkerClient(config: config)),
      );
      final runtime = _lockedRuntimeSnapshot();
      final store = DatabaseCheckoutAuditStore(
        database: database,
        runtimeSnapshot: runtime,
        references: AuditFileStoreReferenceVerifier(auditFiles),
        createId: (_) => const Uuid().v4(),
        now: DateTime.now,
      );
      final controller = CheckoutController(
        scanner: scanner,
        auditStore: store,
        evidenceStore: AuditFileCheckoutEvidenceStore(auditFiles),
        displayPathResolver: auditFiles,
        catalogRepository: DatabaseCatalogRepository(database),
        createInferenceReceipt: (result) {
          final canonicalJson = canonicalInferenceReceiptJson(
            result: result,
            runtimeSnapshot: runtime,
          );
          return ImmutableJsonReceipt(
            canonicalJson: canonicalJson,
            sha256: sha256.convert(utf8.encode(canonicalJson)).toString(),
          );
        },
        paymentService: SimulatedPaymentService(
          auditStore: store,
          clock: DateTime.now,
          createId: (_) => const Uuid().v4(),
        ),
      );
      await controller.initialize();
      return controller;
    } catch (_) {
      await database.close();
      rethrow;
    }
  }
}

AuditRuntimeSnapshot _lockedRuntimeSnapshot() => AuditRuntimeSnapshot(
  detectorId: 'rfdetr_large_bakery_v1',
  detectorSha256:
      '1e1588a8677d6211ee5733223afa48a65e45743b563c824362d41d67ee15fd33',
  repvitArtifactId: 'repvit_m1_15plus5_v1',
  repvitSha256:
      '0369c148c3b208ea41140cc220a6871367eaa8ed52b0cedfa97d39f4b2d76cfc',
  repvitManifestSha256:
      'cb0c8594c723461e11b7e8db8fffffe2d7249b0d5f3d07f3e5503ae040798d18',
  repvitPrototypeSha256:
      '2a970f99bda1ba1623a650b47a549de251680573c722a921ed3d999d5bbfdc77',
  dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
  dinov3Sha256:
      '08c60483bc63c04f533611e34bf70b120eedb7240f469bc16e9e20bf344b941d',
  dinov3SupportSha256:
      'c2afaa2c2cca5e27179799f7cdedb21bab2034d812bf3ad9bf502458be353730',
  calibrationId: 'policy_v2_manifest_rebound_cpu_smoke',
  calibrationSha256:
      '213b08c536d4a344ab115f1acf8e7fc7d6b7da87646c5ae5b39e0e2688f29221',
  preprocessSha256:
      '69857c8c27bfc654207969c372f114569a8ce81f1040b27f47ec2613287ae73b',
  fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
  fusionPolicySha256:
      '06c692d5b35583bfd99498805da474b7e9dfa7c8c36eeed04307695f7e885dcc',
  configSnapshotJson: '{"pipeline":"rfdetr_l_repvit_m1_dinov3_vits16_cpu"}',
  startupDevice: 'cpu',
  startupLoadMs: 0,
  startupWarmupMs: 0,
);

class _UnavailableBootstrapScreen extends StatelessWidget {
  const _UnavailableBootstrapScreen();

  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: Text('계산대를 준비하지 못했어요. 직원에게 알려주세요.')));
}
