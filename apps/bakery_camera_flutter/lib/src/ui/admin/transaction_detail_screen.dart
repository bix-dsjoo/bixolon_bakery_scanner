import 'package:flutter/material.dart';

import '../../admin/admin_models.dart';
import 'widgets/audit_fact_table.dart';

class TransactionDetailScreen extends StatelessWidget {
  const TransactionDetailScreen({required this.detail, super.key});

  final AdminTransactionDetail detail;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('거래 상세')),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        if (detail.hasIntegrityWarning) const _Warning(),
        if (detail.hasIntegrityWarning) _IntegrityExplanation(detail: detail),
        Text('고객이 무엇을 결제했나요?', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        if (detail.order == null)
          const Text('결제된 주문이 없습니다')
        else
          _OrderCard(order: detail.order!),
        const SizedBox(height: 24),
        _Section(
          title: '세션 수명주기',
          child: AuditFactTable(
            facts: {
              '세션 ID': detail.sessionId,
              '세션 시작': detail.startedAt.toIso8601String(),
              '세션 종료': detail.terminalAt?.toIso8601String() ?? '진행 중',
              '종료 상태': detail.terminalState,
              '종료 사유': detail.terminalReason ?? '기록 없음',
              '카탈로그 리비전': detail.catalogRevisionId,
              '설정 리비전': detail.settingsRevisionId,
            },
          ),
        ),
        _Section(
          title: '구성 스냅샷',
          child: AuditFactTable(
            facts: {'구성 스냅샷 JSON': detail.configSnapshotJson},
          ),
        ),
        if (detail.payment != null)
          _Section(
            title: '결제 기록',
            child: AuditFactTable(
              facts: {
                '결제 ID': detail.payment!.paymentId,
                '결제 상태': detail.payment!.status,
                '결제 수단': detail.payment!.provider,
                '결제 금액': '${detail.payment!.amountKrw}원',
                '결제 시각': detail.payment!.paidAt.toIso8601String(),
                '최종 주문 SHA-256': detail.payment!.finalOrderSha256,
              },
            ),
          ),
        const SizedBox(height: 24),
        Text(
          '이 거래가 고객 판단으로 어디가 바뀌었나요?',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        if (detail.resolutions.isEmpty) const Text('고객 선택 기록이 없습니다'),
        for (final row in detail.resolutions)
          ExpansionTile(
            title: Text(row.productName),
            subtitle: Text('${row.source} · ${row.resolvedAt.toLocal()}'),
            trailing: row.isCurrent
                ? const Chip(label: Text('현재 선택'))
                : const Chip(label: Text('이전 선택')),
            children: [
              AuditFactTable(
                facts: {
                  '해결 ID': row.resolutionId,
                  '추론 객체 ID': row.inferenceObjectId ?? '직접 담기',
                  '상품 ID': row.productId,
                  '인식 SKU': row.recognitionSkuId?.toString() ?? '연결 없음',
                  '고객 해결 방식': row.source,
                  '후보 순위': row.candidateRank?.toString() ?? '해당 없음',
                  '객체 상자': row.canonicalBoxJson ?? '직접 담기',
                  '단가': '${row.unitPriceKrw}원',
                },
              ),
            ],
          ),
        const SizedBox(height: 24),
        Text('촬영과 모델 결정 근거', style: Theme.of(context).textTheme.titleLarge),
        for (final attempt in detail.attempts)
          ExpansionTile(
            title: Text('촬영 ${attempt.attemptNumber} · ${attempt.status}'),
            subtitle: Text(attempt.image.relativePath),
            children: [
              AuditFactTable(
                facts: {
                  '촬영 시각': attempt.capturedAt.toIso8601String(),
                  '이미지 경로': attempt.image.relativePath,
                  '이미지 SHA-256': attempt.image.sha256,
                  '이미지 바이트': attempt.image.byteSize.toString(),
                  '증거 상태': _integrity(attempt.image.integrity),
                  '추론 영수증 경로': attempt.receipt?.relativePath ?? '기록 없음',
                  '추론 영수증 SHA-256': attempt.receipt?.sha256 ?? '기록 없음',
                  '추론 영수증 상태': attempt.receipt == null
                      ? '기록 없음'
                      : _integrity(attempt.receipt!.integrity),
                  '재촬영 사유': attempt.retakeReason ?? '없음',
                  '화면 상태': attempt.presentationState ?? '기록 없음',
                },
              ),
              if (attempt.receipt != null)
                AuditFactTable(
                  facts: {'추론 영수증 바이트': attempt.receipt!.byteSize.toString()},
                ),
              for (final object in attempt.objects)
                ExpansionTile(
                  title: Text(object.skuId == null ? 'AI 미확정' : object.skuName),
                  subtitle: Text(
                    '상자 ${object.boxJson} · 신뢰도 ${object.confidence}',
                  ),
                  children: [
                    AuditFactTable(
                      facts: {
                        '객체 ID': object.objectId,
                        'SKU ID': object.skuId?.toString() ?? 'Unknown',
                        '객체 상자': object.boxJson,
                        '결정 경로': object.decisionPath,
                        '탐지 출처': object.detectorSource,
                        '탐지 점수': object.detectorScore.toString(),
                        'Unknown 사유': object.unknownReason ?? '해당 없음',
                      },
                    ),
                    for (final candidate in object.candidates)
                      ListTile(
                        title: Text(
                          '후보 ${candidate.rank}위 · ${candidate.skuName}',
                        ),
                        subtitle: Text(
                          'SKU ${candidate.skuId} · 점수 ${candidate.score}',
                        ),
                      ),
                  ],
                ),
            ],
          ),
        const SizedBox(height: 24),
        Text('측정된 단계 시간', style: Theme.of(context).textTheme.titleLarge),
        const Text('이 화면의 기록은 실행 시간이며 성능 수치나 정확도 주장이 아닙니다.'),
        for (final attempt in detail.attempts)
          AuditFactTable(
            facts: {
              for (final entry in attempt.timingsMs.entries)
                '${attempt.attemptNumber}회 ${entry.key}': entry.value == null
                    ? '기록 없음'
                    : '${entry.value} ms',
            },
          ),
        ExpansionTile(
          title: const Text('모델·정책·보정 원본'),
          children: [
            AuditFactTable(
              facts: {
                'Detector ID': detail.artifacts.detectorId,
                'Detector SHA-256': detail.artifacts.detectorSha256,
                'RepViT ID': detail.artifacts.repvitArtifactId,
                'RepViT SHA-256': detail.artifacts.repvitSha256,
                'RepViT manifest SHA-256':
                    detail.artifacts.repvitManifestSha256,
                'RepViT prototype SHA-256':
                    detail.artifacts.repvitPrototypeSha256,
                'DINOv3 ID': detail.artifacts.dinov3ArtifactId,
                'DINOv3 SHA-256': detail.artifacts.dinov3Sha256,
                'DINOv3 support SHA-256': detail.artifacts.dinov3SupportSha256,
                'Calibration ID': detail.artifacts.calibrationId,
                'Calibration SHA-256': detail.artifacts.calibrationSha256,
                'Preprocess SHA-256': detail.artifacts.preprocessSha256,
                'Policy ID': detail.artifacts.fusionPolicyId,
                'Policy SHA-256': detail.artifacts.fusionPolicySha256,
              },
            ),
          ],
        ),
      ],
    ),
  );

  static String _integrity(AuditEvidenceIntegrity value) => switch (value) {
    AuditEvidenceIntegrity.retained => '검증됨',
    AuditEvidenceIntegrity.retentionExpired => '보관 기간 만료',
    AuditEvidenceIntegrity.missing => '파일 없음',
    AuditEvidenceIntegrity.hashMismatch => '해시 불일치',
    AuditEvidenceIntegrity.unavailable => '확인할 수 없음',
    AuditEvidenceIntegrity.unverified => '검증 대기',
  };
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        child,
      ],
    ),
  );
}

class _Warning extends StatelessWidget {
  const _Warning();

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.error.withValues(alpha: 0.045),
      border: Border.symmetric(
        horizontal: BorderSide(color: Theme.of(context).dividerColor),
      ),
    ),
    child: const ListTile(
      leading: Icon(Icons.warning_amber_rounded),
      title: Text('증거 파일을 확인할 수 없습니다'),
      subtitle: Text('파일이 없거나 해시가 일치하지 않습니다. 거래 기록은 그대로 보존됩니다.'),
    ),
  );
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({required this.order});

  final AdminFinalOrder order;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      border: Border.symmetric(
        horizontal: BorderSide(color: Theme.of(context).dividerColor),
      ),
    ),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${order.totalQuantity}개 · ${order.totalAmountKrw}원',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          for (final line in order.lines)
            Text(
              '${line.productName} ${line.quantity}개 · ${line.lineAmountKrw}원',
            ),
          const SizedBox(height: 8),
          for (final line in order.lines) _OrderLineAudit(line: line),
          AuditFactTable(
            facts: {'주문 영수증 바이트': order.receipt.byteSize.toString()},
          ),
          AuditFactTable(
            facts: {
              '주문 ID': order.orderId,
              '주문 시각': order.createdAt.toIso8601String(),
              '주문 영수증 경로': order.receipt.relativePath,
              '주문 영수증 SHA-256': order.receipt.sha256,
              '주문 영수증 상태': TransactionDetailScreen._integrity(
                order.receipt.integrity,
              ),
            },
          ),
        ],
      ),
    ),
  );
}

class _IntegrityExplanation extends StatelessWidget {
  const _IntegrityExplanation({required this.detail});

  final AdminTransactionDetail detail;

  @override
  Widget build(BuildContext context) {
    final statuses = <AuditEvidenceIntegrity>{
      for (final attempt in detail.attempts) attempt.image.integrity,
      for (final attempt in detail.attempts)
        if (attempt.receipt != null) attempt.receipt!.integrity,
      if (detail.order != null) detail.order!.receipt.integrity,
    }..remove(AuditEvidenceIntegrity.retained);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [for (final status in statuses) Text(_message(status))],
      ),
    );
  }

  String _message(AuditEvidenceIntegrity integrity) => switch (integrity) {
    AuditEvidenceIntegrity.retentionExpired =>
      '보관 기간 만료: 일치하는 보존 기록에 따라 정상 삭제된 증거입니다.',
    AuditEvidenceIntegrity.unverified => '검증 대기: 증거 검증이 아직 실행되지 않았습니다.',
    AuditEvidenceIntegrity.unavailable => '검증 불가: 검증기를 사용할 수 없어 현재 확인할 수 없습니다.',
    AuditEvidenceIntegrity.missing => '파일 없음: 이 증거 파일의 보존 기록 없이 파일을 찾을 수 없습니다.',
    AuditEvidenceIntegrity.hashMismatch =>
      '해시 불일치: 파일이 기록된 SHA-256과 일치하지 않습니다.',
    AuditEvidenceIntegrity.retained => '',
  };
}

class _OrderLineAudit extends StatelessWidget {
  const _OrderLineAudit({required this.line});

  final AdminOrderLine line;

  @override
  Widget build(BuildContext context) => AuditFactTable(
    facts: {
      '상품 ID': line.productId,
      '추론 SKU': line.recognitionSkuId?.toString() ?? '연결 없음',
      '단가': '${line.unitPriceKrw}원',
      '확정 방식': line.resolutionSource,
    },
  );
}
