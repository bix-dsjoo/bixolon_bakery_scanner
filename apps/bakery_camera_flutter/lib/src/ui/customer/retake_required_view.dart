import 'package:flutter/material.dart';

import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';

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
  Widget build(BuildContext context) => CheckoutScaffold(
    title: '다시 확인',
    primaryAction: BakeryPrimaryButton(label: '다시 촬영', onPressed: onRetake),
    child: Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          BakeryStatusBanner(
            status: BakeryStatus.uncertain,
            title: '빵을 떨어뜨려 다시 놓아주세요',
            message: _customerGuidance(state.failure?.code),
          ),
          if (manualCartEligible) ...[
            const SizedBox(height: 16),
            TextButton(onPressed: onManualEntry, child: const Text('직접 담기')),
          ],
        ],
      ),
    ),
  );
}

String _customerGuidance(String? code) => switch (code) {
  'customer_count_mismatch' => '트레이에 담은 빵 개수를 확인한 뒤 다시 촬영해 주세요.',
  'no_bread_detected' => '빵이 카메라에 잘 보이도록 트레이 가운데에 놓아 주세요.',
  _ => '빵이 겹치지 않도록 정리한 뒤 다시 촬영해 주세요.',
};
