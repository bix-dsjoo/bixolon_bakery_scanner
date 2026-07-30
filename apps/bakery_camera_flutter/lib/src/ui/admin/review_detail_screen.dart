import 'package:flutter/material.dart';

import '../../admin/review_models.dart';
import '../../admin/review_service.dart';

class ReviewDetailScreen extends StatefulWidget {
  const ReviewDetailScreen({
    required this.repository,
    required this.target,
    super.key,
  });

  final ReviewRepository repository;
  final ReviewTarget target;

  @override
  State<ReviewDetailScreen> createState() => _ReviewDetailScreenState();
}

class _ReviewDetailScreenState extends State<ReviewDetailScreen> {
  late final Future<ReviewDetail> _detail = widget.repository.reviewDetail(
    widget.target,
  );
  String? _productId;
  bool _saving = false;

  Future<void> _save() async {
    if (_saving) {
      return;
    }
    setState(() => _saving = true);
    try {
      await widget.repository.annotate(
        AdminReviewAnnotationDraft(
          sessionId: widget.target.sessionId,
          attemptId: widget.target.attemptId,
          objectId: widget.target.objectId,
          reviewStatus: ReviewStatus.reviewed,
          correctProductId: _productId,
          reasonCode: 'operator_reviewed',
          authorLabel: 'prototype-admin',
        ),
      );
      if (mounted) {
        Navigator.of(context).pop();
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('검토')),
    body: FutureBuilder<ReviewDetail>(
      future: _detail,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final detail = snapshot.requireData;
        return ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const Text('이 기록은 모델 결과를 바꾸지 않습니다.'),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              key: const Key('review-correct-product'),
              initialValue: _productId,
              decoration: const InputDecoration(labelText: '올바른 상품 (선택)'),
              items: [
                const DropdownMenuItem(value: null, child: Text('선택하지 않음')),
                ...detail.products.map(
                  (product) => DropdownMenuItem(
                    value: product.productId,
                    child: Text(product.displayName),
                  ),
                ),
              ],
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _productId = value),
            ),
            const SizedBox(height: 24),
            FilledButton(
              key: const Key('review-save'),
              onPressed: _saving ? null : _save,
              child: const Text('검토 완료'),
            ),
          ],
        );
      },
    ),
  );
}
