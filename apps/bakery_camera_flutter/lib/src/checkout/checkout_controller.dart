// ignore_for_file: prefer_initializing_formals

import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';

import '../catalog/product.dart';
import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'checkout_models.dart';
import 'checkout_ports.dart';
import 'checkout_recovery.dart';
import 'checkout_state.dart';
import 'inference_checkout_mapper.dart';
import 'simulated_payment_service.dart';

typedef CheckoutClock = DateTime Function();
typedef InferenceReceiptFactory =
    ImmutableJsonReceipt Function(InferenceResult result);

final class _ScanRecovery {
  _ScanRecovery({required this.sessionId, required this.attemptNumber});

  final String sessionId;
  final int attemptNumber;
  DateTime? capturedAt;
  StagedAttempt? stagedAttempt;
  InferenceResult? result;
  CapturedImageSize? imageSize;
  ImmutableJsonReceipt? receipt;
  CapturedAuditFile? retainedCapture;
  bool receiptRetained = false;
  bool attemptCompleted = false;
  InferenceCheckoutMapping? mapping;
}

final class CheckoutController extends ChangeNotifier {
  CheckoutController({
    required ScannerController scanner,
    required CheckoutAuditStore auditStore,
    required CheckoutEvidenceStore evidenceStore,
    required AuditDisplayPathResolver displayPathResolver,
    required CatalogRepository catalogRepository,
    required InferenceReceiptFactory createInferenceReceipt,
    CheckoutClock? now,
    SimulatedPaymentService? paymentService,
  }) : _scanner = scanner,
       _auditStore = auditStore,
       _evidenceStore = evidenceStore,
       _displayPathResolver = displayPathResolver,
       _catalogRepository = catalogRepository,
       _mapper = const InferenceCheckoutMapper(),
       _createInferenceReceipt = createInferenceReceipt,
       _now = now ?? DateTime.now,
       _paymentService =
           paymentService ??
           SimulatedPaymentService(
             auditStore: auditStore,
             clock: now ?? DateTime.now,
             createId: _FallbackPaymentIds.next,
           );

  final ScannerController _scanner;
  final CheckoutAuditStore _auditStore;
  final CheckoutEvidenceStore _evidenceStore;
  final AuditDisplayPathResolver _displayPathResolver;
  final CatalogRepository _catalogRepository;
  final InferenceCheckoutMapper _mapper;
  final InferenceReceiptFactory _createInferenceReceipt;
  final CheckoutClock _now;
  final SimulatedPaymentService _paymentService;

  CheckoutState _state = CheckoutState(
    phase: CheckoutPhase.ready,
    objectDrafts: const [],
    lines: const [],
  );
  List<InterruptedCheckout> _interruptedCheckouts = const [];
  CatalogSnapshot? _catalog;
  CustomerCatalogDiscovery? _customerCatalogDiscovery;
  String? _sessionId;
  int? _retryLimit;
  CustomerCompletionPolicy? _completionPolicy;
  String _kioskDisplayName = 'BIXOLON Bakery';
  int _attemptNumber = 0;
  int _failedAttempts = 0;
  int _scanGeneration = 0;
  bool _initialized = false;
  bool _closed = false;
  bool _sessionActive = false;
  bool _sessionStartInFlight = false;
  Completer<void>? _sessionStartCompletion;
  Future<void>? _closeFuture;
  bool _manualCartMode = false;
  Map<String, Map<int, Product?>> _candidateProducts = const {};
  final Set<String> _explicitlyResolvedObjectIds = {};
  final Map<String, int> _manualQuantities = {};
  FinalOrderDraft? _frozenOrder;
  CheckoutState? _frozenReviewState;
  _ScanRecovery? _scanRecovery;

  CheckoutState get state => _state;
  List<InterruptedCheckout> get interruptedCheckouts => _interruptedCheckouts;
  bool get manualCartEligible =>
      _state.phase == CheckoutPhase.retakeRequired &&
      _retryLimit != null &&
      _failedAttempts > _retryLimit!;
  CustomerCompletionPolicy get completionPolicy =>
      _completionPolicy ??
      (throw StateError('checkout completion policy is unavailable'));
  String get kioskDisplayName => _kioskDisplayName;
  CameraController? get previewController => _scanner.previewController;
  Map<int, int> get inferenceTotals =>
      Map.unmodifiable(_scanner.state.result?.counts ?? const {});
  int get unknownInferenceTotal => _scanner.state.result?.unknownCount ?? 0;

  /// True only while this controller owns an unfinished, auditable checkout.
  /// A completed payment clears this flag before its completion screen appears.
  bool get hasActiveCustomerCheckout => _sessionActive;

  Product? productForCandidate(String objectId, int recognitionSkuId) =>
      _candidateProducts[objectId]?[recognitionSkuId];

  CustomerCatalogDiscovery get customerCatalogDiscovery =>
      _customerCatalogDiscovery ??
      (throw StateError('checkout catalog discovery is unavailable'));

  Future<List<Product>> searchSessionCatalog(String query) async =>
      _requireCatalog().search(query);

  Future<void> initialize() async {
    _ensureOpen();
    if (_initialized) {
      throw StateError('checkout controller can only be initialized once');
    }
    _initialized = true;
    _reserveSessionStart();
    try {
      _interruptedCheckouts = List.unmodifiable(await _recoverAtStartup());
      await _beginSession();
      await _scanner.initialize();
      if (!_scanner.state.cameraReady ||
          _scanner.state.workerStatus != WorkerStatus.ready) {
        await _abandonActiveSession('scanner_startup_failure');
        _replaceState(
          _failureState(
            phase: CheckoutPhase.terminalFailure,
            code: 'scanner_startup_failure',
            message: 'Camera or inference worker startup failed.',
            recoverable: false,
          ),
        );
        return;
      }
      _replaceState(_emptyState(CheckoutPhase.ready));
    } catch (error) {
      await _terminalizeSessionStartFailure(
        code: 'checkout_initialization_failure',
        abandonReason: 'checkout_initialization_failure',
        error: error,
      );
    } finally {
      _finishSessionStart();
    }
  }

  Future<void> scan() async {
    _ensureInitialized();
    if (_state.phase != CheckoutPhase.ready) {
      throw StateError('scan requires the ready phase');
    }
    final sessionId = _requireSession();
    final generation = ++_scanGeneration;
    _attemptNumber += 1;
    final attemptNumber = _attemptNumber;
    final recovery = _ScanRecovery(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
    );
    _scanRecovery = recovery;
    _replaceState(_emptyState(CheckoutPhase.analyzing));

    try {
      await _scanner.analyze(
        beforeInference: (capture) => _stageRecovery(recovery, capture),
      );
      if (generation != _scanGeneration) {
        await _releaseCanceledCapture(recovery.stagedAttempt);
        return;
      }
      await _completeAndPresent(recovery);
    } catch (error) {
      if (generation != _scanGeneration) {
        await _releaseCanceledCapture(recovery.stagedAttempt);
        return;
      }
      final terminal =
          _scanner.state.workerStatus == WorkerStatus.fatal ||
          (!_scanner.state.cameraReady && _scanner.state.cameraError != null);
      if (terminal) {
        await _abandonActiveSession('scanner_terminal_failure');
      }
      _replaceState(
        _failureState(
          phase: terminal
              ? CheckoutPhase.terminalFailure
              : CheckoutPhase.recoverableFailure,
          code: terminal ? 'scanner_terminal_failure' : 'audit_or_scan_failure',
          message: 'The scan could not be safely completed: $error',
          recoverable: !terminal,
        ),
      );
    }
  }

  Future<void> cancelScan() async {
    _ensureInitialized();
    if (_state.phase != CheckoutPhase.analyzing) {
      throw StateError('cancel requires an active analysis');
    }
    try {
      await _abandonActiveSession('customer_cancelled_analysis');
    } catch (error) {
      _replaceState(
        CheckoutState(
          phase: CheckoutPhase.analyzing,
          objectDrafts: const [],
          lines: const [],
          failure: CheckoutFailure(
            code: 'cancellation_persistence_failure',
            message: 'Cancellation could not be durably recorded: $error',
            recoverable: true,
          ),
        ),
      );
      return;
    }
    _scanGeneration += 1;
    _replaceState(
      _failureState(
        phase: CheckoutPhase.terminalFailure,
        code: 'analysis_cancelled',
        message: 'The customer cancelled the active scan.',
        recoverable: false,
      ),
    );
  }

  Future<void> retake() async {
    _ensurePhase(CheckoutPhase.retakeRequired, 'retake');
    await _scanner.resetCapture();
    _candidateProducts = const {};
    _replaceState(_emptyState(CheckoutPhase.ready));
  }

  /// Records a customer-requested rescan, then returns directly to live capture.
  Future<void> restartCapture() async {
    await reportCountMismatch();
    await retake();
  }

  Future<void> enterManualCart() async {
    _ensurePhase(CheckoutPhase.retakeRequired, 'manual cart');
    if (!manualCartEligible) {
      throw StateError('manual cart requires exhausted retries');
    }
    _replaceState(
      _failureState(
        phase: CheckoutPhase.recoverableFailure,
        code: 'manual_cart_entry_failure',
        message: 'Manual cart entry is being durably prepared.',
        recoverable: true,
      ),
    );
    await _completeManualCartEntry();
  }

  Future<void> _completeManualCartEntry() async {
    final sessionId = _requireSession();
    try {
      if (!_manualCartMode) {
        await _auditStore.enterManualCartMode(sessionId, _utcNow());
        _manualCartMode = true;
      }
      _candidateProducts = const {};
      _explicitlyResolvedObjectIds.clear();
      _manualQuantities.clear();
      await _auditStore.replaceDraftOrder(sessionId, const []);
      _replaceState(_emptyState(CheckoutPhase.orderReview));
    } catch (error) {
      _replaceState(
        _failureState(
          phase: CheckoutPhase.recoverableFailure,
          code: 'manual_cart_entry_failure',
          message: 'Manual cart entry could not be safely completed: $error',
          recoverable: true,
        ),
      );
    }
  }

  Future<void> chooseTop3(String objectId, int recognitionSkuId) async {
    _ensurePhase(CheckoutPhase.customerReview, 'Top 3 selection');
    final draft = _draft(objectId);
    if (!draft.inferenceObject.isUnknown ||
        !draft.inferenceObject.candidates.any(
          (candidate) => candidate.skuId == recognitionSkuId,
        )) {
      throw StateError('selection is not an exact candidate for this object');
    }
    final product = productForCandidate(objectId, recognitionSkuId);
    if (product == null) {
      throw StateError('candidate is unavailable in the active catalog');
    }
    await _resolve(
      draft: draft,
      product: product,
      source: CustomerResolutionSource.customerTop3,
    );
  }

  Future<void> chooseCatalog(String objectId, String productId) async {
    _ensurePhase(CheckoutPhase.customerReview, 'catalog selection');
    final draft = _draft(objectId);
    final product = _product(productId);
    await _resolve(
      draft: draft,
      product: product,
      source: CustomerResolutionSource.customerCatalog,
    );
  }

  Future<void> acceptAiSelection(String objectId) async {
    _ensurePhase(CheckoutPhase.customerReview, 'AI selection');
    final draft = _draft(objectId);
    final object = draft.inferenceObject;
    if (object.isUnknown) {
      throw StateError('Unknown objects have no AI selection to accept');
    }
    final product = _productForRecognitionSku(object.skuId!);
    if (product == null) {
      throw StateError('AI selection has no active catalog product');
    }
    await _resolve(
      draft: draft,
      product: product,
      source: CustomerResolutionSource.aiAutoCustomerAccepted,
    );
  }

  /// Replaces a previously accepted registered result with a customer-selected
  /// catalog product. The immutable inference receipt is intentionally left
  /// untouched; only the audited customer resolution changes.
  Future<void> overrideResolvedProduct(
    String objectId,
    String productId,
  ) async {
    _ensurePhase(CheckoutPhase.orderReview, 'product override');
    final draft = _draft(objectId);
    if (draft.inferenceObject.isUnknown || !draft.isResolved) {
      throw StateError('only an accepted registered result can be overridden');
    }
    final product = _product(productId);
    await _resolve(
      draft: draft,
      product: product,
      source: _overrideSource(draft.inferenceObject, product),
    );
  }

  Future<void> continueToOrderReview() async {
    _ensurePhase(CheckoutPhase.customerReview, 'continue');
    if (_state.objectDrafts.any((draft) => !draft.isResolved)) {
      throw StateError('all inference objects must be resolved');
    }
    await _persistLines(_state.lines);
    _replaceState(
      CheckoutState(
        phase: CheckoutPhase.orderReview,
        objectDrafts: _state.objectDrafts,
        lines: _state.lines,
      ),
    );
  }

  Future<void> reportCountMismatch() async {
    if (_state.phase != CheckoutPhase.customerReview &&
        _state.phase != CheckoutPhase.orderReview) {
      throw StateError('count mismatch requires a customer-visible result');
    }
    if (_manualCartMode) {
      throw StateError('manual cart mode is session-absorbing');
    }
    _failedAttempts += 1;
    _candidateProducts = const {};
    _manualQuantities.clear();
    await _persistLines(const []);
    _replaceState(
      _failureState(
        phase: CheckoutPhase.retakeRequired,
        code: 'customer_count_mismatch',
        message: 'The customer reported a different product count.',
        recoverable: true,
      ),
    );
  }

  Future<void> addManualProduct(String productId) async {
    _ensurePhase(CheckoutPhase.orderReview, 'add product');
    final product = _product(productId);
    _manualQuantities.update(
      product.productId,
      (quantity) => quantity + 1,
      ifAbsent: () => 1,
    );
    await _publishEditedLines();
  }

  Future<void> setQuantity(String productId, int quantity) async {
    _ensurePhase(CheckoutPhase.orderReview, 'set quantity');
    if (quantity <= 0) {
      throw ArgumentError.value(quantity, 'quantity', 'must be positive');
    }
    _product(productId);
    final inferred = _resolvedQuantity(productId);
    if (quantity < inferred) {
      throw StateError('quantity cannot omit resolved inference objects');
    }
    final manual = quantity - inferred;
    if (manual == 0) {
      _manualQuantities.remove(productId);
    } else {
      _manualQuantities[productId] = manual;
    }
    await _publishEditedLines();
  }

  Future<void> removeProduct(String productId) async {
    _ensurePhase(CheckoutPhase.orderReview, 'remove product');
    if (_resolvedQuantity(productId) != 0) {
      throw StateError('resolved inference products cannot be removed');
    }
    _manualQuantities.remove(productId);
    await _publishEditedLines();
  }

  Future<void> pay() async {
    _ensurePhase(CheckoutPhase.orderReview, 'payment');
    if (!_state.canPay) {
      throw StateError('payment requires a resolved nonempty order');
    }
    final prior = _state;
    final order = FinalOrderDraft(
      sessionId: _requireSession(),
      catalogRevision: _requireCatalog().revision,
      lines: prior.lines,
      createdAt: _utcNow(),
    );
    _frozenOrder = order;
    _frozenReviewState = prior;
    _replaceState(
      CheckoutState(
        phase: CheckoutPhase.paying,
        objectDrafts: prior.objectDrafts,
        lines: prior.lines,
      ),
    );
    try {
      await _prepareAndCommitFrozenPayment(order, prior);
    } catch (error) {
      _publishPaymentFailure(prior, error);
    }
  }

  Future<void> retryFailure() async {
    _ensurePhase(CheckoutPhase.recoverableFailure, 'retry failure');
    if (_state.failure?.code == 'payment_commit_failure') {
      final order = _frozenOrder;
      final review = _frozenReviewState;
      if (order == null || review == null) {
        throw StateError('payment failure has no frozen order to retry');
      }
      _replaceState(
        CheckoutState(
          phase: CheckoutPhase.paying,
          objectDrafts: review.objectDrafts,
          lines: review.lines,
        ),
      );
      try {
        await _prepareAndCommitFrozenPayment(order, review);
      } catch (error) {
        _publishPaymentFailure(review, error);
      }
      return;
    }
    if (_state.failure?.code == 'manual_cart_entry_failure') {
      await _completeManualCartEntry();
      return;
    }
    if (_state.failure?.code == 'audit_or_scan_failure') {
      final recovery = _scanRecovery;
      if (recovery == null) {
        throw StateError('scan failure has no retained recovery context');
      }
      _replaceState(_emptyState(CheckoutPhase.analyzing));
      try {
        if (_scanner.state.result == null) {
          if (_scanner.state.capturedImagePath == null) {
            await _scanner.resetCapture();
            _scanRecovery = null;
            _replaceState(_emptyState(CheckoutPhase.ready));
            return;
          }
          await _scanner.retryAnalysis(
            beforeInference: recovery.stagedAttempt == null
                ? (capture) => _stageRecovery(recovery, capture)
                : null,
          );
        }
        await _completeAndPresent(recovery);
      } catch (error) {
        _replaceState(
          _failureState(
            phase: CheckoutPhase.recoverableFailure,
            code: 'audit_or_scan_failure',
            message: 'The scan retry could not be safely completed: $error',
            recoverable: true,
          ),
        );
      }
      return;
    }
    throw StateError('recoverable failure has no supported retry path');
  }

  Future<void> startNextCustomer() async {
    if (_state.phase != CheckoutPhase.paymentComplete &&
        _state.phase != CheckoutPhase.terminalFailure) {
      throw StateError('next customer requires a terminal checkout');
    }
    _reserveSessionStart();
    try {
      if (_sessionActive) {
        await _abandonActiveSession('next_customer_recovery');
      }
      await _scanner.resetCapture();
      await _beginSession();
      _replaceState(_emptyState(CheckoutPhase.ready));
    } catch (error) {
      await _terminalizeSessionStartFailure(
        code: 'checkout_session_start_failure',
        abandonReason: 'checkout_session_start_failure',
        error: error,
      );
    } finally {
      _finishSessionStart();
    }
  }

  /// Durably abandons the current unfinished checkout before the app exposes
  /// the administrator surface. Paid sessions cannot enter this path.
  Future<void> abandonForAdminEntry() async {
    _ensureInitialized();
    if (!_sessionActive || _state.phase == CheckoutPhase.paymentComplete) {
      throw StateError(
        'administrator entry requires an active unfinished session',
      );
    }
    if (_state.phase == CheckoutPhase.paying) {
      throw StateError(
        'administrator entry is unavailable while payment commits',
      );
    }
    await _abandonActiveSession('admin_mode_entered');
    _scanGeneration += 1;
  }

  /// Creates a brand-new session before customer controls become available
  /// after the administrator exits. The operator's previous console state is
  /// owned outside this controller and deliberately does not affect receipts.
  Future<void> startFreshCustomerSession() async {
    _ensureInitialized();
    if (_state.phase == CheckoutPhase.paying) {
      throw StateError('cannot start a customer session while payment commits');
    }
    _reserveSessionStart();
    try {
      if (_sessionActive) {
        await _abandonActiveSession('admin_mode_exit_recovery');
      }
      await _scanner.resetCapture();
      await _beginSession();
      _replaceState(_emptyState(CheckoutPhase.ready));
    } catch (error) {
      await _terminalizeSessionStartFailure(
        code: 'admin_customer_session_start_failure',
        abandonReason: 'admin_customer_session_start_failure',
        error: error,
      );
    } finally {
      _finishSessionStart();
    }
  }

  Future<void> close() {
    final existing = _closeFuture;
    if (existing != null) return existing;
    final closing = _closeOnce();
    _closeFuture = closing;
    return closing;
  }

  Future<void> _closeOnce() async {
    _closed = true;
    final sessionStart = _sessionStartCompletion;
    if (sessionStart != null) {
      await sessionStart.future;
    }
    await _abandonActiveSession('controller_closed');
    await _scanner.close();
  }

  Future<void> _beginSession() async {
    if (!_sessionStartInFlight) {
      throw StateError('checkout session startup must be reserved');
    }
    if (_sessionActive) {
      throw StateError('cannot overwrite an active checkout session');
    }
    _ensureOpen();
    final catalog = await _catalogRepository.activeCatalog();
    final discovery = await _catalogRepository.customerDiscoveryFor(catalog);
    _verifyDiscoverySnapshot(catalog, discovery);
    _ensureOpen();
    final sessionId = await _auditStore.beginSession(
      SessionSnapshot(
        sessionStartedAt: _utcNow(),
        catalogRevision: catalog.revision,
      ),
    );
    _catalog = catalog;
    _customerCatalogDiscovery = discovery;
    _sessionId = sessionId;
    _sessionActive = true;
    final retryLimit = await _auditStore.retryLimitForSession(sessionId);
    if (retryLimit < 0) {
      throw StateError('session retry limit must be non-negative');
    }
    _retryLimit = retryLimit;
    _completionPolicy = await _auditStore.completionPolicyForSession(sessionId);
    final presentationSource = _auditStore;
    if (presentationSource is CustomerKioskPresentationSource) {
      final displayName =
          await (presentationSource as CustomerKioskPresentationSource)
              .kioskDisplayNameForSession(sessionId);
      if (displayName.trim().isEmpty) {
        throw StateError('session kiosk display name must not be empty');
      }
      _kioskDisplayName = displayName.trim();
    }
    _attemptNumber = 0;
    _failedAttempts = 0;
    _manualCartMode = false;
    _frozenOrder = null;
    _frozenReviewState = null;
    _scanRecovery = null;
    _candidateProducts = const {};
    _explicitlyResolvedObjectIds.clear();
    _manualQuantities.clear();
  }

  Future<List<InterruptedCheckout>> _recoverAtStartup() async {
    final store = _auditStore;
    if (store is CheckoutRecoveryPort) {
      final result = await CheckoutRecovery(
        port: store as CheckoutRecoveryPort,
        clock: _utcNow,
      ).recover();
      return [
        for (final sessionId in result.interruptedSessionIds)
          InterruptedCheckout(sessionId: sessionId, interruptedAt: _utcNow()),
      ];
    }
    return store.interruptNonterminalSessions(_utcNow());
  }

  void _reserveSessionStart() {
    _ensureOpen();
    if (_sessionStartInFlight) {
      throw StateError('checkout session startup is already in progress');
    }
    _sessionStartInFlight = true;
    _sessionStartCompletion = Completer<void>();
  }

  void _finishSessionStart() {
    _sessionStartInFlight = false;
    final completion = _sessionStartCompletion;
    _sessionStartCompletion = null;
    if (completion != null && !completion.isCompleted) {
      completion.complete();
    }
  }

  Future<void> _resolve({
    required ObjectDraft draft,
    required Product product,
    required CustomerResolutionSource source,
  }) async {
    await _auditStore.recordResolution(
      ObjectResolutionDraft(
        sessionId: _requireSession(),
        inferenceObject: draft.inferenceObject,
        product: product,
        source: source,
        resolvedAt: _utcNow(),
      ),
    );
    _explicitlyResolvedObjectIds.add(draft.inferenceObject.objectId);
    final drafts = [
      for (final value in _state.objectDrafts)
        value.inferenceObject.objectId == draft.inferenceObject.objectId
            ? ObjectDraft.accepted(
                inferenceObject: value.inferenceObject,
                product: product,
              )
            : value,
    ];
    final lines = _linesFor(drafts);
    await _auditStore.replaceDraftOrder(_requireSession(), lines);
    final allResolved = drafts.every((value) => value.isResolved);
    _replaceState(
      CheckoutState(
        phase: _state.phase == CheckoutPhase.orderReview || allResolved
            ? CheckoutPhase.orderReview
            : CheckoutPhase.customerReview,
        objectDrafts: drafts,
        lines: lines,
        capturedEvidencePath: _state.capturedEvidencePath,
        capturedEvidenceDisplayPath: _state.capturedEvidenceDisplayPath,
        capturedImageWidth: _state.capturedImageWidth,
        capturedImageHeight: _state.capturedImageHeight,
      ),
    );
  }

  Future<void> _publishEditedLines() async {
    final lines = _linesFor(_state.objectDrafts);
    await _persistLines(lines);
    _replaceState(
      CheckoutState(
        phase: CheckoutPhase.orderReview,
        objectDrafts: _state.objectDrafts,
        lines: lines,
        capturedEvidencePath: _state.capturedEvidencePath,
        capturedEvidenceDisplayPath: _state.capturedEvidenceDisplayPath,
        capturedImageWidth: _state.capturedImageWidth,
        capturedImageHeight: _state.capturedImageHeight,
      ),
    );
  }

  Future<void> _persistLines(List<CheckoutLine> lines) =>
      _auditStore.replaceDraftOrder(_requireSession(), lines);

  Future<void> _stageRecovery(
    _ScanRecovery recovery,
    ScannerCapture capture,
  ) async {
    recovery.capturedAt ??= _utcNow();
    final retained = await _evidenceStore.retainCapture(
      sessionId: recovery.sessionId,
      attemptNumber: recovery.attemptNumber,
      capturedAtUtc: recovery.capturedAt!,
      sourcePath: capture.path,
    );
    recovery.retainedCapture = retained;
    recovery.stagedAttempt = await _auditStore.stageAttempt(
      sessionId: recovery.sessionId,
      attemptNumber: recovery.attemptNumber,
      image: retained,
    );
  }

  Future<void> _completeAndPresent(_ScanRecovery recovery) async {
    final result = recovery.result ?? _scanner.state.result;
    final imageSize = recovery.imageSize ?? _scanner.state.capturedImageSize;
    final stagedAttempt = recovery.stagedAttempt;
    final capturedAt = recovery.capturedAt;
    if (result == null ||
        imageSize == null ||
        stagedAttempt == null ||
        capturedAt == null) {
      throw StateError('analysis completed without staged strict evidence');
    }
    recovery.result = result;
    recovery.imageSize = imageSize;
    final receipt = recovery.receipt ??= _createInferenceReceipt(result);
    if (!recovery.receiptRetained) {
      await _evidenceStore.retainInferenceReceipt(
        sessionId: recovery.sessionId,
        attemptNumber: recovery.attemptNumber,
        capturedAtUtc: capturedAt,
        receipt: receipt,
      );
      recovery.receiptRetained = true;
    }
    if (!recovery.attemptCompleted) {
      await _auditStore.completeAttempt(
        attempt: stagedAttempt,
        result: result,
        receipt: receipt,
      );
      recovery.attemptCompleted = true;
    }

    final mapping = recovery.mapping ??= await _mapper.map(
      result: result,
      imageSize: imageSize,
      catalog: _requireCatalog(),
    );
    _candidateProducts = mapping.candidateProducts;
    _explicitlyResolvedObjectIds.clear();
    _manualQuantities.clear();
    final lines = _linesFor(mapping.objectDrafts);
    await _auditStore.replaceDraftOrder(recovery.sessionId, lines);
    final retainedPath = recovery.retainedCapture?.path;
    final displayPath = retainedPath == null
        ? null
        : await _displayPathResolver.resolveForDisplay(retainedPath);
    await _scanner.releaseCurrentCapture();
    if (mapping.phase == CheckoutPhase.retakeRequired) {
      _failedAttempts += 1;
    }
    _scanRecovery = null;
    _replaceState(
      CheckoutState(
        phase: mapping.phase,
        objectDrafts: mapping.objectDrafts,
        lines: lines,
        failure: mapping.failure,
        capturedEvidencePath: retainedPath,
        capturedEvidenceDisplayPath: displayPath,
        capturedImageWidth: imageSize.width,
        capturedImageHeight: imageSize.height,
      ),
    );
  }

  Future<void> _prepareAndCommitFrozenPayment(
    FinalOrderDraft order,
    CheckoutState review,
  ) async {
    if (!_manualCartMode) {
      for (final draft in review.objectDrafts) {
        final object = draft.inferenceObject;
        if (object.isUnknown ||
            _explicitlyResolvedObjectIds.contains(object.objectId)) {
          continue;
        }
        await _auditStore.recordResolution(
          ObjectResolutionDraft(
            sessionId: order.sessionId,
            inferenceObject: object,
            product: draft.acceptedProduct!,
            source: CustomerResolutionSource.aiAutoCustomerAccepted,
            resolvedAt: order.createdAt,
          ),
        );
        _explicitlyResolvedObjectIds.add(object.objectId);
      }
    }
    await _auditStore.replaceDraftOrder(order.sessionId, order.lines);
    await _commitFrozenPayment(order, review);
  }

  Future<void> _commitFrozenPayment(
    FinalOrderDraft order,
    CheckoutState review,
  ) async {
    final receipt = await _paymentService.commit(order);
    _sessionActive = false;
    _frozenOrder = null;
    _frozenReviewState = null;
    _replaceState(
      CheckoutState(
        phase: CheckoutPhase.paymentComplete,
        objectDrafts: review.objectDrafts,
        lines: review.lines,
        paymentReceipt: receipt,
      ),
    );
  }

  void _publishPaymentFailure(CheckoutState review, Object error) {
    _replaceState(
      CheckoutState(
        phase: CheckoutPhase.recoverableFailure,
        objectDrafts: review.objectDrafts,
        lines: review.lines,
        failure: CheckoutFailure(
          code: 'payment_commit_failure',
          message: 'Payment could not be safely committed: $error',
          recoverable: true,
        ),
      ),
    );
  }

  List<CheckoutLine> _linesFor(List<ObjectDraft> drafts) {
    final products = <String, Product>{};
    final quantities = <String, int>{};
    for (final draft in drafts.where((draft) => draft.isResolved)) {
      final product = draft.acceptedProduct!;
      products[product.productId] = product;
      quantities.update(
        product.productId,
        (quantity) => quantity + 1,
        ifAbsent: () => 1,
      );
    }
    for (final entry in _manualQuantities.entries) {
      final product = _product(entry.key);
      products[entry.key] = product;
      quantities.update(
        entry.key,
        (quantity) => quantity + entry.value,
        ifAbsent: () => entry.value,
      );
    }
    final lines = [
      for (final entry in quantities.entries)
        CheckoutLine(product: products[entry.key]!, quantity: entry.value),
    ]..sort((left, right) => Product.customerSort(left.product, right.product));
    return List.unmodifiable(lines);
  }

  int _resolvedQuantity(String productId) => _state.objectDrafts
      .where((draft) => draft.acceptedProduct?.productId == productId)
      .length;

  ObjectDraft _draft(String objectId) {
    for (final draft in _state.objectDrafts) {
      if (draft.inferenceObject.objectId == objectId) return draft;
    }
    throw StateError('object does not belong to the customer-visible result');
  }

  Product _product(String productId) {
    for (final product in _requireCatalog().products) {
      if (product.productId == productId && product.active) return product;
    }
    throw StateError('product is not active in the session catalog');
  }

  Product? _productForRecognitionSku(int recognitionSkuId) {
    Product? match;
    for (final product in _requireCatalog().products) {
      if (!product.active || product.recognitionSkuId != recognitionSkuId) {
        continue;
      }
      if (match != null) {
        throw StateError(
          'session catalog maps recognition SKU $recognitionSkuId more than '
          'once',
        );
      }
      match = product;
    }
    return match;
  }

  CustomerResolutionSource _overrideSource(
    InferenceObject object,
    Product product,
  ) {
    final mappedProduct = object.skuId == null
        ? null
        : _productForRecognitionSku(object.skuId!);
    return mappedProduct?.productId == product.productId
        ? CustomerResolutionSource.aiAutoCustomerAccepted
        : CustomerResolutionSource.customerOverrodeAuto;
  }

  Future<void> _releaseCanceledCapture(StagedAttempt? stagedAttempt) async {
    if (stagedAttempt != null && _scanner.state.capturedImagePath != null) {
      await _scanner.releaseCurrentCapture();
    }
  }

  Future<void> _abandonActiveSession(String reason) async {
    final sessionId = _sessionId;
    if (!_sessionActive || sessionId == null) return;
    await _auditStore.abandonSession(sessionId, reason);
    _sessionActive = false;
  }

  Future<void> _terminalizeSessionStartFailure({
    required String code,
    required String abandonReason,
    required Object error,
  }) async {
    Object? abandonmentError;
    try {
      await _abandonActiveSession(abandonReason);
    } catch (caught) {
      abandonmentError = caught;
    }
    final suffix = abandonmentError == null
        ? ''
        : ' Session abandonment must be retried: $abandonmentError';
    _replaceState(
      _failureState(
        phase: CheckoutPhase.terminalFailure,
        code: code,
        message: 'Checkout session setup failed: $error.$suffix',
        recoverable: false,
      ),
    );
  }

  CheckoutState _emptyState(CheckoutPhase phase) =>
      CheckoutState(phase: phase, objectDrafts: const [], lines: const []);

  CheckoutState _failureState({
    required CheckoutPhase phase,
    required String code,
    required String message,
    required bool recoverable,
  }) => CheckoutState(
    phase: phase,
    objectDrafts: const [],
    lines: const [],
    failure: CheckoutFailure(
      code: code,
      message: message,
      recoverable: recoverable,
    ),
  );

  CatalogSnapshot _requireCatalog() {
    final catalog = _catalog;
    if (catalog == null) throw StateError('checkout catalog is unavailable');
    return catalog;
  }

  void _verifyDiscoverySnapshot(
    CatalogSnapshot catalog,
    CustomerCatalogDiscovery discovery,
  ) {
    final supplied = discovery.catalog;
    final sameRevision =
        supplied.revision.revisionId == catalog.revision.revisionId &&
        supplied.revision.sha256 == catalog.revision.sha256 &&
        supplied.revision.createdAt == catalog.revision.createdAt;
    final sameProducts =
        supplied.products.length == catalog.products.length &&
        supplied.products.every(
          (product) => catalog.products.any(
            (expected) =>
                expected.productId == product.productId &&
                expected.displayName == product.displayName &&
                expected.unitPrice == product.unitPrice &&
                expected.recognitionSkuId == product.recognitionSkuId &&
                expected.categoryId == product.categoryId &&
                expected.photoAssetPath == product.photoAssetPath &&
                expected.active == product.active &&
                expected.sortOrder == product.sortOrder,
          ),
        );
    final validFeaturedProducts = discovery.featuredProducts.every(
      (featured) => supplied.products.any(
        (product) => product.productId == featured.productId,
      ),
    );
    if (!sameRevision || !sameProducts || !validFeaturedProducts) {
      throw StateError('catalog discovery does not match the session snapshot');
    }
  }

  String _requireSession() {
    final sessionId = _sessionId;
    if (!_sessionActive || sessionId == null) {
      throw StateError('checkout session is not active');
    }
    return sessionId;
  }

  DateTime _utcNow() => _now().toUtc();

  void _ensurePhase(CheckoutPhase phase, String command) {
    _ensureInitialized();
    if (_state.phase != phase) {
      throw StateError('$command is illegal from ${_state.phase.name}');
    }
  }

  void _ensureInitialized() {
    _ensureOpen();
    if (!_initialized) {
      throw StateError('checkout controller is not initialized');
    }
  }

  void _ensureOpen() {
    if (_closed) throw StateError('checkout controller is closed');
  }

  void _replaceState(CheckoutState next) {
    if (_closed) return;
    _state = next;
    notifyListeners();
  }
}

final class _FallbackPaymentIds {
  static int _next = 0;
  static String next(String prefix) => '$prefix-local-${++_next}';
}
