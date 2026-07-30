import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/ui/admin/transaction_detail_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'detail keeps missing evidence warning visible with audit facts',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: TransactionDetailScreen(detail: _detail),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('증거 파일을 확인할 수 없습니다'), findsOneWidget);
      expect(find.text('고객이 무엇을 결제했나요?'), findsOneWidget);
      await tester.drag(find.byType(ListView), const Offset(0, -1000));
      await tester.pumpAndSettle();
      expect(find.text('측정된 단계 시간'), findsOneWidget);
      expect(find.text('세션 수명주기'), findsOneWidget);
      expect(find.text('모델·정책·보정 원본'), findsOneWidget);
    },
  );
}

final _detail = AdminTransactionDetail(
  sessionId: 'session-1',
  startedAt: DateTime.utc(2026),
  terminalAt: DateTime.utc(2026, 1, 1, 0, 1),
  terminalState: 'completed',
  terminalReason: 'paid',
  catalogRevisionId: 'catalog-v1',
  settingsRevisionId: 'settings-v1',
  artifacts: const AdminArtifactSnapshot(
    detectorId: 'detector',
    detectorSha256: 'a',
    repvitArtifactId: 'repvit',
    repvitSha256: 'a',
    repvitManifestSha256: 'a',
    repvitPrototypeSha256: 'a',
    dinov3ArtifactId: 'dino',
    dinov3Sha256: 'a',
    dinov3SupportSha256: 'a',
    calibrationId: 'calibration',
    calibrationSha256: 'a',
    preprocessSha256: 'a',
    fusionPolicyId: 'policy',
    fusionPolicySha256: 'a',
  ),
  attempts: [
    AdminScanAttempt(
      attemptNumber: 1,
      capturedAt: DateTime.utc(2026),
      status: 'completed',
      image: const AdminEvidenceReference(
        relativePath: 'attempt.jpg',
        sha256: 'a',
        byteSize: 1,
        integrity: AuditEvidenceIntegrity.missing,
      ),
      receipt: null,
      presentationState: 'review',
      retakeReason: null,
      timingsMs: const {'detector': 8},
      objects: const [],
    ),
  ],
  resolutions: const [],
  order: null,
  payment: null,
  hasIntegrityWarning: true,
);
