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
  late Future<ReviewDetail> _detail;
  final _noteController = TextEditingController();
  String? _productId;
  ReviewConclusion _conclusion = ReviewConclusion.aiCorrect;
  ReviewIssueTag _issueTag = ReviewIssueTag.productMisclassification;
  bool _saving = false;
  String? _saveError;

  @override
  void initState() {
    super.initState();
    _detail = _load();
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<ReviewDetail> _load() => widget.repository.reviewDetail(widget.target);

  void _retryLoad() {
    final nextDetail = _load();
    setState(() {
      _detail = nextDetail;
    });
  }

  Future<void> _save() async {
    if (_saving) return;
    if (_conclusion == ReviewConclusion.bothIncorrect && _productId == null) {
      setState(() => _saveError = '올바른 상품을 선택해주세요.');
      return;
    }
    setState(() {
      _saving = true;
      _saveError = null;
    });
    try {
      await widget.repository.annotate(
        AdminReviewAnnotationDraft(
          sessionId: widget.target.sessionId,
          attemptId: widget.target.attemptId,
          objectId: widget.target.objectId,
          reviewStatus: _conclusion == ReviewConclusion.insufficientEvidence
              ? ReviewStatus.needsFollowUp
              : ReviewStatus.reviewed,
          conclusion: _conclusion,
          correctProductId: _productId,
          reasonCode: _issueTag.storageValue,
          note: _noteController.text,
          authorLabel: 'prototype-admin',
        ),
      );
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        setState(() => _saveError = '검토 기록을 저장하지 못했어요. 다시 시도해주세요.');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('검토')),
    body: FutureBuilder<ReviewDetail>(
      future: _detail,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('검토 기록을 불러오지 못했어요.'),
                const SizedBox(height: 12),
                FilledButton(
                  key: const Key('review-detail-retry'),
                  onPressed: _retryLoad,
                  child: const Text('다시 확인하기'),
                ),
              ],
            ),
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        return _ReviewForm(
          detail: snapshot.requireData,
          saving: _saving,
          conclusion: _conclusion,
          issueTag: _issueTag,
          productId: _productId,
          noteController: _noteController,
          error: _saveError,
          onConclusionChanged: (value) => setState(() {
            _conclusion = value;
            if (value != ReviewConclusion.bothIncorrect) _productId = null;
            _saveError = null;
          }),
          onIssueTagChanged: (value) => setState(() => _issueTag = value),
          onProductChanged: (value) => setState(() {
            _productId = value;
            _saveError = null;
          }),
          onSave: _save,
        );
      },
    ),
  );
}

class _ReviewForm extends StatelessWidget {
  const _ReviewForm({
    required this.detail,
    required this.saving,
    required this.conclusion,
    required this.issueTag,
    required this.productId,
    required this.noteController,
    required this.error,
    required this.onConclusionChanged,
    required this.onIssueTagChanged,
    required this.onProductChanged,
    required this.onSave,
  });

  final ReviewDetail detail;
  final bool saving;
  final ReviewConclusion conclusion;
  final ReviewIssueTag issueTag;
  final String? productId;
  final TextEditingController noteController;
  final String? error;
  final ValueChanged<ReviewConclusion> onConclusionChanged;
  final ValueChanged<ReviewIssueTag> onIssueTagChanged;
  final ValueChanged<String?> onProductChanged;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(24),
    children: [
      const Text('이 기록은 모델 결과를 바꾸지 않습니다.'),
      const SizedBox(height: 20),
      const Text('검토 결론'),
      for (final option in _conclusionOptions)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: SizedBox(
            height: 48,
            child: ChoiceChip(
              key: Key('review-conclusion-${option.$1.storageValue}'),
              label: Text(option.$2),
              selected: conclusion == option.$1,
              onSelected: saving ? null : (_) => onConclusionChanged(option.$1),
            ),
          ),
        ),
      const SizedBox(height: 12),
      DropdownButtonFormField<ReviewIssueTag>(
        key: const Key('review-issue-tag'),
        initialValue: issueTag,
        decoration: const InputDecoration(labelText: '문제 태그'),
        items: [
          for (final option in _issueTagOptions)
            DropdownMenuItem(value: option.$1, child: Text(option.$2)),
        ],
        onChanged: saving ? null : (value) => onIssueTagChanged(value!),
      ),
      if (conclusion == ReviewConclusion.bothIncorrect) ...[
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
          key: const Key('review-correct-product'),
          initialValue: productId,
          decoration: const InputDecoration(labelText: '올바른 상품'),
          items: [
            for (final product in detail.products)
              DropdownMenuItem(
                value: product.productId,
                child: Text(product.displayName),
              ),
          ],
          onChanged: saving ? null : onProductChanged,
        ),
      ],
      const SizedBox(height: 16),
      TextFormField(
        key: const Key('review-note'),
        controller: noteController,
        enabled: !saving,
        maxLines: 3,
        decoration: const InputDecoration(labelText: '메모 (선택)'),
      ),
      if (error != null) ...[
        const SizedBox(height: 12),
        Text(
          error!,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      ],
      const SizedBox(height: 24),
      FilledButton(
        key: Key(error == null ? 'review-save' : 'review-save-retry'),
        onPressed: saving ? null : onSave,
        child: Text(saving ? '저장 중' : '검토 완료'),
      ),
    ],
  );
}

const _conclusionOptions = <(ReviewConclusion, String)>[
  (ReviewConclusion.aiCorrect, 'AI 판정이 맞아요'),
  (ReviewConclusion.customerCorrect, '고객 선택이 맞아요'),
  (ReviewConclusion.bothIncorrect, '둘 다 아니에요'),
  (ReviewConclusion.insufficientEvidence, '사진만으로 판단하기 어려워요'),
];

const _issueTagOptions = <(ReviewIssueTag, String)>[
  (ReviewIssueTag.productMisclassification, '상품 오분류'),
  (ReviewIssueTag.miss, '누락'),
  (ReviewIssueTag.duplicate, '중복'),
  (ReviewIssueTag.merge, '병합'),
  (ReviewIssueTag.split, '분할'),
  (ReviewIssueTag.nonTargetDetection, '비대상 감지'),
  (ReviewIssueTag.imageQuality, '이미지 품질'),
  (ReviewIssueTag.catalogIssue, '카탈로그 문제'),
];
