import 'package:flutter/material.dart';

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
  late Future<ReviewPage> _page = _load();

  Future<ReviewPage> _load() =>
      widget.repository.reviewInbox(const ReviewFilter(), null);

  void _reload() {
    setState(() {
      _page = _load();
    });
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<ReviewPage>(
    future: _page,
    builder: (context, snapshot) {
      if (!snapshot.hasData) {
        if (snapshot.hasError) {
          return Center(
            child: FilledButton(
              key: const Key('review-inbox-retry'),
              onPressed: _reload,
              child: const Text('다시 확인하기'),
            ),
          );
        }
        return const Center(child: CircularProgressIndicator());
      }
      final items = snapshot.requireData.items;
      if (items.isEmpty) return const Center(child: Text('확인할 기록이 없습니다.'));
      return ListView.separated(
        itemCount: items.length,
        separatorBuilder: (_, _) => const SizedBox(height: 8),
        itemBuilder: (context, index) {
          final item = items[index];
          return Card(
            child: ListTile(
              title: Text(item.summary),
              subtitle: Text(item.sessionId),
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
                if (mounted) _reload();
              },
            ),
          );
        },
      );
    },
  );
}
