import 'package:flutter/material.dart';

import '../../checkout/checkout_state.dart';
import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';

class PaymentView extends StatelessWidget {
  const PaymentView({required this.state, super.key});

  final CheckoutState state;

  @override
  Widget build(BuildContext context) => const CheckoutScaffold(
    title: '결제 중',
    primaryAction: SizedBox(height: 56),
    child: Padding(
      padding: EdgeInsets.only(top: 24),
      child: Column(
        children: [
          BakeryStatusBanner(
            status: BakeryStatus.loading,
            title: '결제를 준비하고 있어요',
            message: '완료될 때까지 화면을 유지해 주세요.',
          ),
          SizedBox(height: 28),
          CircularProgressIndicator(),
        ],
      ),
    ),
  );
}
