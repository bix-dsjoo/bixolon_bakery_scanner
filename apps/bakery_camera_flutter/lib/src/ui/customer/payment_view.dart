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
    primaryAction: SizedBox(height: 56),
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
