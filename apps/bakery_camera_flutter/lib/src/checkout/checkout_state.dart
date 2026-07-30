import 'checkout_models.dart';

final class CheckoutState {
  CheckoutState({
    required this.phase,
    required List<ObjectDraft> objectDrafts,
    required List<CheckoutLine> lines,
    this.failure,
    this.paymentReceipt,
    this.capturedEvidencePath,
    this.capturedImageWidth,
    this.capturedImageHeight,
  }) : objectDrafts = List.unmodifiable(objectDrafts),
       lines = List.unmodifiable(lines);

  final CheckoutPhase phase;
  final List<ObjectDraft> objectDrafts;
  final List<CheckoutLine> lines;
  final CheckoutFailure? failure;
  final PaymentReceipt? paymentReceipt;

  /// A read-only audit-file location for customer review only. This is never
  /// used as inference input and does not replace the immutable receipt.
  final String? capturedEvidencePath;
  final int? capturedImageWidth;
  final int? capturedImageHeight;

  ObjectDraft? get activeObject {
    for (final draft in objectDrafts) {
      if (!draft.isResolved) return draft;
    }
    return null;
  }

  bool get canPay =>
      phase == CheckoutPhase.orderReview &&
      objectDrafts.every((draft) => draft.isResolved) &&
      lines.any((line) => line.quantity > 0);
}
