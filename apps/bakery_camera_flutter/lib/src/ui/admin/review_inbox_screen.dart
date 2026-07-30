import 'package:flutter/material.dart';

import '../../admin/admin_models.dart';
import '../../admin/review_models.dart';
import '../../admin/review_service.dart';
import 'review_detail_screen.dart';

class ReviewInboxScreen extends StatefulWidget {
  const ReviewInboxScreen({required this.repository, super.key});

  final ReviewRepository repository;

  @override
  State<ReviewInboxScreen> createState() => _ReviewInboxScreenState();
}

class _ReviewInboxScreenState extends State<ReviewInboxScreen> {
  final _items = <ReviewInboxItem>[];
  PageCursor? _nextCursor;
  bool _initialLoading = true;
  bool _loadingMore = false;
  String? _initialError;
  String? _loadMoreError;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    final generation = ++_generation;
    setState(() {
      _initialLoading = _items.isEmpty;
      _initialError = null;
      _loadMoreError = null;
      _loadingMore = false;
    });
    try {
      final page = await widget.repository.reviewInbox(
        const ReviewFilter(),
        null,
      );
      if (!mounted || generation != _generation) return;
      setState(() {
        _items
          ..clear()
          ..addAll(page.items);
        _nextCursor = page.nextCursor;
        _initialLoading = false;
      });
    } catch (_) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _initialLoading = false;
        _initialError = '검토 목록을 불러오지 못했어요.';
      });
    }
  }

  Future<void> _loadMore() async {
    final cursor = _nextCursor;
    if (cursor == null || _loadingMore) return;
    final generation = _generation;
    setState(() {
      _loadingMore = true;
      _loadMoreError = null;
    });
    try {
      final page = await widget.repository.reviewInbox(
        const ReviewFilter(),
        cursor,
      );
      if (!mounted || generation != _generation) return;
      setState(() {
        _items.addAll(page.items);
        _nextCursor = page.nextCursor;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _loadingMore = false;
        _loadMoreError = '다음 검토 기록을 불러오지 못했어요.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_initialLoading && _items.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_initialError != null && _items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_initialError!),
            const SizedBox(height: 12),
            FilledButton(
              key: const Key('review-inbox-retry'),
              onPressed: _reload,
              child: const Text('다시 확인하기'),
            ),
          ],
        ),
      );
    }
    if (_items.isEmpty) return const Center(child: Text('확인할 기록이 없습니다.'));
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _items.length + (_nextCursor == null ? 0 : 1),
      separatorBuilder: (_, _) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        if (index == _items.length) {
          if (_loadingMore) {
            return const Center(child: CircularProgressIndicator());
          }
          return Center(
            child: FilledButton.tonal(
              key: const Key('review-inbox-load-more'),
              onPressed: _loadMore,
              child: Text(_loadMoreError ?? '더 보기'),
            ),
          );
        }
        final item = _items[index];
        return Card(
          child: ListTile(
            key: Key('review-inbox-${item.sessionId}'),
            title: Text(item.summary),
            subtitle: Text(
              '${_priorityLabel(item.priority)} · ${_statusLabel(item.status)}\n${item.sessionId}',
            ),
            isThreeLine: true,
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              await Navigator.of(context).push<void>(
                MaterialPageRoute(
                  builder: (_) => ReviewDetailScreen(
                    repository: widget.repository,
                    target: item.target,
                  ),
                ),
              );
              if (mounted) {
                _reload();
              }
            },
          ),
        );
      },
    );
  }
}

String _priorityLabel(ReviewPriority priority) => switch (priority) {
  ReviewPriority.integrityFailure => '증빙 확인',
  ReviewPriority.customerOverride => '고객 변경',
  ReviewPriority.unknownResolvedByCustomer => 'AI 미확정',
  ReviewPriority.manualCatalogResolution => '카탈로그 선택',
  ReviewPriority.retakeOrFailure => '재촬영/실패',
};

String _statusLabel(ReviewStatus status) => switch (status) {
  ReviewStatus.open => '검토 전',
  ReviewStatus.reviewed => '검토 완료',
  ReviewStatus.needsFollowUp => '추가 확인',
};
