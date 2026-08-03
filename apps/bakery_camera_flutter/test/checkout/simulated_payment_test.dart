import 'dart:async';

import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_ports.dart';
import 'package:bakery_camera_prototype/src/checkout/simulated_payment_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final order = FinalOrderDraft(
    sessionId: 'session-1',
    catalogRevision: CatalogRevision(
      revisionId: 'catalog-1',
      sha256: 'a' * 64,
      createdAt: DateTime.utc(2026, 7, 30),
    ),
    lines: [
      CheckoutLine(
        product: Product(
          productId: 'bread-1',
          displayName: '크루아상',
          unitPrice: 2800,
          recognitionSkuId: 1,
          categoryId: 'bread',
          photoAssetPath: null,
          active: true,
          sortOrder: 1,
        ),
        quantity: 2,
      ),
    ],
    createdAt: DateTime.utc(2026, 7, 30),
  );

  test(
    'rapid simulated payment requests share one deterministic durable commit',
    () async {
      final store = _PaymentStore()..gate = Completer<void>();
      final service = SimulatedPaymentService(
        auditStore: store,
        clock: () => DateTime.utc(2026, 7, 30, 12),
        createId: (prefix) => '$prefix-fixed',
      );

      final first = service.commit(order);
      final second = service.commit(order);
      await store.started.future;
      expect(identical(first, second), isTrue);
      expect(store.requests, hasLength(1));
      expect(store.requests.single.paymentId, 'payment-fixed');
      expect(store.requests.single.orderId, 'order-fixed');
      expect(store.requests.single.committedAt, DateTime.utc(2026, 7, 30, 12));

      store.gate!.complete();
      final receipt = await first;
      expect(receipt.status, 'approved');
      expect(receipt.provider, 'simulated');
      expect(receipt.currency, 'KRW');
      expect(receipt.orderId, 'order-fixed');
    },
  );

  test(
    'failed payment commit leaves the order available for a later retry',
    () async {
      final store = _PaymentStore()..failure = StateError('database offline');
      final service = SimulatedPaymentService(
        auditStore: store,
        clock: () => DateTime.utc(2026, 7, 30, 12),
        createId: (prefix) => '$prefix-${store.requests.length}',
      );

      await expectLater(service.commit(order), throwsStateError);
      store.failure = null;
      final receipt = await service.commit(order);

      expect(store.requests, hasLength(2));
      expect(receipt.paymentId, 'payment-1');
    },
  );
}

final class _PaymentStore implements CheckoutAuditStore {
  final started = Completer<void>();
  final requests = <SimulatedPaymentRequest>[];
  Completer<void>? gate;
  Object? failure;

  @override
  Future<PaymentReceipt> commitSimulatedPayment(
    FinalOrderDraft order, {
    SimulatedPaymentRequest? request,
  }) async {
    final intent = request!;
    requests.add(intent);
    if (!started.isCompleted) started.complete();
    await gate?.future;
    final error = failure;
    if (error != null) throw error;
    return PaymentReceipt(
      paymentId: intent.paymentId,
      orderId: intent.orderId,
      sessionId: order.sessionId,
      amount: order.totalPrice,
      currency: intent.currency,
      provider: intent.provider,
      status: intent.status,
      paidAt: intent.committedAt,
    );
  }

  @override
  Future<void> abandonSession(String sessionId, String reason) async {}
  @override
  Future<String> beginSession(SessionSnapshot snapshot) async => 'session-1';
  @override
  Future<CustomerCompletionPolicy> completionPolicyForSession(
    String sessionId,
  ) async => throw UnimplementedError();
  @override
  Future<PersistedAttempt> completeAttempt({
    required StagedAttempt attempt,
    required dynamic result,
    required ImmutableJsonReceipt receipt,
  }) async => throw UnimplementedError();
  @override
  Future<void> enterManualCartMode(
    String sessionId,
    DateTime enteredAt,
  ) async {}
  @override
  Future<List<InterruptedCheckout>> interruptNonterminalSessions(
    DateTime detectedAt,
  ) async => const [];
  @override
  Future<void> recordResolution(ObjectResolutionDraft resolution) async {}
  @override
  Future<void> replaceDraftOrder(
    String sessionId,
    List<CheckoutLine> lines,
  ) async {}
  @override
  Future<int> retryLimitForSession(String sessionId) async => 0;
  @override
  Future<StagedAttempt> stageAttempt({
    required String sessionId,
    required int attemptNumber,
    required CapturedAuditFile image,
  }) async => throw UnimplementedError();
}
