// ignore_for_file: prefer_initializing_formals

import 'package:flutter/foundation.dart';

import '../catalog/product.dart';
import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'checkout_models.dart';
import 'checkout_ports.dart';
import 'checkout_state.dart';
import 'inference_checkout_mapper.dart';

typedef CheckoutClock = DateTime Function();
typedef InferenceReceiptFactory =
    ImmutableJsonReceipt Function(InferenceResult result);

final class CheckoutController extends ChangeNotifier {
  CheckoutController({
    required ScannerController scanner,
    required CheckoutAuditStore auditStore,
    required CheckoutEvidenceStore evidenceStore,
    required CatalogRepository catalogRepository,
    required InferenceReceiptFactory createInferenceReceipt,
    CheckoutClock? now,
  }) : _scanner = scanner,
       _auditStore = auditStore,
       _evidenceStore = evidenceStore,
       _catalogRepository = catalogRepository,
       _mapper = InferenceCheckoutMapper(catalogRepository),
       _createInferenceReceipt = createInferenceReceipt,
       _now = now ?? DateTime.now;

  final ScannerController _scanner;
  final CheckoutAuditStore _auditStore;
  final CheckoutEvidenceStore _evidenceStore;
  final CatalogRepository _catalogRepository;
  final InferenceCheckoutMapper _mapper;
  final InferenceReceiptFactory _createInferenceReceipt;
  final CheckoutClock _now;

  CheckoutState _state = CheckoutState(
    phase: CheckoutPhase.ready,
    objectDrafts: const [],
    lines: const [],
  );
  List<InterruptedCheckout> _interruptedCheckouts = const [];
  CatalogSnapshot? _catalog;
  String? _sessionId;
  int? _retryLimit;
  int _attemptNumber = 0;
  int _failedAttempts = 0;
  int _scanGeneration = 0;
  bool _initialized = false;
  bool _closed = false;
  bool _sessionActive = false;
  bool _manualCartMode = false;
  Map<String, Map<int, Product?>> _candidateProducts = const {};
  final Set<String> _explicitlyResolvedObjectIds = {};
  final Map<String, int> _manualQuantities = {};

  CheckoutState get state => _state;
  List<InterruptedCheckout> get interruptedCheckouts => _interruptedCheckouts;
  bool get manualCartEligible =>
      _state.phase == CheckoutPhase.retakeRequired &&
      _retryLimit != null &&
      _failedAttempts > _retryLimit!;
  Map<int, int> get inferenceTotals =>
      Map.unmodifiable(_scanner.state.result?.counts ?? const {});
  int get unknownInferenceTotal => _scanner.state.result?.unknownCount ?? 0;

  Product? productForCandidate(String objectId, int recognitionSkuId) =>
      _candidateProducts[objectId]?[recognitionSkuId];

  Future<void> initialize() async {
    _ensureOpen();
    if (_initialized) {
      throw StateError('checkout controller can only be initialized once');
    }
    _initialized = true;
    try {
      _interruptedCheckouts = List.unmodifiable(
        await _auditStore.interruptNonterminalSessions(_utcNow()),
      );
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
      await _abandonActiveSession('checkout_initialization_failure');
      _replaceState(
        _failureState(
          phase: CheckoutPhase.terminalFailure,
          code: 'checkout_initialization_failure',
          message: 'Checkout initialization failed: $error',
          recoverable: false,
        ),
      );
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
    StagedAttempt? stagedAttempt;
    DateTime? capturedAt;
    _replaceState(_emptyState(CheckoutPhase.analyzing));

    try {
      await _scanner.analyze(
        beforeInference: (capture) async {
          capturedAt = _utcNow();
          final retained = await _evidenceStore.retainCapture(
            sessionId: sessionId,
            attemptNumber: attemptNumber,
            capturedAtUtc: capturedAt!,
            sourcePath: capture.path,
          );
          stagedAttempt = await _auditStore.stageAttempt(
            sessionId: sessionId,
            attemptNumber: attemptNumber,
            image: retained,
          );
        },
      );
      if (generation != _scanGeneration) {
        await _releaseCanceledCapture(stagedAttempt);
        return;
      }
      final result = _scanner.state.result;
      final imageSize = _scanner.state.capturedImageSize;
      if (result == null ||
          imageSize == null ||
          stagedAttempt == null ||
          capturedAt == null) {
        throw StateError('analysis completed without staged strict evidence');
      }

      final receipt = _createInferenceReceipt(result);
      await _evidenceStore.retainInferenceReceipt(
        sessionId: sessionId,
        attemptNumber: attemptNumber,
        capturedAtUtc: capturedAt!,
        receipt: receipt,
      );
      await _auditStore.completeAttempt(
        attempt: stagedAttempt!,
        result: result,
        receipt: receipt,
      );
      await _scanner.releaseCurrentCapture();

      final mapping = await _mapper.map(result: result, imageSize: imageSize);
      _candidateProducts = mapping.candidateProducts;
      _explicitlyResolvedObjectIds.clear();
      _manualQuantities.clear();
      _manualCartMode = false;
      final lines = _linesFor(mapping.objectDrafts);
      await _auditStore.replaceDraftOrder(sessionId, lines);
      if (mapping.phase == CheckoutPhase.retakeRequired) {
        _failedAttempts += 1;
      }
      _replaceState(
        CheckoutState(
          phase: mapping.phase,
          objectDrafts: mapping.objectDrafts,
          lines: lines,
          failure: mapping.failure,
        ),
      );
    } catch (error) {
      if (generation != _scanGeneration) {
        await _releaseCanceledCapture(stagedAttempt);
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
    _scanGeneration += 1;
    await _abandonActiveSession('customer_cancelled_analysis');
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

  Future<void> enterManualCart() async {
    _ensurePhase(CheckoutPhase.retakeRequired, 'manual cart');
    if (!manualCartEligible) {
      throw StateError('manual cart requires exhausted retries');
    }
    final sessionId = _requireSession();
    await _auditStore.enterManualCartMode(sessionId, _utcNow());
    _manualCartMode = true;
    _candidateProducts = const {};
    _explicitlyResolvedObjectIds.clear();
    _manualQuantities.clear();
    await _auditStore.replaceDraftOrder(sessionId, const []);
    _replaceState(_emptyState(CheckoutPhase.orderReview));
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
    final source = draft.inferenceObject.isUnknown
        ? CustomerResolutionSource.customerCatalog
        : product.recognitionSkuId == draft.inferenceObject.skuId
        ? CustomerResolutionSource.aiAutoCustomerAccepted
        : CustomerResolutionSource.customerOverrodeAuto;
    await _resolve(draft: draft, product: product, source: source);
  }

  Future<void> acceptAiSelection(String objectId) async {
    _ensurePhase(CheckoutPhase.customerReview, 'AI selection');
    final draft = _draft(objectId);
    final object = draft.inferenceObject;
    if (object.isUnknown) {
      throw StateError('Unknown objects have no AI selection to accept');
    }
    final product = await _catalogRepository.productForRecognitionSku(
      object.skuId!,
    );
    if (product == null) {
      throw StateError('AI selection has no active catalog product');
    }
    await _resolve(
      draft: draft,
      product: product,
      source: CustomerResolutionSource.aiAutoCustomerAccepted,
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
    _replaceState(
      CheckoutState(
        phase: CheckoutPhase.paying,
        objectDrafts: prior.objectDrafts,
        lines: prior.lines,
      ),
    );
    try {
      if (!_manualCartMode) {
        for (final draft in prior.objectDrafts) {
          final object = draft.inferenceObject;
          if (object.isUnknown ||
              _explicitlyResolvedObjectIds.contains(object.objectId)) {
            continue;
          }
          await _auditStore.recordResolution(
            ObjectResolutionDraft(
              sessionId: _requireSession(),
              inferenceObject: object,
              product: draft.acceptedProduct!,
              source: CustomerResolutionSource.aiAutoCustomerAccepted,
              resolvedAt: _utcNow(),
            ),
          );
        }
      }
      await _persistLines(prior.lines);
      final order = FinalOrderDraft(
        sessionId: _requireSession(),
        catalogRevision: _requireCatalog().revision,
        lines: prior.lines,
        createdAt: _utcNow(),
      );
      final receipt = await _auditStore.commitSimulatedPayment(order);
      _sessionActive = false;
      _replaceState(
        CheckoutState(
          phase: CheckoutPhase.paymentComplete,
          objectDrafts: prior.objectDrafts,
          lines: prior.lines,
          paymentReceipt: receipt,
        ),
      );
    } catch (error) {
      _replaceState(
        CheckoutState(
          phase: CheckoutPhase.recoverableFailure,
          objectDrafts: const [],
          lines: const [],
          failure: CheckoutFailure(
            code: 'payment_commit_failure',
            message: 'Payment could not be safely committed: $error',
            recoverable: true,
          ),
        ),
      );
    }
  }

  Future<void> startNextCustomer() async {
    if (_state.phase != CheckoutPhase.paymentComplete &&
        _state.phase != CheckoutPhase.terminalFailure) {
      throw StateError('next customer requires a terminal checkout');
    }
    await _scanner.resetCapture();
    await _beginSession();
    _replaceState(_emptyState(CheckoutPhase.ready));
  }

  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    await _abandonActiveSession('controller_closed');
    await _scanner.close();
  }

  Future<void> _beginSession() async {
    final catalog = await _catalogRepository.activeCatalog();
    final sessionId = await _auditStore.beginSession(
      SessionSnapshot(
        sessionStartedAt: _utcNow(),
        catalogRevision: catalog.revision,
      ),
    );
    final retryLimit = await _auditStore.retryLimitForSession(sessionId);
    if (retryLimit < 0) {
      throw StateError('session retry limit must be non-negative');
    }
    _catalog = catalog;
    _sessionId = sessionId;
    _retryLimit = retryLimit;
    _attemptNumber = 0;
    _failedAttempts = 0;
    _sessionActive = true;
    _manualCartMode = false;
    _candidateProducts = const {};
    _explicitlyResolvedObjectIds.clear();
    _manualQuantities.clear();
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
    _replaceState(
      CheckoutState(
        phase: CheckoutPhase.customerReview,
        objectDrafts: drafts,
        lines: lines,
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
      ),
    );
  }

  Future<void> _persistLines(List<CheckoutLine> lines) =>
      _auditStore.replaceDraftOrder(_requireSession(), lines);

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

  Future<void> _releaseCanceledCapture(StagedAttempt? stagedAttempt) async {
    if (stagedAttempt != null && _scanner.state.capturedImagePath != null) {
      await _scanner.releaseCurrentCapture();
    }
  }

  Future<void> _abandonActiveSession(String reason) async {
    final sessionId = _sessionId;
    if (!_sessionActive || sessionId == null) return;
    _sessionActive = false;
    await _auditStore.abandonSession(sessionId, reason);
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
