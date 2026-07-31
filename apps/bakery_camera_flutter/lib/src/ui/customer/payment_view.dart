import 'package:flutter/material.dart';

import '../../checkout/checkout_state.dart';
import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';

/// Payment is shown only while the controller is waiting for the actual
/// durable commit. It deliberately avoids an artificial activity spinner.
class PaymentView extends StatelessWidget {
  const PaymentView({required this.state, super.key});

  final CheckoutState state;

  @override
  Widget build(BuildContext context) => const CheckoutScaffold(
    title: '결제 중',
    child: Padding(
      padding: EdgeInsets.only(top: 24),
      child: BakeryStatusBanner(
        status: BakeryStatus.loading,
        title: '결제를 기록하고 있어요',
        message: '결제 내역을 안전하게 저장하는 동안 잠시만 기다려 주세요.',
      ),
    ),
  );
}

/// A supplemental completion cue. The copy and next-customer action remain
/// available when the generated bitmap cannot be decoded.
class PaymentCompleteIllustration extends StatelessWidget {
  const PaymentCompleteIllustration({super.key});

  @override
  Widget build(BuildContext context) => Semantics(
    label: '결제 완료 안내 그림',
    image: true,
    child: Image.asset(
      'assets/illustrations/payment_complete.png',
      height: 120,
      fit: BoxFit.contain,
      excludeFromSemantics: true,
      errorBuilder: (_, _, _) => const SizedBox.shrink(),
    ),
  );
}
