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
  final List<TransactionListItem> _items = [];
  PageCursor? _nextCursor;
  bool _isLoading = true;
  bool _isLoadingMore = false;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    setState(() => _isLoading = true);
    final page = await widget.repository.transactions(_filter, null);
    if (!mounted) return;
    setState(() {
      _items
        ..clear()
        ..addAll(page.items);
      _nextCursor = page.nextCursor;
      _isLoading = false;
    });
  }

  Future<void> _loadMore() async {
    final cursor = _nextCursor;
    if (cursor == null || _isLoadingMore) return;
    setState(() => _isLoadingMore = true);
    final page = await widget.repository.transactions(_filter, cursor);
    if (!mounted) return;
    setState(() {
      _items.addAll(page.items);
      _nextCursor = page.nextCursor;
      _isLoadingMore = false;
    });
  }

  @override
  Widget build(BuildContext context) => Material(
    child: _isLoading
        ? const Center(child: CircularProgressIndicator())
        : Column(
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
                child: _items.isEmpty
                    ? const Center(child: Text('조건에 맞는 거래가 없습니다'))
                    : ListView.separated(
                        itemCount:
                            _items.length + (_nextCursor == null ? 0 : 1),
                        separatorBuilder: (_, _) => const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          if (index == _items.length) {
                            return Center(
                              child: FilledButton.tonal(
                                onPressed: _isLoadingMore ? null : _loadMore,
                                child: _isLoadingMore
                                    ? const SizedBox(
                                        height: 20,
                                        width: 20,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                        ),
                                      )
                                    : const Text('더 보기'),
                              ),
                            );
                          }
                          final item = _items[index];
                          return _TransactionTile(
                            item: item,
                            onTap: () async {
                              final detail = await widget.repository
                                  .transactionDetail(item.sessionId);
                              if (!context.mounted) return;
                              await Navigator.of(context).push(
                                MaterialPageRoute<void>(
                                  builder: (_) =>
                                      TransactionDetailScreen(detail: detail),
                                ),
                              );
                            },
                          );
                        },
                      ),
              ),
            ],
          ),
  );
}

class _Filters extends StatelessWidget {
  const _Filters({required this.filter, required this.onChanged});
  final TransactionFilter filter;
  final ValueChanged<TransactionFilter> onChanged;
  static const _keep = Object();

  TransactionFilter _copy({
    DateRange? dateRange,
    Object? sessionQuery = _keep,
    Object? productQuery = _keep,
    Object? modelPolicyQuery = _keep,
    TransactionPaymentStatus? paymentStatus,
    String? resolutionSource,
    bool? requiresUnknown,
    bool? requiresRetake,
    bool? requiresFailure,
  }) => TransactionFilter(
    dateRange: dateRange ?? filter.dateRange,
    sessionQuery: identical(sessionQuery, _keep)
        ? filter.sessionQuery
        : sessionQuery as String?,
    productQuery: identical(productQuery, _keep)
        ? filter.productQuery
        : productQuery as String?,
    modelPolicyQuery: identical(modelPolicyQuery, _keep)
        ? filter.modelPolicyQuery
        : modelPolicyQuery as String?,
    paymentStatus: paymentStatus ?? filter.paymentStatus,
    resolutionSource: resolutionSource ?? filter.resolutionSource,
    requiresUnknown: requiresUnknown ?? filter.requiresUnknown,
    requiresRetake: requiresRetake ?? filter.requiresRetake,
    requiresFailure: requiresFailure ?? filter.requiresFailure,
  );

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 8,
    runSpacing: 8,
    children: [
      SizedBox(
        width: 180,
        child: TextFormField(
          initialValue: filter.sessionQuery,
          decoration: const InputDecoration(labelText: '세션 ID'),
          onFieldSubmitted: (value) => onChanged(
            _copy(sessionQuery: value.trim().isEmpty ? null : value.trim()),
          ),
        ),
      ),
      SizedBox(
        width: 180,
        child: TextFormField(
          initialValue: filter.productQuery,
          decoration: const InputDecoration(labelText: '상품명'),
          onFieldSubmitted: (value) => onChanged(
            _copy(productQuery: value.trim().isEmpty ? null : value.trim()),
          ),
        ),
      ),
      SizedBox(
        width: 180,
        child: TextFormField(
          initialValue: filter.modelPolicyQuery,
          decoration: const InputDecoration(labelText: '모델·정책 ID 또는 해시'),
          onFieldSubmitted: (value) => onChanged(
            _copy(modelPolicyQuery: value.trim().isEmpty ? null : value.trim()),
          ),
        ),
      ),
      OutlinedButton.icon(
        onPressed: () async {
          final selected = await showDateRangePicker(
            context: context,
            firstDate: DateTime.utc(2020),
            lastDate: DateTime.utc(2100),
            initialDateRange: filter.dateRange == null
                ? null
                : DateTimeRange(
                    start: filter.dateRange!.startInclusive,
                    end: filter.dateRange!.endExclusive.subtract(
                      const Duration(days: 1),
                    ),
                  ),
          );
          if (selected == null) return;
          onChanged(
            _copy(
              dateRange: DateRange.utc(
                selected.start,
                selected.end.add(const Duration(days: 1)),
              ),
            ),
          );
        },
        icon: const Icon(Icons.date_range_outlined),
        label: const Text('기간 선택'),
      ),
      DropdownButton<TransactionPaymentStatus>(
        value: filter.paymentStatus,
        onChanged: (value) => onChanged(
          _copy(paymentStatus: value ?? TransactionPaymentStatus.any),
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
      DropdownButton<String>(
        value: filter.resolutionSource ?? '',
        onChanged: (value) => onChanged(
          TransactionFilter(
            dateRange: filter.dateRange,
            sessionQuery: filter.sessionQuery,
            productQuery: filter.productQuery,
            modelPolicyQuery: filter.modelPolicyQuery,
            paymentStatus: filter.paymentStatus,
            resolutionSource: value == null || value.isEmpty ? null : value,
            requiresUnknown: filter.requiresUnknown,
            requiresRetake: filter.requiresRetake,
            requiresFailure: filter.requiresFailure,
          ),
        ),
        items: const [
          DropdownMenuItem(value: '', child: Text('전체 해결 방식')),
          DropdownMenuItem(
            value: 'ai_auto_customer_accepted',
            child: Text('자동 확인'),
          ),
          DropdownMenuItem(value: 'customer_top3', child: Text('추천 선택')),
          DropdownMenuItem(value: 'customer_catalog', child: Text('목록 선택')),
          DropdownMenuItem(
            value: 'customer_overrode_auto',
            child: Text('자동 결과 변경'),
          ),
          DropdownMenuItem(value: 'customer_manual_cart', child: Text('직접 담기')),
        ],
      ),
      FilterChip(
        label: const Text('AI 미확정'),
        selected: filter.requiresUnknown == true,
        onSelected: (value) => onChanged(
          TransactionFilter(
            dateRange: filter.dateRange,
            sessionQuery: filter.sessionQuery,
            productQuery: filter.productQuery,
            modelPolicyQuery: filter.modelPolicyQuery,
            paymentStatus: filter.paymentStatus,
            resolutionSource: filter.resolutionSource,
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
            dateRange: filter.dateRange,
            sessionQuery: filter.sessionQuery,
            productQuery: filter.productQuery,
            modelPolicyQuery: filter.modelPolicyQuery,
            paymentStatus: filter.paymentStatus,
            resolutionSource: filter.resolutionSource,
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
            dateRange: filter.dateRange,
            sessionQuery: filter.sessionQuery,
            productQuery: filter.productQuery,
            modelPolicyQuery: filter.modelPolicyQuery,
            paymentStatus: filter.paymentStatus,
            resolutionSource: filter.resolutionSource,
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
