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
        Text('고객이 무엇을 결제했나요?', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        if (detail.order == null)
          const Text('결제된 주문이 없습니다')
        else
          _OrderCard(order: detail.order!),
        const SizedBox(height: 28),
        Text(
          '이 거래가 고객 판단으로 어디가 바뀌었나요?',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        ...detail.resolutions.map(
          (row) => ListTile(
            title: Text(row.productName),
            subtitle: Text('${row.source} · ${row.resolvedAt.toLocal()}'),
            trailing: row.isCurrent
                ? const Chip(label: Text('현재 선택'))
                : const Chip(label: Text('이전 선택')),
          ),
        ),
        const SizedBox(height: 28),
        Text('촬영과 모델 결정 근거', style: Theme.of(context).textTheme.titleLarge),
        ...detail.attempts.map(
          (attempt) => ExpansionTile(
            title: Text('촬영 ${attempt.attemptNumber} · ${attempt.status}'),
            subtitle: Text(attempt.image.relativePath),
            children: [
              AuditFactTable(
                facts: {
                  '이미지 SHA-256': attempt.image.sha256,
                  '이미지 상태': _integrity(attempt.image.integrity),
                  '재촬영 사유': attempt.retakeReason ?? '없음',
                  '화면 상태': attempt.presentationState ?? '없음',
                },
              ),
              for (final object in attempt.objects)
                ListTile(
                  title: Text(object.skuId == null ? 'AI 미확정' : object.skuName),
                  subtitle: Text(
                    '상자 ${object.boxJson} · 신뢰도 ${object.confidence} · ${object.decisionPath}',
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 28),
        Text('측정된 단계 시간', style: Theme.of(context).textTheme.titleLarge),
        const Text('운영 중 기록된 시간이며 성능 수치나 정확도 주장이 아닙니다.'),
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
                'Detector': detail.artifacts.detectorId,
                'Detector SHA-256': detail.artifacts.detectorSha256,
                '카탈로그 리비전': detail.catalogRevisionId,
                '설정 리비전': detail.settingsRevisionId,
                'RepViT SHA-256': detail.artifacts.repvitSha256,
                'RepViT prototype SHA-256':
                    detail.artifacts.repvitPrototypeSha256,
                'DINOv3 SHA-256': detail.artifacts.dinov3Sha256,
                'DINOv3 support SHA-256': detail.artifacts.dinov3SupportSha256,
                'Calibration SHA-256': detail.artifacts.calibrationSha256,
                'Preprocess SHA-256': detail.artifacts.preprocessSha256,
                'Policy SHA-256': detail.artifacts.fusionPolicySha256,
              },
            ),
          ],
        ),
      ],
    ),
  );
  String _integrity(AuditEvidenceIntegrity value) => switch (value) {
    AuditEvidenceIntegrity.retained => '검증됨',
    AuditEvidenceIntegrity.missing => '파일 없음',
    AuditEvidenceIntegrity.hashMismatch => '해시 불일치',
    AuditEvidenceIntegrity.unverified => '검증 대기',
  };
}

class _Warning extends StatelessWidget {
  const _Warning();
  @override
  Widget build(BuildContext context) => const Card(
    child: ListTile(
      leading: Icon(Icons.warning_amber_rounded),
      title: Text('증거 파일을 확인할 수 없습니다'),
      subtitle: Text('파일이 없어졌거나 해시가 일치하지 않습니다. 거래 기록은 그대로 보존됩니다.'),
    ),
  );
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({required this.order});
  final AdminFinalOrder order;
  @override
  Widget build(BuildContext context) => Card(
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
        ],
      ),
    ),
  );
}
