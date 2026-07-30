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
      expect(find.text('구성 스냅샷'), findsOneWidget);
      expect(
        find.text('파일 없음: 이 증거 파일의 보존 기록 없이 파일을 찾을 수 없습니다.'),
        findsOneWidget,
      );
      expect(find.text('증거 파일을 확인할 수 없습니다'), findsOneWidget);
      expect(find.text('고객이 무엇을 결제했나요?'), findsOneWidget);
      await tester.drag(find.byType(ListView), const Offset(0, -1000));
      await tester.pumpAndSettle();
      expect(find.text('측정된 단계 시간'), findsOneWidget);
      expect(find.text('세션 수명주기'), findsOneWidget);
      expect(find.text('모델·정책·보정 원본'), findsOneWidget);
    },
  );

  testWidgets('detail distinguishes each evidence integrity warning', (
    tester,
  ) async {
    for (final entry in {
      AuditEvidenceIntegrity.retentionExpired:
          '보관 기간 만료: 일치하는 보존 기록에 따라 정상 삭제된 증거입니다.',
      AuditEvidenceIntegrity.unverified: '검증 대기: 증거 검증이 아직 실행되지 않았습니다.',
      AuditEvidenceIntegrity.unavailable: '검증 불가: 검증기를 사용할 수 없어 현재 확인할 수 없습니다.',
      AuditEvidenceIntegrity.missing: '파일 없음: 이 증거 파일의 보존 기록 없이 파일을 찾을 수 없습니다.',
      AuditEvidenceIntegrity.hashMismatch:
          '해시 불일치: 파일이 기록된 SHA-256과 일치하지 않습니다.',
    }.entries) {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: TransactionDetailScreen(
            detail: _detailWithIntegrity(entry.key),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(entry.value), findsOneWidget);
    }
  });
}

AdminTransactionDetail _detailWithIntegrity(AuditEvidenceIntegrity integrity) =>
    AdminTransactionDetail(
      sessionId: _detail.sessionId,
      startedAt: _detail.startedAt,
      terminalAt: _detail.terminalAt,
      terminalState: _detail.terminalState,
      terminalReason: _detail.terminalReason,
      catalogRevisionId: _detail.catalogRevisionId,
      settingsRevisionId: _detail.settingsRevisionId,
      configSnapshotJson: _detail.configSnapshotJson,
      artifacts: _detail.artifacts,
      attempts: [
        AdminScanAttempt(
          attemptNumber: 1,
          capturedAt: DateTime.utc(2026),
          status: 'completed',
          image: AdminEvidenceReference(
            relativePath: 'attempt.jpg',
            sha256: 'a',
            byteSize: 1,
            integrity: integrity,
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

final _detail = AdminTransactionDetail(
  sessionId: 'session-1',
  startedAt: DateTime.utc(2026),
  terminalAt: DateTime.utc(2026, 1, 1, 0, 1),
  terminalState: 'completed',
  terminalReason: 'paid',
  catalogRevisionId: 'catalog-v1',
  settingsRevisionId: 'settings-v1',
  configSnapshotJson: '{"pipeline":"canonical_cpu"}',
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
