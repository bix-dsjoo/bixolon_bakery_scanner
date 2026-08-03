import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/diagnostics_models.dart';
import 'package:bakery_camera_prototype/src/admin/diagnostics_service.dart';
import 'package:bakery_camera_prototype/src/admin/product_management_service.dart';
import 'package:bakery_camera_prototype/src/admin/retention_service.dart';
import 'package:bakery_camera_prototype/src/admin/review_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_service.dart';
import 'package:bakery_camera_prototype/src/admin/settings_models.dart';
import 'package:bakery_camera_prototype/src/admin/settings_service.dart';
import 'package:bakery_camera_prototype/src/app/app_mode_controller.dart';
import 'package:bakery_camera_prototype/src/app/app_mode_surface.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/persistence/database_admin_repository.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/customer_checkout_journey_fixture.dart';

void main() {
  test(
    'admin audit journey preserves inference while recording review, catalog, settings, and ready reset',
    () async {
      final fixture = await CustomerCheckoutJourneyFixture.create(
        includeUnchangedRegisteredObject: true,
      );
      addTearDown(fixture.dispose);

      await fixture.controller.initialize();
      await fixture.controller.scan();
      expect(fixture.controller.state.phase, CheckoutPhase.customerReview);
      await fixture.controller.chooseTop3('object-2', 10);
      expect(fixture.controller.state.phase, CheckoutPhase.orderReview);
      await fixture.controller.overrideResolvedProduct(
        'object-1',
        'milk-bread',
      );
      await fixture.controller.addManualProduct('croissant');
      await fixture.controller.pay();
      expect(fixture.controller.state.phase, CheckoutPhase.paymentComplete);
      final modes = AppModeController(
        customerLifecycle: CheckoutCustomerModeLifecycle(fixture.controller),
      );
      addTearDown(modes.dispose);
      expect(modes.mode, AppMode.customer);
      expect(await modes.enterAdmin(abandonConfirmed: true), isTrue);
      expect(modes.mode, AppMode.admin);
      expect(fixture.controller.state.phase, CheckoutPhase.paymentComplete);

      final session = await fixture.database
          .select(fixture.database.checkoutSessions)
          .getSingle();
      final objectsBefore = await fixture.database
          .select(fixture.database.inferenceObjects)
          .get();
      final resolutionsBefore = await fixture.database
          .select(fixture.database.objectResolutions)
          .get();
      final orderBefore = await fixture.database
          .select(fixture.database.finalOrders)
          .getSingle();

      final admin = DatabaseAdminRepository(
        fixture.database,
        verifyEvidence: (path, sha, bytes) async {
          await fixture.files.verifyExisting(
            relativePath: path,
            sha256: sha,
            byteSize: bytes,
          );
          return AuditEvidenceIntegrity.retained;
        },
      );
      final range = DateRange.utc(
        DateTime.utc(2026, 7, 30),
        DateTime.utc(2026, 7, 31),
      );
      final dashboard = await admin.dashboard(range);
      expect(dashboard.completedOrders, 1);
      expect(dashboard.customerOverrides, 1);
      expect(dashboard.manualCartLines, 1);
      expect(dashboard.customerResolvedUnknownObjects, 1);

      final history = await admin.transactions(
        const TransactionFilter(
          paymentStatus: TransactionPaymentStatus.completed,
        ),
        null,
      );
      expect(history.items.single.sessionId, session.sessionId);
      final detail = await admin.transactionDetail(session.sessionId);
      expect(
        detail.attempts.single.objects.where((object) => object.skuId == null),
        hasLength(1),
      );
      expect(
        detail.resolutions.map((row) => row.source),
        containsAll(<String>[
          'ai_auto_customer_accepted',
          'customer_top3',
          'customer_overrode_auto',
        ]),
      );
      expect(
        detail.order!.lines.map((line) => line.resolutionSource),
        containsAll(<String>[
          'ai_auto_customer_accepted',
          'customer_top3',
          'customer_overrode_auto',
          'customer_manual_cart',
        ]),
      );

      final reviews = DatabaseReviewService(
        fixture.database,
        createId: (_) => 'journey-review',
        now: () => DateTime.utc(2026, 7, 30, 12, 1),
      );
      await reviews.annotate(
        AdminReviewAnnotationDraft(
          sessionId: session.sessionId,
          objectId: objectsBefore
              .singleWhere((object) => object.skuId == null)
              .inferenceObjectId,
          reviewStatus: ReviewStatus.reviewed,
          conclusion: ReviewConclusion.customerCorrect,
          reasonCode: 'customer_choice_checked',
          note: 'audit journey',
          authorLabel: 'prototype-admin',
        ),
      );
      expect(
        await fixture.database.select(fixture.database.inferenceObjects).get(),
        objectsBefore,
      );
      expect(
        await fixture.database.select(fixture.database.objectResolutions).get(),
        resolutionsBefore,
      );
      expect(
        await fixture.database.select(fixture.database.finalOrders).getSingle(),
        orderBefore,
      );

      final products = ProductManagementService(
        database: fixture.database,
        createId: () => 'journey-catalog-v2',
        now: () => DateTime.utc(2026, 7, 30, 12, 2),
      );
      final revision = await products.save(
        const ProductDraft.edit(
          productId: 'milk-bread',
          displayName: 'New Milk Bread',
          unitPriceKrw: 1900,
          recognitionSkuId: null,
          categoryId: 'bread',
          active: true,
          sortOrder: 3,
        ),
      );
      expect(revision.revision.revisionId, 'journey-catalog-v2');
      final preservedLine =
          (await fixture.database
                  .select(fixture.database.finalOrderLines)
                  .get())
              .singleWhere((line) => line.productId == 'milk-bread');
      expect(preservedLine.productName, isNot('New Milk Bread'));
      expect(preservedLine.unitPriceKrw, 1300);

      final configSha = sha256
          .convert(utf8.encode(session.configSnapshotJson))
          .toString();
      final diagnostics = DiagnosticsService(
        live: DiagnosticsLiveState(
          cameraReady: true,
          cameraLastError: null,
          worker: const WorkerDiagnosticsState.ready(
            device: 'cpu',
            loadMs: 1,
            warmupMs: 1,
            detectorThreshold: .42,
            detectorId: 'rfdetr_large_bakery_v1',
            repvitId: 'repvit_m1_15plus5_v1',
            dinov3Id: 'dinov3_vits16_15plus5_v1',
            fusionPolicyId: 'fusion-v1',
          ),
        ),
        expectedArtifacts: DiagnosticsExpectedArtifacts(
          detectorId: session.detectorId,
          detectorSha256: session.detectorSha256,
          repvitId: session.repvitArtifactId,
          repvitSha256: session.repvitSha256,
          dinov3Id: session.dinov3ArtifactId,
          dinov3Sha256: session.dinov3Sha256,
          fusionPolicyId: session.fusionPolicyId,
          fusionPolicySha256: session.fusionPolicySha256,
          configSha256: configSha,
        ),
        audit: DatabaseDiagnosticsAuditReader(
          database: fixture.database,
          auditRoot: fixture.files.rootPath,
        ),
      );
      final diagnosticsSnapshot = await diagnostics.refresh();
      expect(
        diagnosticsSnapshot.customerImpact,
        DiagnosticsCustomerImpact.ready,
      );
      expect(diagnosticsSnapshot.artifacts.allVerified, isTrue);

      final settings = SettingsService(
        database: fixture.database,
        createId: () => 'journey-settings-v2',
        now: () => DateTime.utc(2026, 7, 30, 12, 3),
      );
      final savedSettings = await settings.save(
        const KioskSettingsDraft(
          kioskDisplayName: 'BIXOLON Journey',
          retryLimit: 3,
          paymentCompleteDurationSeconds: 5,
          customerAutoReset: true,
          evidenceRetentionDays: 90,
          locale: 'ko-KR',
          adminAuthorLabel: 'prototype-admin',
        ),
      );
      expect(savedSettings.revisionId, 'journey-settings-v2');

      final retention = RetentionService(
        database: fixture.database,
        evidenceRoot: Directory(fixture.files.rootPath),
        createId: () => 'journey-retention',
        now: () => DateTime.utc(2026, 7, 30, 12, 4),
      );
      final preview = await retention.preview(DateTime.utc(2026, 7, 1));
      expect(preview.files, isEmpty);

      await modes.exitAdmin();
      expect(modes.mode, AppMode.customer);
      expect(fixture.controller.state.phase, CheckoutPhase.ready);
      expect(await settings.current(), isNotNull);
    },
  );
}
