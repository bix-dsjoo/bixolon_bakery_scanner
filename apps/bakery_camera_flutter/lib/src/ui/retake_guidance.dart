import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'bixolon_brand.dart';

final class RetakeGuidance extends StatelessWidget {
  const RetakeGuidance({
    super.key,
    required this.primaryInstruction,
    required this.diagnostics,
  });

  final String primaryInstruction;
  final Widget diagnostics;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(
        '이 사진만으로 판단하기 어려워요',
        style: Theme.of(
          context,
        ).textTheme.titleLarge?.copyWith(color: unknownAmber),
      ),
      const SizedBox(height: 8),
      Text(primaryInstruction, style: Theme.of(context).textTheme.bodyLarge),
      const SizedBox(height: 18),
      DecoratedBox(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: bixolonDivider)),
        ),
        child: ExpansionTile(
          key: const Key('retake-analysis-disclosure'),
          tilePadding: EdgeInsets.zero,
          childrenPadding: EdgeInsets.zero,
          shape: const Border(),
          collapsedShape: const Border(),
          title: const Text('분석 참고'),
          children: [diagnostics],
        ),
      ),
    ],
  );
}
