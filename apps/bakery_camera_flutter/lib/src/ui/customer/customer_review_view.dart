import 'dart:io';

import 'package:flutter/material.dart';

import '../../catalog/product.dart';
import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';
import '../components/price_text.dart';

class CustomerReviewView extends StatelessWidget {
  const CustomerReviewView({
    required this.state,
    required this.productForCandidate,
    required this.onChooseTop3,
    required this.onOpenCatalog,
    required this.onContinue,
    super.key,
  });

  final CheckoutState state;
  final Product? Function(String objectId, int skuId) productForCandidate;
  final void Function(String objectId, int skuId) onChooseTop3;
  final ValueChanged<String> onOpenCatalog;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    final draft = state.activeObject;
    if (draft == null) {
      return CheckoutScaffold(
        title: '상품 확인',
        primaryAction: BakeryPrimaryButton(
          label: '주문 확인',
          onPressed: onContinue,
        ),
        child: const SizedBox.shrink(),
      );
    }
    return CheckoutScaffold(
      title: '상품 확인',
      primaryAction: BakeryPrimaryButton(label: '다음', onPressed: null),
      child: Padding(
        padding: const EdgeInsets.only(top: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            BakeryStatusBanner(
              status: BakeryStatus.uncertain,
              title: '이 빵이 맞나요?',
              message: '한 개씩 확인하면 주문을 정확히 담을 수 있어요.',
            ),
            const SizedBox(height: 20),
            if (state.capturedEvidencePath case final imagePath?) ...[
              CapturedReviewImage(
                imagePath: imagePath,
                imageWidth: state.capturedImageWidth ?? 1,
                imageHeight: state.capturedImageHeight ?? 1,
                crop: Rect.fromLTRB(
                  draft.inferenceObject.bboxXyxy[0],
                  draft.inferenceObject.bboxXyxy[1],
                  draft.inferenceObject.bboxXyxy[2],
                  draft.inferenceObject.bboxXyxy[3],
                ),
              ),
              const SizedBox(height: 20),
            ],
            if (draft.requiresCatalogSelection)
              const Text('목록에서 상품을 찾아 선택해 주세요.')
            else ...[
              for (final candidate in draft.candidates)
                if (productForCandidate(
                      draft.inferenceObject.objectId,
                      candidate.skuId,
                    )
                    case final product?)
                  ListTile(
                    title: Text(product.displayName),
                    trailing: PriceText(amount: product.unitPrice),
                    onTap: () => onChooseTop3(
                      draft.inferenceObject.objectId,
                      candidate.skuId,
                    ),
                  ),
            ],
            TextButton.icon(
              onPressed: () => onOpenCatalog(draft.inferenceObject.objectId),
              icon: const Icon(Icons.search),
              label: const Text('전체 상품에서 찾기'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Presents only the retained audit still and the currently selected bread.
/// No recognition geometry, score, or model-facing data is rendered here.
class CapturedReviewImage extends StatelessWidget {
  const CapturedReviewImage({
    required this.imagePath,
    required this.imageWidth,
    required this.imageHeight,
    required this.crop,
    super.key,
  });

  final String imagePath;
  final int imageWidth;
  final int imageHeight;
  final Rect crop;

  @override
  Widget build(BuildContext context) {
    final alignment = Alignment(
      (crop.center.dx / imageWidth * 2 - 1).clamp(-1.0, 1.0).toDouble(),
      (crop.center.dy / imageHeight * 2 - 1).clamp(-1.0, 1.0).toDouble(),
    );
    Widget image(BoxFit fit, AlignmentGeometry alignment) => Image.file(
      File(imagePath),
      fit: fit,
      alignment: alignment,
      errorBuilder: (_, _, _) => const ColoredBox(
        color: Color(0xFFE9E7E2),
        child: Center(child: Icon(Icons.image_outlined)),
      ),
    );
    return Row(
      children: [
        Expanded(
          child: Semantics(
            label: '촬영한 트레이 사진',
            image: true,
            child: ClipRRect(
              key: const Key('captured-still'),
              borderRadius: BorderRadius.circular(12),
              child: AspectRatio(
                aspectRatio: imageWidth / imageHeight,
                child: image(BoxFit.cover, Alignment.center),
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        SizedBox(
          width: 112,
          child: Semantics(
            label: '선택한 빵 사진',
            image: true,
            child: ClipRRect(
              key: const Key('selected-object-crop'),
              borderRadius: BorderRadius.circular(12),
              child: AspectRatio(
                aspectRatio: 1,
                child: image(BoxFit.cover, alignment),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
