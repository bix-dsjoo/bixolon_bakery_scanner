import 'package:flutter/material.dart';

import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';

class ReadyView extends StatelessWidget {
  const ReadyView({required this.onScan, super.key});

  final VoidCallback? onScan;

  @override
  Widget build(BuildContext context) => CheckoutScaffold(
    title: '셀프 계산',
    primaryAction: BakeryPrimaryButton(
      label: '빵 확인하기',
      icon: Icons.camera_alt_outlined,
      onPressed: onScan,
      autofocus: true,
    ),
    child: const Padding(
      padding: EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          BakeryStatusBanner(
            status: BakeryStatus.ready,
            title: '빵을 트레이에 올려주세요',
            message: '빵이 겹치지 않도록 펼쳐 놓으면 더 잘 확인할 수 있어요.',
          ),
          SizedBox(height: 24),
          Text('트레이를 카메라 아래에 맞춰주세요.'),
        ],
      ),
    ),
  );
}
