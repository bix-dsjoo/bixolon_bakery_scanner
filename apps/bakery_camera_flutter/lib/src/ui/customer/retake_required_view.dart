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
    primaryAction: BakeryPrimaryButton(
      label: '다시 촬영',
      icon: Icons.camera_alt_outlined,
      onPressed: onRetake,
    ),
    child: Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const BakeryStatusBanner(
            status: BakeryStatus.uncertain,
            title: '빵을 떨어뜨려 다시 놓아주세요',
            message: '빵이 겹치지 않게 정리한 뒤 다시 촬영해 주세요.',
          ),
          if (manualCartEligible) ...[
            const SizedBox(height: 16),
            TextButton.icon(
              onPressed: onManualEntry,
              icon: const Icon(Icons.list_alt_outlined),
              label: const Text('직접 담기'),
            ),
          ],
        ],
      ),
    ),
  );
}
