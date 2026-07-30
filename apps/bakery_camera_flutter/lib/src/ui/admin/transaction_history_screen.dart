import 'package:flutter/material.dart';

import '../../admin/admin_models.dart';
import '../../admin/admin_repository.dart';
import 'transaction_detail_screen.dart';

class TransactionHistoryScreen extends StatefulWidget {
  const TransactionHistoryScreen({required this.repository, super.key});

  final TransactionAuditRepository repository;

  @override
  State<TransactionHistoryScreen> createState() =>
      _TransactionHistoryScreenState();
}

class _TransactionHistoryScreenState extends State<TransactionHistoryScreen> {
  TransactionFilter _filter = const TransactionFilter();
  late Future<TransactionPage> _page = widget.repository.transactions(
    _filter,
    null,
  );

  void _reload() =>
      setState(() => _page = widget.repository.transactions(_filter, null));

  @override
  Widget build(BuildContext context) => Material(
    child: FutureBuilder<TransactionPage>(
      future: _page,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final items = snapshot.requireData.items;
        return Column(
          children: [
            _Filters(
              filter: _filter,
              onChanged: (filter) {
                _filter = filter;
                _reload();
              },
            ),
            const SizedBox(height: 16),
            Expanded(
              child: items.isEmpty
                  ? const Center(child: Text('조건에 맞는 거래가 없습니다'))
                  : ListView.separated(
                      itemCount: items.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 8),
                      itemBuilder: (context, index) => _TransactionTile(
                        item: items[index],
                        onTap: () async {
                          final detail = await widget.repository
                              .transactionDetail(items[index].sessionId);
                          if (!context.mounted) return;
                          await Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) =>
                                  TransactionDetailScreen(detail: detail),
                            ),
                          );
                        },
                      ),
                    ),
            ),
          ],
        );
      },
    ),
  );
}

class _Filters extends StatelessWidget {
  const _Filters({required this.filter, required this.onChanged});
  final TransactionFilter filter;
  final ValueChanged<TransactionFilter> onChanged;

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 8,
    runSpacing: 8,
    children: [
      DropdownButton<TransactionPaymentStatus>(
        value: filter.paymentStatus,
        onChanged: (value) => onChanged(
          TransactionFilter(
            paymentStatus: value ?? TransactionPaymentStatus.any,
            requiresUnknown: filter.requiresUnknown,
            requiresRetake: filter.requiresRetake,
            requiresFailure: filter.requiresFailure,
          ),
        ),
        items: const [
          DropdownMenuItem(
            value: TransactionPaymentStatus.any,
            child: Text('전체 결제'),
          ),
          DropdownMenuItem(
            value: TransactionPaymentStatus.completed,
            child: Text('결제 완료'),
          ),
          DropdownMenuItem(
            value: TransactionPaymentStatus.unpaid,
            child: Text('미결제'),
          ),
        ],
      ),
      FilterChip(
        label: const Text('AI 미확정'),
        selected: filter.requiresUnknown == true,
        onSelected: (value) => onChanged(
          TransactionFilter(
            paymentStatus: filter.paymentStatus,
            requiresUnknown: value ? true : null,
            requiresRetake: filter.requiresRetake,
            requiresFailure: filter.requiresFailure,
          ),
        ),
      ),
      FilterChip(
        label: const Text('재촬영'),
        selected: filter.requiresRetake == true,
        onSelected: (value) => onChanged(
          TransactionFilter(
            paymentStatus: filter.paymentStatus,
            requiresUnknown: filter.requiresUnknown,
            requiresRetake: value ? true : null,
            requiresFailure: filter.requiresFailure,
          ),
        ),
      ),
      FilterChip(
        label: const Text('실패'),
        selected: filter.requiresFailure == true,
        onSelected: (value) => onChanged(
          TransactionFilter(
            paymentStatus: filter.paymentStatus,
            requiresUnknown: filter.requiresUnknown,
            requiresRetake: filter.requiresRetake,
            requiresFailure: value ? true : null,
          ),
        ),
      ),
    ],
  );
}

class _TransactionTile extends StatelessWidget {
  const _TransactionTile({required this.item, required this.onTap});
  final TransactionListItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      onTap: onTap,
      title: Text(_outcome(item)),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${item.breadCount}개 · ${item.finalAmountKrw == null ? '금액 없음' : '${item.finalAmountKrw}원'} · 촬영 ${item.scanAttemptCount}회',
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 4,
            children: [
              for (final source in item.resolutionSources)
                Chip(label: Text(_source(source))),
              if (item.hasUnknown) const Chip(label: Text('AI 미확정')),
              if (item.hasRetake) const Chip(label: Text('재촬영')),
            ],
          ),
          Text(item.sessionId, style: Theme.of(context).textTheme.labelSmall),
        ],
      ),
      trailing: const Icon(Icons.chevron_right),
    ),
  );

  String _outcome(TransactionListItem value) => switch (value.terminalState) {
    'completed' => '결제 완료',
    'failed' => '진행 실패',
    'abandoned' => '고객이 취소함',
    'interrupted' => '중단됨',
    _ => '진행 중',
  };
  String _source(String value) => switch (value) {
    'ai_auto_customer_accepted' => '자동 확인',
    'customer_top3' => '추천 선택',
    'customer_catalog' => '목록 선택',
    'customer_overrode_auto' => '자동 결과 변경',
    'customer_manual_cart' => '직접 담기',
    _ => value,
  };
}
