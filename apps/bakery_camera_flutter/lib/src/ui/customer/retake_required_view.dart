import 'package:flutter/material.dart';

import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
import 'checkout_review_workspace.dart';
import 'customer_review_presentation.dart';

/// Keeps a failed scan in the same review workspace so the customer can see
/// the retained capture while receiving concise retake guidance.
class RetakeRequiredView extends StatelessWidget {
  const RetakeRequiredView({
    required this.state,
    required this.manualCartEligible,
    required this.onRetake,
    required this.onManualEntry,
    super.key,
  });

  final CheckoutState state;
  final bool manualCartEligible;
  final VoidCallback? onRetake;
  final VoidCallback? onManualEntry;

  @override
  Widget build(BuildContext context) => CheckoutReviewWorkspace(
    state: state,
    presentation: CustomerReviewPresentation.fromDrafts(state.objectDrafts),
    selectedObjectId: null,
    onSelectObject: (_) {},
    taskTitle: '다시 확인',
    taskContent: const SizedBox.expand(),
    primaryActionLabel: null,
    onPrimaryAction: null,
    overlay: _RetakeCaptureNotice(
      state: state,
      manualCartEligible: manualCartEligible,
      onRetake: onRetake,
      onManualEntry: onManualEntry,
    ),
  );
}

class _RetakeCaptureNotice extends StatelessWidget {
  const _RetakeCaptureNotice({
    required this.state,
    required this.manualCartEligible,
    required this.onRetake,
    required this.onManualEntry,
  });

  final CheckoutState state;
  final bool manualCartEligible;
  final VoidCallback? onRetake;
  final VoidCallback? onManualEntry;

  @override
  Widget build(BuildContext context) => KeyedSubtree(
    key: const Key('retake-capture-notice'),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        BakeryStatusBanner(
          status: BakeryStatus.uncertain,
          title: '빵을 떨어뜨려 다시 놓아주세요',
          message: _customerGuidance(state.failure?.code),
        ),
        const SizedBox(height: 8),
        BakeryPrimaryButton(label: '다시 촬영', onPressed: onRetake),
        if (manualCartEligible) ...[
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: onManualEntry,
              child: const Text('직접 담기'),
            ),
          ),
        ],
      ],
    ),
  );
}

String _customerGuidance(String? code) => switch (code) {
  'customer_count_mismatch' => '트레이에 담은 빵 개수를 확인한 뒤 다시 촬영해 주세요.',
  'no_bread_detected' => '빵이 카메라에 잘 보이도록 트레이 가운데에 놓아 주세요.',
  _ => '빵이 겹치지 않도록 정리한 뒤 다시 촬영해 주세요.',
};
