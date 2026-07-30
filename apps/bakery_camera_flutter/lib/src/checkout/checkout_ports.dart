import '../catalog/product.dart';
import '../inference/inference_models.dart';
import 'checkout_models.dart';

abstract interface class CheckoutAuditStore {
  Future<List<InterruptedCheckout>> interruptNonterminalSessions(
    DateTime detectedAt,
  );
  Future<String> beginSession(SessionSnapshot snapshot);
  Future<int> retryLimitForSession(String sessionId);
  Future<CustomerCompletionPolicy> completionPolicyForSession(String sessionId);
  Future<void> enterManualCartMode(String sessionId, DateTime enteredAt);
  Future<StagedAttempt> stageAttempt({
    required String sessionId,
    required int attemptNumber,
    required CapturedAuditFile image,
  });
  Future<PersistedAttempt> completeAttempt({
    required StagedAttempt attempt,
    required InferenceResult result,
    required ImmutableJsonReceipt receipt,
  });
  Future<void> recordResolution(ObjectResolutionDraft resolution);
  Future<void> replaceDraftOrder(String sessionId, List<CheckoutLine> lines);
  Future<PaymentReceipt> commitSimulatedPayment(
    FinalOrderDraft order, {
    SimulatedPaymentRequest? request,
  });
  Future<void> abandonSession(String sessionId, String reason);
}

/// Startup recovery runs before a new customer session. The returned data is
/// audit-only and must never be used to resume or charge a prior session.
abstract interface class CheckoutRecoveryPort {
  Future<CheckoutRecoveryReport> recoverInterruptedCheckout(
    DateTime detectedAt,
  );
}

final class CheckoutRecoveryReport {
  const CheckoutRecoveryReport({
    required this.interruptedSessionIds,
    required this.repairedPaymentSessionIds,
    required this.evidenceIssuePaths,
  });

  final List<String> interruptedSessionIds;
  final List<String> repairedPaymentSessionIds;
  final List<String> evidenceIssuePaths;
}

abstract interface class CatalogRepository {
  Future<CatalogSnapshot> activeCatalog();
  Future<Product?> productForRecognitionSku(int recognitionSkuId);
  Future<CustomerCatalogDiscovery> customerDiscovery();
  Future<List<Product>> search(String query);
}

abstract interface class CheckoutEvidenceStore {
  Future<CapturedAuditFile> retainCapture({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required String sourcePath,
  });
  Future<void> retainInferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  });
}

/// Resolves a persisted audit-relative location for a customer-only local
/// preview. Implementations must reject paths outside their owned audit root.
abstract interface class AuditDisplayPathResolver {
  Future<String> resolveForDisplay(String relativePath);
}
