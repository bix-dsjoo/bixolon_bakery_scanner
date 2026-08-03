import 'package:flutter/material.dart';

import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/checkout_scaffold.dart';
import '../components/price_text.dart';
import 'captured_review_overlay.dart';
import 'customer_review_presentation.dart';

/// The stable checkout shell shared by automatic and customer-assisted review.
///
/// Domain phases remain distinct, but the retained scene, right-hand work pane,
/// total, and primary action never move when the last exception is resolved.
class CheckoutReviewWorkspace extends StatelessWidget {
  const CheckoutReviewWorkspace({
    required this.state,
    required this.presentation,
    required this.selectedObjectId,
    required this.onSelectObject,
    required this.taskTitle,
    required this.taskContent,
    required this.primaryActionLabel,
    required this.onPrimaryAction,
    this.footerActions,
    this.overlay,
    this.imageProviderFactory = customerReviewFileImageProvider,
    this.legacySceneKey,
    this.legacyTaskKey,
    this.legacyDividerKey,
    super.key,
  });

  final CheckoutState state;
  final CustomerReviewPresentation presentation;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;
  final String taskTitle;
  final Widget taskContent;
  final String? primaryActionLabel;
  final VoidCallback? onPrimaryAction;
  final Widget? footerActions;
  final Widget? overlay;
  final CustomerReviewImageProviderFactory imageProviderFactory;
  final Key? legacySceneKey;
  final Key? legacyTaskKey;
  final Key? legacyDividerKey;

  @override
  Widget build(BuildContext context) {
    final total = state.lines.fold(0, (sum, line) => sum + line.totalPrice);
    return CheckoutScaffold(
      title: '주문 확인',
      maxWidth: 1240,
      scrollable: false,
      primaryAction: primaryActionLabel == null
          ? null
          : BakeryPrimaryButton(
              label: primaryActionLabel!,
              onPressed: onPrimaryAction,
            ),
      child: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 4, bottom: 16),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final scene = KeyedSubtree(
                  key: const Key('checkout-review-scene-pane'),
                  child: KeyedSubtree(
                    key: legacySceneKey,
                    child: _CheckoutReviewScene(
                      state: state,
                      presentation: presentation,
                      selectedObjectId: selectedObjectId,
                      onSelectObject: onSelectObject,
                      imageProviderFactory: imageProviderFactory,
                    ),
                  ),
                );
                final task = KeyedSubtree(
                  key: const Key('checkout-review-task-pane'),
                  child: KeyedSubtree(
                    key: legacyTaskKey,
                    child: _CheckoutReviewTask(
                      title: taskTitle,
                      content: taskContent,
                      total: total,
                      footerActions: footerActions,
                    ),
                  ),
                );
                if (constraints.maxWidth < 700) {
                  return Column(
                    children: [
                      Expanded(flex: 3, child: scene),
                      const SizedBox(height: 12),
                      SizedBox(
                        key: legacyDividerKey,
                        height: 1,
                        child: const Divider(
                          key: Key('checkout-review-workspace-divider'),
                          height: 1,
                          thickness: 1,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Expanded(flex: 4, child: task),
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(flex: 3, child: scene),
                    const SizedBox(width: 12),
                    SizedBox(
                      key: legacyDividerKey,
                      width: 1,
                      child: const VerticalDivider(
                        key: Key('checkout-review-workspace-divider'),
                        width: 1,
                        thickness: 1,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(flex: 2, child: task),
                  ],
                );
              },
            ),
          ),
          if (overlay case final notice?)
            Positioned.fill(
              child: Align(
                alignment: Alignment.topCenter,
                child: Padding(
                  padding: const EdgeInsets.only(top: 24),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 440),
                    child: notice,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _CheckoutReviewScene extends StatelessWidget {
  const _CheckoutReviewScene({
    required this.state,
    required this.presentation,
    required this.selectedObjectId,
    required this.onSelectObject,
    required this.imageProviderFactory,
  });

  final CheckoutState state;
  final CustomerReviewPresentation presentation;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;
  final CustomerReviewImageProviderFactory imageProviderFactory;

  @override
  Widget build(BuildContext context) {
    final imagePath = state.capturedEvidenceDisplayPath;
    final imageWidth = state.capturedImageWidth;
    final imageHeight = state.capturedImageHeight;
    final hasCapture =
        imagePath != null &&
        imageWidth != null &&
        imageWidth > 0 &&
        imageHeight != null &&
        imageHeight > 0;
    return Padding(
      padding: const EdgeInsets.only(right: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('촬영한 트레이', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Expanded(
            child: Center(
              child: hasCapture
                  ? CapturedReviewOverlay(
                      imagePath: imagePath,
                      imageWidth: imageWidth,
                      imageHeight: imageHeight,
                      objects: presentation.objects,
                      selectedObjectId: selectedObjectId,
                      onSelectObject: onSelectObject,
                      imageProviderFactory: imageProviderFactory,
                    )
                  : const _MissingCapture(),
            ),
          ),
        ],
      ),
    );
  }
}

class _MissingCapture extends StatelessWidget {
  const _MissingCapture();

  @override
  Widget build(BuildContext context) => Semantics(
    label: '직접 담기 안내 그림',
    image: true,
    child: Image.asset(
      'assets/illustrations/manual_cart_entry.png',
      height: 120,
      fit: BoxFit.contain,
      excludeFromSemantics: true,
      errorBuilder: (_, _, _) => const SizedBox.shrink(),
    ),
  );
}

class _CheckoutReviewTask extends StatelessWidget {
  const _CheckoutReviewTask({
    required this.title,
    required this.content,
    required this.total,
    required this.footerActions,
  });

  final String title;
  final Widget content;
  final int total;
  final Widget? footerActions;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Padding(
        padding: const EdgeInsets.only(left: 4, bottom: 8),
        child: Text(title, style: Theme.of(context).textTheme.titleMedium),
      ),
      Expanded(child: content),
      const Divider(height: 24),
      Padding(
        padding: const EdgeInsets.only(left: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('합계', style: Theme.of(context).textTheme.titleLarge),
            PriceText(
              amount: total,
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
        ),
      ),
      if (footerActions != null) ...[const SizedBox(height: 8), footerActions!],
    ],
  );
}
