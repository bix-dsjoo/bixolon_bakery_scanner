import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../admin/admin_models.dart';
import '../audit/audit_file_store.dart';
import '../camera/camera_service.dart';
import '../catalog/catalog_seed.dart';
import '../checkout/checkout_controller.dart';
import '../checkout/checkout_models.dart';
import '../checkout/simulated_payment_service.dart';
import '../inference/inference_launch_config.dart';
import '../inference/inference_worker_client.dart';
import '../persistence/database_catalog_repository.dart';
import '../persistence/database_admin_repository.dart';
import '../persistence/database_checkout_audit_store.dart';
import '../persistence/database_factory.dart';
import '../scanner/scanner_controller.dart';
import '../ui/app_theme.dart';
import '../ui/admin/admin_destination.dart';
import '../ui/admin/dashboard_screen.dart';
import '../ui/admin/transaction_history_screen.dart';
import 'app_mode_controller.dart';
import 'app_mode_surface.dart';

/// Production composition root. Customer screens never receive the model
/// transport or artifact details; those remain in the audited persistence path.
class BakeryApp extends StatefulWidget {
  const BakeryApp({super.key});

  @override
  State<BakeryApp> createState() => _BakeryAppState();
}

class _BakeryAppState extends State<BakeryApp> {
  Future<_AppServices>? _bootstrap;

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
    home: FutureBuilder<_AppServices>(
      future: _bootstrap,
      builder: (context, snapshot) {
        if (snapshot.hasData) {
          final services = snapshot.requireData;
          return BakeryAppSurface(
            checkout: services.checkout,
            customerLifecycle: _CheckoutCustomerModeLifecycle(
              services.checkout,
            ),
            adminDestinationBuilder: (context, destination, onAttention) =>
                _adminDestination(
                  context,
                  destination,
                  services.admin,
                  onAttention,
                ),
          );
        }
        if (snapshot.hasError) return const _UnavailableBootstrapScreen();
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      },
    ),
  );

  Future<_AppServices> _createCheckout() async {
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
      return _AppServices(
        checkout: controller,
        admin: DatabaseAdminRepository(
          database,
          verifyEvidence: (relativePath, sha256, byteSize) async {
            try {
              await auditFiles.verifyExisting(
                relativePath: relativePath,
                sha256: sha256,
                byteSize: byteSize,
              );
              return AuditEvidenceIntegrity.retained;
            } on StateError catch (error) {
              return error.toString().contains('does not exist')
                  ? AuditEvidenceIntegrity.missing
                  : AuditEvidenceIntegrity.hashMismatch;
            }
          },
        ),
      );
    } catch (_) {
      await database.close();
      rethrow;
    }
  }

  Widget _adminDestination(
    BuildContext context,
    AdminDestination destination,
    DatabaseAdminRepository admin,
    ValueChanged<AttentionItem> onAttentionSelected,
  ) {
    if (destination == AdminDestination.dashboard) {
      return DashboardScreen(
        repository: admin,
        range: _seoulTodayRange(),
        onAttentionSelected: onAttentionSelected,
      );
    }
    if (destination == AdminDestination.transactions) {
      return TransactionHistoryScreen(repository: admin);
    }
    return Center(
      child: Text(
        '${destination.label} 화면을 준비하고 있어요.',
        style: Theme.of(context).textTheme.bodyLarge,
      ),
    );
  }
}

final class _AppServices {
  const _AppServices({required this.checkout, required this.admin});

  final CheckoutController checkout;
  final DatabaseAdminRepository admin;
}

DateRange _seoulTodayRange() {
  const seoulOffset = Duration(hours: 9);
  final seoulNow = DateTime.now().toUtc().add(seoulOffset);
  final localStart = DateTime.utc(seoulNow.year, seoulNow.month, seoulNow.day);
  return DateRange.utc(
    localStart.subtract(seoulOffset),
    localStart.add(const Duration(days: 1)).subtract(seoulOffset),
  );
}

final class _CheckoutCustomerModeLifecycle implements CustomerModeLifecycle {
  const _CheckoutCustomerModeLifecycle(this._checkout);

  final CheckoutController _checkout;

  @override
  bool get hasActiveCustomerCheckout => _checkout.hasActiveCustomerCheckout;

  @override
  Future<void> abandonForAdminEntry(String reason) {
    if (reason != 'admin_mode_entered') {
      throw ArgumentError.value(reason, 'reason', 'is not an admin entry');
    }
    return _checkout.abandonForAdminEntry();
  }

  @override
  Future<void> startFreshCustomerSession() =>
      _checkout.startFreshCustomerSession();
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
