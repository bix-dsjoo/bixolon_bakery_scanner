import 'package:flutter/material.dart';

import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';

class AnalyzingView extends StatelessWidget {
  const AnalyzingView({super.key});

  @override
  Widget build(BuildContext context) => CheckoutScaffold(
    title: '빵 확인',
    scrollable: false,
    child: Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: 420),
        child: Column(
          mainAxisSize: MainAxisSize.min,
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
    ),
  );
}
