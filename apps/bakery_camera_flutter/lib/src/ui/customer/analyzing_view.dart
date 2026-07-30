import 'package:flutter/material.dart';

import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';

class AnalyzingView extends StatelessWidget {
  const AnalyzingView({super.key});

  @override
  Widget build(BuildContext context) => const CheckoutScaffold(
    title: '빵 확인',
    primaryAction: SizedBox(height: 56),
    child: Padding(
      padding: EdgeInsets.only(top: 24),
      child: Column(
        children: [
          BakeryStatusBanner(
            status: BakeryStatus.loading,
            title: '빵을 확인하고 있어요',
            message: '잠시만 기다려주세요.',
          ),
          SizedBox(height: 28),
          CircularProgressIndicator(),
        ],
      ),
    ),
  );
}
