// ignore_for_file: prefer_initializing_formals

import 'checkout_models.dart';
import 'checkout_ports.dart';

typedef PaymentClock = DateTime Function();
typedef PaymentIdGenerator = String Function(String prefix);

/// Creates a reproducible simulated-payment intent and serializes duplicate
/// taps. There is deliberately no timer, random decline, or fake delay.
final class SimulatedPaymentService {
  SimulatedPaymentService({
    required CheckoutAuditStore auditStore,
    required PaymentClock clock,
    required PaymentIdGenerator createId,
  }) : _auditStore = auditStore,
       _clock = clock,
       _createId = createId;

  final CheckoutAuditStore _auditStore;
  final PaymentClock _clock;
  final PaymentIdGenerator _createId;
  Future<PaymentReceipt>? _inFlight;

  Future<PaymentReceipt> commit(FinalOrderDraft order) {
    final current = _inFlight;
    if (current != null) return current;
    final request = SimulatedPaymentRequest(
      paymentId: _createId('payment'),
      orderId: _createId('order'),
      committedAt: _clock().toUtc(),
    );
    late final Future<PaymentReceipt> operation;
    operation = _auditStore
        .commitSimulatedPayment(order, request: request)
        .whenComplete(() {
          if (identical(_inFlight, operation)) _inFlight = null;
        });
    _inFlight = operation;
    return operation;
  }
}
