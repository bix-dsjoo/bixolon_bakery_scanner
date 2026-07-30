import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../admin/admin_models.dart';
import '../admin/diagnostics_models.dart';
import '../admin/diagnostics_service.dart';
import '../admin/retention_service.dart';
import '../admin/review_service.dart';
import '../admin/product_management_service.dart';
import '../admin/settings_service.dart';
import '../audit/audit_file_store.dart';
import '../camera/camera_service.dart';
import '../catalog/catalog_seed.dart';
import '../catalog/catalog_photo_store.dart';
import '../checkout/checkout_controller.dart';
import '../checkout/checkout_models.dart';
import '../checkout/simulated_payment_service.dart';
import '../inference/inference_launch_config.dart';
import '../inference/inference_models.dart';
import '../inference/inference_worker_client.dart';
import '../persistence/database_catalog_repository.dart';
import '../persistence/database_admin_repository.dart';
import '../persistence/database_checkout_audit_store.dart';
import '../persistence/database_factory.dart';
import '../scanner/scanner_controller.dart';
import '../ui/app_theme.dart';
import '../ui/admin/admin_destination.dart';
import '../ui/admin/dashboard_screen.dart';
import '../ui/admin/diagnostics_screen.dart';
import '../ui/admin/transaction_history_screen.dart';
import '../ui/admin/review_inbox_screen.dart';
import '../ui/admin/product_management_screen.dart';
import '../ui/admin/settings_screen.dart';
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
            adminDestinationBuilder:
                (context, destination, onAttention, initialSessionId) =>
                    _adminDestination(
                      context,
                      destination,
                      services.admin,
                      services.reviews,
                      services.products,
                      services.diagnostics,
                      services.settings,
                      services.retention,
                      services.dashboardReadiness,
                      onAttention,
                      initialSessionId,
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
      final workerClient = InferenceWorkerClient(config: config);
      final scanner = ScannerController(
        camera: CameraService(),
        worker: InferenceWorkerSession(workerClient),
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
      final diagnostics = DiagnosticsService.live(
        liveState: () => _diagnosticsLiveState(
          scanner.state,
          workerClient.diagnosticSnapshot,
        ),
        expectedArtifacts: _diagnosticsExpectedArtifacts(runtime),
        audit: DatabaseDiagnosticsAuditReader(
          database: database,
          auditRoot: auditFiles.rootPath,
        ),
      );
      final dashboardReadiness = DashboardReadinessController.watch(
        liveChanges: scanner,
        load: () async =>
            switch ((await diagnostics.refresh()).customerImpact) {
              DiagnosticsCustomerImpact.ready => DashboardAvailability.ready,
              DiagnosticsCustomerImpact.actionRequired =>
                DashboardAvailability.unavailable,
            },
      );
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
        reviews: DatabaseReviewService(
          database,
          createId: (_) => const Uuid().v4(),
          now: DateTime.now,
        ),
        products: ProductManagementService(
          database: database,
          createId: () => const Uuid().v4(),
          now: DateTime.now,
          photoStore: CatalogPhotoStore(
            support,
            forbiddenArtifactHashes: await _generatedUiIllustrationHashes(),
          ),
        ),
        diagnostics: diagnostics,
        dashboardReadiness: dashboardReadiness,
        settings: SettingsService(
          database: database,
          createId: () => const Uuid().v4(),
          now: DateTime.now,
        ),
        retention: RetentionService(
          database: database,
          evidenceRoot: Directory(auditFiles.rootPath),
          createId: () => const Uuid().v4(),
          now: DateTime.now,
          isSafeToRun: () => !controller.hasActiveCustomerCheckout,
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
    DatabaseReviewService reviews,
    ProductManagementService products,
    DiagnosticsService diagnostics,
    SettingsService settings,
    RetentionService retention,
    DashboardReadinessController dashboardReadiness,
    ValueChanged<AttentionItem> onAttentionSelected,
    String? initialSessionId,
  ) {
    if (destination == AdminDestination.dashboard) {
      return DashboardScreen(
        repository: admin,
        range: _seoulTodayRange(),
        onAttentionSelected: onAttentionSelected,
        readiness: dashboardReadiness,
      );
    }
    if (destination == AdminDestination.transactions) {
      return TransactionHistoryScreen(
        repository: admin,
        initialSessionId: initialSessionId,
      );
    }
    if (destination == AdminDestination.reviewInbox) {
      return ReviewInboxScreen(
        repository: reviews,
        currentAdminAuthor: () async =>
            (await settings.current()).adminAuthorLabel,
      );
    }
    if (destination == AdminDestination.products) {
      return ProductManagementScreen(service: products);
    }
    if (destination == AdminDestination.diagnostics) {
      return DiagnosticsScreen(load: diagnostics.refresh);
    }
    if (destination == AdminDestination.settings) {
      return SettingsScreen(settings: settings, retention: retention);
    }
    return Center(
      child: Text(
        '${destination.label} 화면을 준비하고 있어요.',
        style: Theme.of(context).textTheme.bodyLarge,
      ),
    );
  }
}

/// Generated UI art has an explicit asset manifest. Its content hashes are a
/// deny-list for catalog intake, so copying an ImageGen file to an innocent
/// filename cannot turn it into sale-product photography.
Future<Set<String>> _generatedUiIllustrationHashes() async {
  final document = jsonDecode(
    await rootBundle.loadString('assets/asset_manifest.json'),
  );
  if (document is! Map<String, Object?> ||
      document['generated_ui_illustrations'] is! List<Object?>) {
    throw const FormatException('generated UI asset manifest is invalid');
  }
  final hashes = <String>{};
  for (final entry
      in document['generated_ui_illustrations']! as List<Object?>) {
    if (entry is! Map<String, Object?> || entry['sha256'] is! String) {
      throw const FormatException('generated UI asset manifest is invalid');
    }
    final hash = entry['sha256']! as String;
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch(hash)) {
      throw const FormatException('generated UI asset hash is invalid');
    }
    hashes.add(hash);
  }
  return hashes;
}

final class _AppServices {
  const _AppServices({
    required this.checkout,
    required this.admin,
    required this.reviews,
    required this.products,
    required this.diagnostics,
    required this.dashboardReadiness,
    required this.settings,
    required this.retention,
  });

  final CheckoutController checkout;
  final DatabaseAdminRepository admin;
  final DatabaseReviewService reviews;
  final ProductManagementService products;
  final DiagnosticsService diagnostics;
  final DashboardReadinessController dashboardReadiness;
  final SettingsService settings;
  final RetentionService retention;
}

DiagnosticsLiveState _diagnosticsLiveState(
  ScannerState scanner,
  WorkerDiagnosticSnapshot worker,
) {
  final metrics = worker.startupMetrics;
  final error =
      worker.fatalEvent?.message ??
      worker.lastWorkerError?.message ??
      scanner.workerError ??
      scanner.analysisError;
  final workerState =
      worker.status == WorkerStatus.fatal && worker.fatalEvent != null
      ? WorkerDiagnosticsState.fatal(
          code: worker.fatalEvent!.code,
          message: worker.fatalEvent!.message,
          diagnostics: worker.diagnostics,
        )
      : worker.status == WorkerStatus.ready && metrics != null
      ? WorkerDiagnosticsState.ready(
          device: metrics.device,
          loadMs: metrics.loadMs,
          warmupMs: metrics.warmupMs,
          detectorThreshold: metrics.detectorThreshold,
          detectorId: metrics.detectorId,
          repvitId: metrics.repvitId,
          dinov3Id: metrics.dinov3Id,
          fusionPolicyId: metrics.fusionPolicyId,
          lastError: error,
          diagnostics: worker.diagnostics,
        )
      : WorkerDiagnosticsState.status(
          status: WorkerDiagnosticsStatus.values.byName(worker.status.name),
          device: metrics?.device ?? scanner.device,
          lastError: error,
          diagnostics: worker.diagnostics,
        );
  return DiagnosticsLiveState(
    cameraReady: scanner.cameraReady,
    cameraLastError: scanner.cameraError,
    worker: workerState,
  );
}

DiagnosticsExpectedArtifacts _diagnosticsExpectedArtifacts(
  AuditRuntimeSnapshot runtime,
) => DiagnosticsExpectedArtifacts(
  detectorId: runtime.detectorId,
  detectorSha256: runtime.detectorSha256,
  repvitId: runtime.repvitArtifactId,
  repvitSha256: runtime.repvitSha256,
  dinov3Id: runtime.dinov3ArtifactId,
  dinov3Sha256: runtime.dinov3Sha256,
  fusionPolicyId: runtime.fusionPolicyId,
  fusionPolicySha256: runtime.fusionPolicySha256,
  configSha256: sha256
      .convert(utf8.encode(runtime.configSnapshotJson))
      .toString(),
);

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
  calibrationId: 'fusion_policy_fusion_local_or_global_consensus_margin_v1',
  calibrationSha256:
      '06c692d5b35583bfd99498805da474b7e9dfa7c8c36eeed04307695f7e885dcc',
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
