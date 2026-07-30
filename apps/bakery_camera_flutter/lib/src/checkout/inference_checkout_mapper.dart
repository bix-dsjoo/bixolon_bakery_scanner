import '../catalog/product.dart';
import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'checkout_models.dart';
import 'checkout_ports.dart';

final class InferenceCheckoutMapping {
  InferenceCheckoutMapping({
    required this.phase,
    required List<ObjectDraft> objectDrafts,
    required Map<String, Map<int, Product?>> candidateProducts,
    this.failure,
  }) : objectDrafts = List.unmodifiable(objectDrafts),
       candidateProducts = Map.unmodifiable({
         for (final entry in candidateProducts.entries)
           entry.key: Map<int, Product?>.unmodifiable(entry.value),
       });

  final CheckoutPhase phase;
  final List<ObjectDraft> objectDrafts;
  final Map<String, Map<int, Product?>> candidateProducts;
  final CheckoutFailure? failure;
}

final class InferenceCheckoutMapper {
  const InferenceCheckoutMapper(this._catalog);

  final CatalogRepository _catalog;

  Future<InferenceCheckoutMapping> map({
    required InferenceResult result,
    required CapturedImageSize imageSize,
  }) async {
    if (result.imageWidth != imageSize.width ||
        result.imageHeight != imageSize.height) {
      return _retake(
        code: 'canonical_image_size_mismatch',
        message: 'The analyzed image dimensions do not match the capture.',
      );
    }
    if (!result.presentation.finalCountUsable ||
        result.presentation.state == InferencePresentationState.needsRetake) {
      return _retake(
        code: _retakeCode(result.presentation),
        message: _retakeMessage(result.presentation),
      );
    }

    final drafts = <ObjectDraft>[];
    final candidateProducts = <String, Map<int, Product?>>{};
    for (final object in result.objects) {
      if (!object.isUnknown) {
        final product = await _catalog.productForRecognitionSku(object.skuId!);
        drafts.add(
          product == null
              ? ObjectDraft.unresolvedCatalog(object)
              : ObjectDraft.accepted(inferenceObject: object, product: product),
        );
        continue;
      }

      drafts.add(ObjectDraft.unresolved(object));
      candidateProducts[object.objectId] = {
        for (final candidate in object.candidates)
          candidate.skuId: await _catalog.productForRecognitionSku(
            candidate.skuId,
          ),
      };
    }
    return InferenceCheckoutMapping(
      phase: drafts.every((draft) => draft.isResolved)
          ? CheckoutPhase.orderReview
          : CheckoutPhase.customerReview,
      objectDrafts: drafts,
      candidateProducts: candidateProducts,
    );
  }

  InferenceCheckoutMapping _retake({
    required String code,
    required String message,
  }) => InferenceCheckoutMapping(
    phase: CheckoutPhase.retakeRequired,
    objectDrafts: const [],
    candidateProducts: const {},
    failure: CheckoutFailure(code: code, message: message, recoverable: true),
  );

  static String _retakeCode(InferencePresentation presentation) =>
      switch (presentation.instruction) {
        RetakeInstruction.noBreadDetected => 'no_bread_detected',
        RetakeInstruction.separateBreads => 'separate_breads',
        RetakeInstruction.candidateEvidenceWeak => 'candidate_evidence_weak',
        null => 'unsafe_inference_result',
      };

  static String _retakeMessage(InferencePresentation presentation) =>
      switch (presentation.instruction) {
        RetakeInstruction.noBreadDetected =>
          'No bakery product was detected in the capture.',
        RetakeInstruction.separateBreads =>
          'Products must be separated and scanned again.',
        RetakeInstruction.candidateEvidenceWeak =>
          'Candidate evidence is too weak for customer selection.',
        null => 'The inference result is not safe for checkout.',
      };
}
