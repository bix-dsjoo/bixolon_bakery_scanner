import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../admin/diagnostics_models.dart';

/// Administrator-only, read-only operational evidence. The screen deliberately
/// exposes no policy editor, artifact browser, raw receipt export, or worker
/// command because those would weaken the locked inference contract.
class DiagnosticsScreen extends StatefulWidget {
  const DiagnosticsScreen({required this.load, super.key});

  final Future<DiagnosticsSnapshot> Function() load;

  @override
  State<DiagnosticsScreen> createState() => _DiagnosticsScreenState();
}

class _DiagnosticsScreenState extends State<DiagnosticsScreen> {
  late Future<DiagnosticsSnapshot> _snapshot = widget.load();

  void _reload() => setState(() => _snapshot = widget.load());

  @override
  Widget build(BuildContext context) => FutureBuilder<DiagnosticsSnapshot>(
    future: _snapshot,
    builder: (context, value) {
      if (value.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      if (value.hasError) {
        return _Failure(onRetry: _reload);
      }
      return _DiagnosticsBody(snapshot: value.requireData, onReload: _reload);
    },
  );
}

class _DiagnosticsBody extends StatelessWidget {
  const _DiagnosticsBody({required this.snapshot, required this.onReload});

  final DiagnosticsSnapshot snapshot;
  final VoidCallback onReload;

  @override
  Widget build(BuildContext context) {
    final isReady = snapshot.customerImpact == DiagnosticsCustomerImpact.ready;
    return SingleChildScrollView(
      key: const ValueKey('diagnostics-list'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _ImpactCard(isReady: isReady, snapshot: snapshot),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: onReload,
            icon: const Icon(Icons.refresh),
            label: const Text('시스템 다시 확인하기'),
          ),
          const SizedBox(height: 16),
          _SectionCard(
            title: '연결 상태',
            child: Column(
              children: [
                _StatusRow(
                  label: '카메라',
                  isHealthy: snapshot.live.cameraReady,
                  detail: snapshot.live.cameraReady
                      ? '촬영 준비됨'
                      : snapshot.live.cameraLastError ?? '연결을 확인해 주세요',
                ),
                const Divider(),
                _StatusRow(
                  label: '추론 워커',
                  isHealthy: snapshot.live.worker.isReady,
                  detail: snapshot.live.worker.isReady
                      ? '${snapshot.live.worker.device ?? '알 수 없음'} · 시작 ${_formatMs(snapshot.live.worker.loadMs)} · 워밍업 ${_formatMs(snapshot.live.worker.warmupMs)}'
                      : snapshot.live.worker.lastError ?? '준비 상태를 확인해 주세요',
                ),
                if (snapshot.live.worker.isReady &&
                    snapshot.live.worker.lastError != null) ...[
                  const SizedBox(height: 8),
                  Text('최근 워커 오류: ${snapshot.live.worker.lastError}'),
                ],
                if (snapshot.live.worker.fatalCode != null) ...[
                  const SizedBox(height: 8),
                  Text('오류 코드: ${snapshot.live.worker.fatalCode}'),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          _SectionCard(
            title: '추론 파이프라인',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '검출 임계값: ${_formatThreshold(snapshot.live.worker.detectorThreshold)}',
                ),
                const SizedBox(height: 8),
                const Text('값은 검증된 시작 정보에서만 읽습니다. 여기서 변경할 수 없습니다.'),
                const SizedBox(height: 12),
                for (final artifact in [
                  snapshot.artifacts.detector,
                  snapshot.artifacts.repvit,
                  snapshot.artifacts.dinov3,
                  snapshot.artifacts.fusion,
                ]) ...[_ArtifactRow(artifact: artifact), const Divider()],
              ],
            ),
          ),
          const SizedBox(height: 16),
          _SectionCard(
            title: '저장소',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _StatusRow(
                  label: '감사 저장소',
                  isHealthy: snapshot.storage.persistenceReady,
                  detail: snapshot.storage.migrationStatus,
                ),
                const SizedBox(height: 10),
                Text('스키마 ${snapshot.storage.schemaVersion}'),
                const SizedBox(height: 8),
                Text(
                  snapshot.storage.activeCatalogRevisionId == null
                      ? '활성 상품 목록을 확인해 주세요.'
                      : '활성 상품 목록: ${snapshot.storage.activeCatalogRevisionId}',
                ),
                const SizedBox(height: 8),
                Text('감사 루트: ${snapshot.storage.auditRoot}'),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _TimingCard(timing: snapshot.timing),
          const SizedBox(height: 24),
          const Text('모델 식별자와 해시만 복사할 수 있습니다. 원본 이미지와 감사 기록은 내보내지 않습니다.'),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _ImpactCard extends StatelessWidget {
  const _ImpactCard({required this.isReady, required this.snapshot});

  final bool isReady;
  final DiagnosticsSnapshot snapshot;

  @override
  Widget build(BuildContext context) => Card(
    color: isReady
        ? Theme.of(context).colorScheme.secondaryContainer
        : Theme.of(context).colorScheme.errorContainer,
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            isReady ? '고객 계산을 계속할 수 있어요' : '고객 계산 전 확인이 필요해요',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 6),
          Text(
            isReady
                ? '카메라, 추론 워커, 저장소와 검증된 파이프라인이 준비되었습니다.'
                : _impactDetail(snapshot),
          ),
        ],
      ),
    ),
  );

  String _impactDetail(DiagnosticsSnapshot value) {
    if (!value.live.cameraReady) return '카메라 연결 상태를 확인해 주세요.';
    if (!value.live.worker.isReady) return '추론 워커 상태를 확인해 주세요.';
    if (!value.storage.persistenceReady) return '감사 저장소 상태를 확인해 주세요.';
    return '파이프라인 아티팩트 검증 결과를 확인해 주세요.';
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.child});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 16),
          child,
        ],
      ),
    ),
  );
}

class _StatusRow extends StatelessWidget {
  const _StatusRow({
    required this.label,
    required this.isHealthy,
    required this.detail,
  });
  final String label;
  final bool isHealthy;
  final String detail;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(isHealthy ? Icons.check_circle_outline : Icons.error_outline),
      const SizedBox(width: 10),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 2),
            Text(detail),
          ],
        ),
      ),
    ],
  );
}

class _ArtifactRow extends StatelessWidget {
  const _ArtifactRow({required this.artifact});
  final DiagnosticsArtifactStatus artifact;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _StatusRow(
        label: artifact.label,
        isHealthy: artifact.isVerified,
        detail: artifact.isVerified ? '기대 해시와 일치' : '기대 해시와 일치하지 않음',
      ),
      const SizedBox(height: 8),
      _CopyValue(label: '기대 ID', value: artifact.expectedId),
      const SizedBox(height: 6),
      _CopyValue(label: '기대 SHA-256', value: artifact.expectedSha256),
      if (artifact.observedId != null) ...[
        const SizedBox(height: 6),
        _CopyValue(label: '관측 ID', value: artifact.observedId!),
      ],
      if (artifact.observedSha256 != null) ...[
        const SizedBox(height: 6),
        _CopyValue(label: '관측 SHA-256', value: artifact.observedSha256!),
      ],
    ],
  );
}

class _CopyValue extends StatelessWidget {
  const _CopyValue({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(child: Text('$label: ${_shorten(value)}')),
      IconButton(
        key: ValueKey('copy-$label-$value'),
        tooltip: 'ID 복사',
        onPressed: () async {
          await Clipboard.setData(ClipboardData(text: value));
          if (!context.mounted) return;
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('복사했어요')));
        },
        icon: const Icon(Icons.copy_outlined),
      ),
    ],
  );
}

class _TimingCard extends StatelessWidget {
  const _TimingCard({required this.timing});
  final DiagnosticsTimingSummary timing;

  @override
  Widget build(BuildContext context) => _SectionCard(
    title: '측정된 실행 시간',
    child: timing.sampleCount == 0
        ? const Text('완료된 측정 영수증이 아직 없습니다.')
        : Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '표본 ${timing.sampleCount}건 · 조건부 DINO 실행 ${(timing.conditionalDinoRate * 100).toStringAsFixed(0)}%',
              ),
              const SizedBox(height: 8),
              _TimingLine(label: '총 시간', value: timing.total),
              _TimingLine(label: '검출', value: timing.detector),
              _TimingLine(label: 'RepViT', value: timing.repvit),
              _TimingLine(label: 'DINOv3', value: timing.dinov3),
              const SizedBox(height: 8),
              const Text('운영상 수집된 기록이며 벤치마크 또는 성능 개선 주장에 사용하지 않습니다.'),
            ],
          ),
  );
}

class _TimingLine extends StatelessWidget {
  const _TimingLine({required this.label, required this.value});
  final String label;
  final DiagnosticsDistribution value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 6),
    child: Text(
      '$label · 최소 ${_formatMs(value.minimumMs)} / 중앙 ${_formatMs(value.p50Ms)} / 최대 ${_formatMs(value.maximumMs)}',
    ),
  );
}

class _Failure extends StatelessWidget {
  const _Failure({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text('시스템 상태를 불러오지 못했어요.'),
        const SizedBox(height: 12),
        FilledButton(onPressed: onRetry, child: const Text('시스템 다시 확인하기')),
      ],
    ),
  );
}

String _formatMs(double? value) => value == null
    ? '없음'
    : '${value.toStringAsFixed(value == value.roundToDouble() ? 0 : 1)} ms';
String _formatThreshold(double? value) =>
    value == null ? '시작 정보 없음' : value.toStringAsFixed(2);
String _shorten(String value) => value.length != 64
    ? value
    : '${value.substring(0, 10)}…${value.substring(value.length - 8)}';
