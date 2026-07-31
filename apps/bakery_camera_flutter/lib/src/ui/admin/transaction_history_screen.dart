import 'package:flutter/material.dart';

import '../../admin/admin_models.dart';
import '../../admin/admin_repository.dart';
import 'transaction_detail_screen.dart';

class TransactionHistoryScreen extends StatefulWidget {
  const TransactionHistoryScreen({
    required this.repository,
    this.initialSessionId,
    super.key,
  });

  final TransactionAuditRepository repository;

  /// A one-shot dashboard deep link. The list is constrained first so the
  /// browser's surrounding history stays truthful before the immutable detail
  /// is pushed.
  final String? initialSessionId;

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
  Object? _reloadError;
  Object? _loadMoreError;
  Object? _detailError;
  String? _detailErrorSessionId;
  bool _isOpeningDetail = false;
  int _requestGeneration = 0;
  String? _initialDetailSessionId;

  @override
  void initState() {
    super.initState();
    final initialSessionId = widget.initialSessionId?.trim();
    if (initialSessionId != null && initialSessionId.isNotEmpty) {
      _filter = TransactionFilter(sessionQuery: initialSessionId);
      _initialDetailSessionId = initialSessionId;
    }
    _reload();
  }

  Future<void> _reload() async {
    if (!mounted) return;
    final generation = ++_requestGeneration;
    final filter = _filter;
    if (!_isCurrentReload(generation, filter)) return;
    setState(() {
      _isLoading = true;
      _isLoadingMore = false;
      _reloadError = null;
      _loadMoreError = null;
    });
    try {
      final page = await widget.repository.transactions(filter, null);
      if (!_isCurrentReload(generation, filter)) return;
      setState(() {
        _items
          ..clear()
          ..addAll(page.items);
        _nextCursor = page.nextCursor;
        _isLoading = false;
        _isLoadingMore = false;
        _reloadError = null;
        _loadMoreError = null;
      });
      final initialSessionId = _initialDetailSessionId;
      if (initialSessionId != null) {
        _initialDetailSessionId = null;
        await _openDetail(initialSessionId);
      }
    } catch (error) {
      if (!_isCurrentReload(generation, filter)) return;
      setState(() {
        _isLoading = false;
        _isLoadingMore = false;
        _reloadError = error;
      });
    }
  }

  Future<void> _loadMore() async {
    final cursor = _nextCursor;
    if (cursor == null || _isLoading || _isLoadingMore || !mounted) return;
    final generation = _requestGeneration;
    final filter = _filter;
    if (!_isCurrentLoadMore(generation, filter, cursor)) return;
    setState(() {
      _isLoadingMore = true;
      _loadMoreError = null;
    });
    try {
      final page = await widget.repository.transactions(filter, cursor);
      if (!_isCurrentLoadMore(generation, filter, cursor)) return;
      setState(() {
        _items.addAll(page.items);
        _nextCursor = page.nextCursor;
        _isLoadingMore = false;
        _loadMoreError = null;
      });
    } catch (error) {
      if (!_isCurrentLoadMore(generation, filter, cursor)) return;
      setState(() {
        _isLoadingMore = false;
        _loadMoreError = error;
      });
    }
  }

  bool _isCurrentReload(int generation, TransactionFilter filter) =>
      mounted && generation == _requestGeneration && identical(filter, _filter);

  bool _isCurrentLoadMore(
    int generation,
    TransactionFilter filter,
    PageCursor cursor,
  ) => _isCurrentReload(generation, filter) && identical(cursor, _nextCursor);

  Future<void> _openDetail(String sessionId) async {
    if (!mounted || _isOpeningDetail) return;
    setState(() {
      _isOpeningDetail = true;
      _detailError = null;
      _detailErrorSessionId = null;
    });
    try {
      final detail = await widget.repository.transactionDetail(sessionId);
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => TransactionDetailScreen(detail: detail),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _detailError = error;
        _detailErrorSessionId = sessionId;
      });
    } finally {
      if (mounted) {
        setState(() => _isOpeningDetail = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => Material(
    child: _isLoading && _items.isEmpty
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
              if (_detailError != null && _detailErrorSessionId != null)
                _DetailErrorBanner(
                  onRetry: () => _openDetail(_detailErrorSessionId!),
                ),
              const SizedBox(height: 16),
              Expanded(
                child: _items.isEmpty && _reloadError == null
                    ? const Center(child: Text('조건에 맞는 거래가 없습니다'))
                    : ListView.separated(
                        key: const ValueKey('transaction-list'),
                        itemCount:
                            _items.length +
                            (_nextCursor == null ? 0 : 1) +
                            (_reloadError == null ? 0 : 1),
                        separatorBuilder: (_, _) => const Divider(),
                        itemBuilder: (context, index) {
                          final errorOffset = _reloadError == null ? 0 : 1;
                          if (_reloadError != null && index == 0) {
                            return _ReloadErrorBanner(onRetry: _reload);
                          }
                          final itemIndex = index - errorOffset;
                          if (itemIndex == _items.length) {
                            return Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (_loadMoreError != null)
                                  const Padding(
                                    padding: EdgeInsets.only(bottom: 8),
                                    child: Text(
                                      '추가 거래를 불러오지 못했습니다.',
                                      key: Key('transaction-load-more-error'),
                                    ),
                                  ),
                                Center(
                                  child: FilledButton.tonal(
                                    key: const Key('transaction-load-more'),
                                    onPressed: _isLoading || _isLoadingMore
                                        ? null
                                        : _loadMore,
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
                                ),
                              ],
                            );
                          }
                          final item = _items[itemIndex];
                          return _TransactionTile(
                            item: item,
                            onTap: _isOpeningDetail
                                ? null
                                : () => _openDetail(item.sessionId),
                          );
                        },
                      ),
              ),
            ],
          ),
  );
}

class _DetailErrorBanner extends StatelessWidget {
  const _DetailErrorBanner({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            '거래 상세를 불러오지 못했습니다.',
            key: Key('transaction-detail-error'),
          ),
          const SizedBox(height: 8),
          FilledButton(
            key: const Key('transaction-retry-detail'),
            onPressed: onRetry,
            child: const Text('다시 시도'),
          ),
        ],
      ),
    ),
  );
}

class _ReloadErrorBanner extends StatelessWidget {
  const _ReloadErrorBanner({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            '거래 내역을 불러오지 못했습니다.',
            key: Key('transaction-reload-error'),
          ),
          const SizedBox(height: 8),
          FilledButton(
            key: const Key('transaction-retry-reload'),
            onPressed: onRetry,
            child: const Text('다시 시도'),
          ),
        ],
      ),
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
    Object? terminalState = _keep,
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
    terminalState: identical(terminalState, _keep)
        ? filter.terminalState
        : terminalState as String?,
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
          key: const Key('transaction-filter-session'),
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
      OutlinedButton(
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
        child: const Text('기간 선택'),
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
        value: filter.terminalState ?? '',
        onChanged: (value) => onChanged(
          _copy(terminalState: value == null || value.isEmpty ? null : value),
        ),
        items: const [
          DropdownMenuItem(value: '', child: Text('전체 진행 상태')),
          DropdownMenuItem(value: 'active', child: Text('진행 중')),
          DropdownMenuItem(value: 'completed', child: Text('결제 완료')),
          DropdownMenuItem(value: 'failed', child: Text('진행 실패')),
          DropdownMenuItem(value: 'abandoned', child: Text('고객 취소')),
          DropdownMenuItem(value: 'interrupted', child: Text('중단됨')),
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
            terminalState: filter.terminalState,
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
            terminalState: filter.terminalState,
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
            terminalState: filter.terminalState,
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
            terminalState: filter.terminalState,
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
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: Colors.transparent,
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
