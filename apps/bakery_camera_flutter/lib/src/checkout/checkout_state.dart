import 'checkout_models.dart';

final class CheckoutState {
  CheckoutState({
    required this.phase,
    required List<ObjectDraft> objectDrafts,
    required List<CheckoutLine> lines,
    this.failure,
    this.paymentReceipt,
  }) : objectDrafts = List.unmodifiable(objectDrafts),
       lines = List.unmodifiable(lines);

  final CheckoutPhase phase;
  final List<ObjectDraft> objectDrafts;
  final List<CheckoutLine> lines;
  final CheckoutFailure? failure;
  final PaymentReceipt? paymentReceipt;

  bool get canPay =>
      phase == CheckoutPhase.orderReview &&
      objectDrafts.every((draft) => draft.isResolved) &&
      lines.any((line) => line.quantity > 0);
}
