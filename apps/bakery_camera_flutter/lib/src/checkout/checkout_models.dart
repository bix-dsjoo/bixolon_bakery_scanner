import '../catalog/product.dart';
import '../inference/inference_models.dart';

enum CheckoutPhase {
  ready,
  analyzing,
  retakeRequired,
  customerReview,
  orderReview,
  paying,
  paymentComplete,
  recoverableFailure,
  terminalFailure,
}

enum CustomerResolutionSource {
  aiAutoCustomerAccepted('ai_auto_customer_accepted'),
  customerTop3('customer_top3'),
  customerCatalog('customer_catalog'),
  customerOverrodeAuto('customer_overrode_auto'),
  customerManualCart('customer_manual_cart');

  const CustomerResolutionSource(this.storageValue);

  final String storageValue;

  static CustomerResolutionSource parse(String value) {
    for (final source in values) {
      if (source.storageValue == value) return source;
    }
    throw FormatException('unsupported customer resolution source: $value');
  }
}

final class CheckoutLine {
  CheckoutLine({required this.product, required this.quantity}) {
    if (quantity <= 0) {
      throw ArgumentError.value(quantity, 'quantity', 'must be positive');
    }
  }

  final Product product;
  final int quantity;

  int get totalPrice => product.unitPrice * quantity;
}

/// A customer-facing object derived from, but never substituted for, one
/// immutable inference object. Customer selections are expressed separately.
final class ObjectDraft {
  ObjectDraft._({
    required this.inferenceObject,
    required this.acceptedProduct,
    required List<InferenceCandidate> candidates,
  }) : candidates = List.unmodifiable(candidates);

  factory ObjectDraft.unresolved(InferenceObject inferenceObject) {
    if (!inferenceObject.isUnknown || inferenceObject.candidates.isEmpty) {
      throw ArgumentError.value(
        inferenceObject,
        'inferenceObject',
        'only Unknown inference objects can be unresolved',
      );
    }
    return ObjectDraft._(
      inferenceObject: inferenceObject,
      acceptedProduct: null,
      candidates: inferenceObject.candidates,
    );
  }

  factory ObjectDraft.unresolvedCatalog(InferenceObject inferenceObject) {
    if (inferenceObject.isUnknown || inferenceObject.candidates.isNotEmpty) {
      throw ArgumentError.value(
        inferenceObject,
        'inferenceObject',
        'only registered inference objects can require catalog selection',
      );
    }
    return ObjectDraft._(
      inferenceObject: inferenceObject,
      acceptedProduct: null,
      candidates: const [],
    );
  }

  factory ObjectDraft.accepted({
    required InferenceObject inferenceObject,
    required Product product,
  }) => ObjectDraft._(
    inferenceObject: inferenceObject,
    acceptedProduct: product,
    candidates: const [],
  );

  final InferenceObject inferenceObject;
  final Product? acceptedProduct;
  final List<InferenceCandidate> candidates;

  bool get isResolved => acceptedProduct != null;
  bool get requiresCatalogSelection =>
      acceptedProduct == null && candidates.isEmpty;
  Product? get product => acceptedProduct;
}

/// An audited customer action, distinct from the model inference evidence.
final class ObjectResolutionDraft {
  const ObjectResolutionDraft({
    required this.sessionId,
    required this.inferenceObject,
    required this.product,
    required this.source,
    required this.resolvedAt,
  }) : assert(sessionId != '');

  final String sessionId;
  final InferenceObject inferenceObject;
  final Product product;
  final CustomerResolutionSource source;
  final DateTime resolvedAt;
}

final class FinalOrderDraft {
  FinalOrderDraft({
    required this.sessionId,
    required this.catalogRevision,
    required List<CheckoutLine> lines,
    required this.createdAt,
  }) : assert(sessionId != ''),
       lines = List.unmodifiable(lines) {
    if (lines.any((line) => line.quantity <= 0)) {
      throw ArgumentError.value(
        lines,
        'lines',
        'all quantities must be positive',
      );
    }
  }

  final String sessionId;
  final CatalogRevision catalogRevision;
  final List<CheckoutLine> lines;
  final DateTime createdAt;

  int get totalPrice => lines.fold(0, (sum, line) => sum + line.totalPrice);
}

final class PaymentReceipt {
  PaymentReceipt({
    required this.paymentId,
    required this.orderId,
    required this.sessionId,
    required this.amount,
    required this.currency,
    required this.provider,
    required this.status,
    required this.paidAt,
  }) : assert(paymentId != ''),
       assert(sessionId != '') {
    if (amount < 0) {
      throw ArgumentError.value(amount, 'amount', 'must be non-negative');
    }
  }

  final String paymentId;
  final String orderId;
  final String sessionId;
  final int amount;
  final String currency;
  final String provider;
  final String status;
  final DateTime paidAt;
}

/// The deterministic intent created before the only durable payment commit.
/// The database either records exactly this approved simulation or records
/// nothing; it never generates a second receipt after a retry.
final class SimulatedPaymentRequest {
  SimulatedPaymentRequest({
    required this.paymentId,
    required this.orderId,
    required this.committedAt,
    this.currency = 'KRW',
    this.provider = 'simulated',
    this.status = 'approved',
  }) {
    if (paymentId.trim().isEmpty || orderId.trim().isEmpty) {
      throw ArgumentError('payment and order IDs must not be empty');
    }
    if (currency != 'KRW' || provider != 'simulated' || status != 'approved') {
      throw ArgumentError('only approved KRW simulated payments are supported');
    }
  }

  final String paymentId;
  final String orderId;
  final DateTime committedAt;
  final String currency;
  final String provider;
  final String status;
}

final class CheckoutFailure {
  const CheckoutFailure({
    required this.code,
    required this.message,
    required this.recoverable,
  }) : assert(code != ''),
       assert(message != '');

  final String code;
  final String message;
  final bool recoverable;
}

/// Session-snapshotted customer completion behavior. The controller reads it
/// through the audit store's immutable settings revision once per session.
final class CustomerCompletionPolicy {
  const CustomerCompletionPolicy({
    required this.duration,
    required this.autoReset,
  });

  final Duration duration;
  final bool autoReset;
}

final class SessionSnapshot {
  const SessionSnapshot({
    required this.sessionStartedAt,
    required this.catalogRevision,
  });

  final DateTime sessionStartedAt;
  final CatalogRevision catalogRevision;
}

final class CapturedAuditFile {
  const CapturedAuditFile({
    required this.fileId,
    required this.path,
    required this.sha256,
  }) : assert(fileId != ''),
       assert(path != ''),
       assert(sha256 != '');

  final String fileId;
  final String path;
  final String sha256;
}

final class StagedAttempt {
  const StagedAttempt({
    required this.attemptId,
    required this.sessionId,
    required this.attemptNumber,
  }) : assert(attemptId != ''),
       assert(sessionId != ''),
       assert(attemptNumber > 0);

  final String attemptId;
  final String sessionId;
  final int attemptNumber;
}

final class PersistedAttempt {
  const PersistedAttempt({required this.attemptId}) : assert(attemptId != '');

  final String attemptId;
}

final class ImmutableJsonReceipt {
  const ImmutableJsonReceipt({
    required this.canonicalJson,
    required this.sha256,
  }) : assert(canonicalJson != ''),
       assert(sha256 != '');

  final String canonicalJson;
  final String sha256;
}

final class InterruptedCheckout {
  const InterruptedCheckout({
    required this.sessionId,
    required this.interruptedAt,
  }) : assert(sessionId != '');

  final String sessionId;
  final DateTime interruptedAt;
}
