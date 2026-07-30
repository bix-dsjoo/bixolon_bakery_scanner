import 'dart:async';

import 'package:bakery_camera_prototype/src/camera/camera_service.dart';
import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_controller.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_ports.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:camera/camera.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  late List<String> events;
  late _FakeCamera camera;
  late _FakeWorker worker;
  late ScannerController scanner;
  late _FakeAuditStore audit;
  late _FakeEvidenceStore evidence;
  late _FakeCatalog catalog;
  late CheckoutController controller;

  setUp(() {
    events = [];
    camera = _FakeCamera(events);
    worker = _FakeWorker(events);
    scanner = ScannerController(
      camera: camera,
      worker: worker,
      readImageSize: (_) async =>
          const CapturedImageSize(width: 1920, height: 1080),
    );
    audit = _FakeAuditStore(events);
    evidence = _FakeEvidenceStore(events);
    catalog = _FakeCatalog();
    controller = CheckoutController(
      scanner: scanner,
      auditStore: audit,
      evidenceStore: evidence,
      displayPathResolver: const _DisplayPathResolver(),
      catalogRepository: catalog,
      createInferenceReceipt: (_) => const ImmutableJsonReceipt(
        canonicalJson: '{"receipt":"strict"}',
        sha256:
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      ),
      now: () => DateTime.utc(2026, 7, 30, 8),
    );
  });

  tearDown(() async {
    await controller.close();
  });

  test(
    'empty or unsafe scan requires retake and exposes no candidates',
    () async {
      worker.nextResult = _emptyResult();
      await controller.initialize();

      await controller.scan();

      expect(controller.state.phase, CheckoutPhase.retakeRequired);
      expect(controller.state.objectDrafts, isEmpty);
      expect(controller.state.lines, isEmpty);
      expect(controller.state.failure!.code, 'no_bread_detected');
    },
  );

  test('unknown scan enters review with exact Top 3', () async {
    final resultWithOneUnknown = buildUiInferenceResult();
    worker.nextResult = resultWithOneUnknown;
    await controller.initialize();

    await controller.scan();

    expect(
      controller.state.phase,
      CheckoutPhase.customerReview,
      reason: controller.state.failure?.message,
    );
    expect(
      controller.state.activeObject!.candidates,
      resultWithOneUnknown.objects.last.candidates,
    );
    expect(
      controller.productForCandidate('object-2', 10)?.productId,
      'product-donut',
    );
    expect(controller.productForCandidate('object-2', 12), isNull);
    expect(
      controller.state.capturedEvidencePath,
      'sessions/capture-1.jpg',
      reason: 'customer review uses the already-retained audit still only',
    );
    expect(
      controller.state.capturedEvidenceDisplayPath,
      r'C:\audit-root\sessions\capture-1.jpg',
      reason:
          'the persisted reference remains relative while the UI receives a safe local path',
    );
    expect(controller.state.capturedImageWidth, 1920);
    expect(controller.state.capturedImageHeight, 1080);
  });

  test(
    'completion behavior is loaded once from the session settings snapshot',
    () async {
      await controller.initialize();

      expect(controller.completionPolicy.duration, const Duration(seconds: 4));
      expect(controller.completionPolicy.autoReset, isTrue);
    },
  );

  test('admin entry abandons only an active unfinished session', () async {
    await controller.initialize();

    expect(controller.hasActiveCustomerCheckout, isTrue);
    await controller.abandonForAdminEntry();

    expect(controller.hasActiveCustomerCheckout, isFalse);
    expect(audit.abandonReasons, ['admin_mode_entered']);
    await expectLater(controller.abandonForAdminEntry(), throwsStateError);
  });

  test(
    'admin exit starts a fresh session after an audited abandonment',
    () async {
      await controller.initialize();
      await controller.abandonForAdminEntry();

      await controller.startFreshCustomerSession();

      expect(controller.hasActiveCustomerCheckout, isTrue);
      expect(controller.state.phase, CheckoutPhase.ready);
      expect(audit.begunSessionIds, hasLength(2));
    },
  );

  test(
    'all mapped registered detections go directly to editable order review',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();

      await controller.scan();

      expect(controller.state.phase, CheckoutPhase.orderReview);
      expect(
        controller.state.objectDrafts.every((object) => object.product != null),
        isTrue,
      );
      expect(controller.state.lines.single.quantity, 1);
      expect(audit.resolutions, isEmpty);
      expect(controller.inferenceTotals, {6: 1});
    },
  );

  test('capture and attempt persist before inference and receipt before '
      'presentation', () async {
    worker.nextResult = _registeredResult();
    audit.completeGate = Completer<void>();
    await controller.initialize();

    final scan = controller.scan();
    await audit.completeCalled.future;

    expect(events.skip(events.indexOf('capture')).take(4), [
      'capture',
      'retain_capture',
      'stage',
      'worker',
    ]);
    expect(events, containsAllInOrder(['retain_receipt', 'complete']));
    expect(controller.state.phase, CheckoutPhase.analyzing);
    expect(camera.releasedPaths, isEmpty);

    audit.completeGate!.complete();
    await scan;

    expect(events, containsAllInOrder(['complete', 'release']));
    expect(controller.state.phase, CheckoutPhase.orderReview);
  });

  test('capture persistence failure stops before worker inference', () async {
    evidence.captureError = StateError('disk full');
    await controller.initialize();

    await controller.scan();

    expect(worker.analyzeCalls, 0);
    expect(controller.state.phase, CheckoutPhase.recoverableFailure);
    expect(controller.state.objectDrafts, isEmpty);
    expect(camera.releasedPaths, isEmpty);
  });

  test(
    'receipt persistence failure presents no customer resolution and retains '
    'capture',
    () async {
      evidence.receiptError = StateError('receipt fsync failed');
      worker.nextResult = _registeredResult();
      await controller.initialize();

      await controller.scan();

      expect(controller.state.phase, CheckoutPhase.recoverableFailure);
      expect(controller.state.objectDrafts, isEmpty);
      expect(audit.completedAttempts, isEmpty);
      expect(camera.releasedPaths, isEmpty);
      expect(scanner.state.result, same(worker.nextResult));
    },
  );

  test(
    'registered SKU without mapping stays unresolved and records a catalog choice',
    () async {
      catalog.productsBySku.remove(6);
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();

      expect(controller.state.phase, CheckoutPhase.customerReview);
      expect(controller.state.activeObject!.requiresCatalogSelection, isTrue);

      await controller.chooseCatalog('object-1', 'product-donut');
      await controller.continueToOrderReview();

      expect(
        audit.resolutions.single.source,
        CustomerResolutionSource.customerCatalog,
      );
      expect(controller.state.phase, CheckoutPhase.orderReview);
    },
  );

  test(
    'session catalog discovery search and selected product stay on the initial revision',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      catalog.activateRevision(
        revisionId: 'catalog-v2',
        products: [_product('product-v2-only', 'Revision Two Only', 17)],
      );

      expect(
        controller.customerCatalogDiscovery.catalog.revision.revisionId,
        'catalog-v1',
      );
      expect(
        controller.customerCatalogDiscovery.featuredProducts.map(
          (product) => product.productId,
        ),
        contains('product-donut'),
      );
      expect(
        (await controller.searchSessionCatalog(
          'Donut',
        )).map((product) => product.productId),
        contains('product-donut'),
      );
      expect(
        (await controller.searchSessionCatalog('Revision Two Only')),
        isEmpty,
      );

      await controller.scan();
      await controller.overrideResolvedProduct('object-1', 'product-donut');

      expect(audit.resolutions.single.product.displayName, 'Sugar Donut');
      expect(
        audit.resolutions.single.source,
        CustomerResolutionSource.customerOverrodeAuto,
      );
    },
  );

  test('Top 3 choices preserve history and exact customer source', () async {
    worker.nextResult = buildUiInferenceResult();
    await controller.initialize();
    await controller.scan();

    await controller.chooseTop3('object-2', 10);
    await controller.chooseTop3('object-2', 11);

    expect(audit.resolutions, hasLength(2));
    expect(
      audit.resolutions.map((value) => value.source),
      everyElement(CustomerResolutionSource.customerTop3),
    );
    expect(audit.resolutions.map((value) => value.product.productId), [
      'product-donut',
      'product-cream-donut',
    ]);
    expect(controller.state.activeObject, isNull);
  });

  test(
    'unchanged registered objects become AI accepted only when payment freezes',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();

      expect(audit.resolutions, isEmpty);
      await controller.pay();

      expect(audit.resolutions, hasLength(1));
      expect(
        audit.resolutions.single.source,
        CustomerResolutionSource.aiAutoCustomerAccepted,
      );
      expect(controller.state.phase, CheckoutPhase.paymentComplete);
    },
  );

  test(
    'retry exhaustion enters explicit manual cart and keeps lines unlinked',
    () async {
      audit.retryLimit = 1;
      worker.nextResult = _emptyResult();
      await controller.initialize();
      await controller.scan();
      expect(controller.manualCartEligible, isFalse);

      await controller.retake();
      worker.nextResult = _emptyResult(requestId: 'analysis-2');
      await controller.scan();

      expect(controller.manualCartEligible, isTrue);
      await controller.enterManualCart();
      await controller.addManualProduct('product-donut');
      await expectLater(controller.reportCountMismatch(), throwsStateError);
      await controller.pay();

      expect(audit.manualCartEntries, 1);
      expect(audit.resolutions, isEmpty);
      expect(audit.committedOrder!.lines.single.quantity, 1);
      expect(controller.state.phase, CheckoutPhase.paymentComplete);
    },
  );

  test(
    'manual cart entry failure is session absorbing and retries idempotently',
    () async {
      audit.retryLimit = 0;
      worker.nextResult = _emptyResult();
      await controller.initialize();
      await controller.scan();
      audit.draftFailuresRemaining = 1;

      await controller.enterManualCart();

      expect(controller.state.phase, CheckoutPhase.recoverableFailure);
      expect(controller.state.failure!.code, 'manual_cart_entry_failure');
      expect(audit.manualCartEntries, 1);
      await expectLater(controller.retake(), throwsStateError);

      await controller.retryFailure();
      await controller.addManualProduct('product-donut');

      expect(audit.manualCartEntries, 1);
      expect(controller.state.phase, CheckoutPhase.orderReview);
      expect(controller.state.lines.single.quantity, 1);
    },
  );

  test(
    'count mismatch discards product output and returns to retake',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();

      await controller.reportCountMismatch();

      expect(controller.state.phase, CheckoutPhase.retakeRequired);
      expect(controller.state.objectDrafts, isEmpty);
      expect(controller.state.lines, isEmpty);
      expect(controller.state.failure!.code, 'customer_count_mismatch');
    },
  );

  test(
    'analysis cancellation abandons session and ignores late result',
    () async {
      worker.nextResult = _registeredResult();
      worker.analysisGate = Completer<void>();
      await controller.initialize();
      final scan = controller.scan();
      await worker.analysisStarted.future;

      await controller.cancelScan();
      expect(audit.abandonReasons, ['customer_cancelled_analysis']);
      expect(controller.state.phase, CheckoutPhase.terminalFailure);

      worker.analysisGate!.complete();
      await scan;

      expect(audit.completedAttempts, isEmpty);
      expect(camera.releasedPaths, [camera.capture.path]);
      expect(controller.state.objectDrafts, isEmpty);
    },
  );

  test('failed cancellation retains identity and can be retried', () async {
    worker.nextResult = _registeredResult();
    worker.analysisGate = Completer<void>();
    audit.abandonFailuresRemaining = 1;
    await controller.initialize();
    final scan = controller.scan();
    await worker.analysisStarted.future;

    await controller.cancelScan();

    expect(controller.state.phase, CheckoutPhase.analyzing);
    expect(controller.state.failure!.code, 'cancellation_persistence_failure');
    expect(audit.abandonAttempts, 1);

    await controller.cancelScan();

    expect(audit.abandonAttempts, 2);
    expect(controller.state.phase, CheckoutPhase.terminalFailure);
    worker.analysisGate!.complete();
    await scan;
  });

  test(
    'failed admin abandonment during analysis leaves the active scan able to finish',
    () async {
      worker.nextResult = _registeredResult();
      worker.analysisGate = Completer<void>();
      await controller.initialize();
      final scan = controller.scan();
      await worker.analysisStarted.future;
      audit.abandonFailuresRemaining = 1;

      await expectLater(controller.abandonForAdminEntry(), throwsStateError);

      expect(controller.hasActiveCustomerCheckout, isTrue);
      expect(controller.state.phase, CheckoutPhase.analyzing);

      worker.analysisGate!.complete();
      await scan;

      expect(controller.state.phase, CheckoutPhase.orderReview);
      expect(audit.completedAttempts, hasLength(1));
    },
  );

  test('camera and worker startup failures are terminal', () async {
    camera.initializeResult = false;

    await controller.initialize();

    expect(controller.state.phase, CheckoutPhase.terminalFailure);
    expect(audit.abandonReasons, ['scanner_startup_failure']);
  });

  test(
    'cold start interrupts old sessions before beginning a new one',
    () async {
      audit.interrupted = [
        InterruptedCheckout(
          sessionId: 'old-session',
          interruptedAt: DateTime.utc(2026, 7, 30, 7, 59),
        ),
      ];

      await controller.initialize();

      expect(events.indexOf('interrupt'), lessThan(events.indexOf('begin')));
      expect(controller.interruptedCheckouts, audit.interrupted);
      expect(controller.state.phase, CheckoutPhase.ready);
    },
  );

  test('retry snapshot failure abandons the durably begun session', () async {
    audit.retryError = StateError('settings snapshot unavailable');

    await controller.initialize();

    expect(audit.abandonReasons, ['checkout_initialization_failure']);
    expect(controller.state.phase, CheckoutPhase.terminalFailure);
  });

  test(
    'next customer retry snapshot failure terminalizes and can start again',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();
      await controller.pay();
      final completedSessionId = audit.begunSessionIds.single;
      audit.retryError = StateError('settings snapshot unavailable');

      await controller.startNextCustomer();

      final failedSessionId = audit.begunSessionIds.last;
      expect(failedSessionId, isNot(completedSessionId));
      expect(controller.state.phase, CheckoutPhase.terminalFailure);
      expect(controller.state.failure!.code, 'checkout_session_start_failure');
      expect(audit.abandonedSessionIds, [failedSessionId]);

      audit.retryError = null;
      await controller.startNextCustomer();

      expect(audit.begunSessionIds, hasLength(3));
      expect(controller.state.phase, CheckoutPhase.ready);
    },
  );

  test(
    'next customer startup is single flight before a durable session begins',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();
      await controller.pay();
      audit.beginSessionGate = Completer<void>();
      audit.beginSessionBlocked = Completer<void>();

      final first = controller.startNextCustomer();
      await audit.beginSessionBlocked!.future;
      final second = controller.startNextCustomer();
      final secondResult = expectLater(second, throwsStateError);
      await Future<void>.delayed(Duration.zero);
      audit.retryError = StateError('settings snapshot unavailable');
      audit.beginSessionGate!.complete();

      await first;
      await secondResult;

      expect(audit.beginCalls, 2);
      expect(audit.begunSessionIds, hasLength(2));
      final failedSessionId = audit.begunSessionIds.last;
      expect(audit.abandonedSessionIds, [failedSessionId]);
      expect(controller.state.phase, CheckoutPhase.terminalFailure);
    },
  );

  test(
    'close waits for a session blocked before durable begin and abandons it',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();
      await controller.pay();
      final publishedPhases = <CheckoutPhase>[];
      controller.addListener(() => publishedPhases.add(controller.state.phase));
      audit.beginSessionGate = Completer<void>();
      audit.beginSessionBlocked = Completer<void>();

      final startup = controller.startNextCustomer();
      await audit.beginSessionBlocked!.future;
      var closeReturned = false;
      final closing = controller.close().then((_) => closeReturned = true);
      await Future<void>.delayed(Duration.zero);
      final closeWaitedForStartup = !closeReturned;
      audit.beginSessionGate!.complete();

      await startup;
      await closing;

      expect(closeWaitedForStartup, isTrue);
      expect(publishedPhases, isNot(contains(CheckoutPhase.ready)));
      expect(audit.begunSessionIds, hasLength(2));
      expect(audit.abandonedSessionIds, [audit.begunSessionIds.last]);
    },
  );

  test(
    'close waits after durable begin and before retry lookup completes',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();
      await controller.pay();
      final publishedPhases = <CheckoutPhase>[];
      controller.addListener(() => publishedPhases.add(controller.state.phase));
      audit.retryLimitGate = Completer<void>();
      audit.retryLimitBlocked = Completer<void>();

      final startup = controller.startNextCustomer();
      await audit.retryLimitBlocked!.future;
      final startedSessionId = audit.begunSessionIds.last;
      var closeReturned = false;
      final closing = controller.close().then((_) => closeReturned = true);
      await Future<void>.delayed(Duration.zero);
      final closeWaitedForStartup = !closeReturned;
      audit.retryLimitGate!.complete();

      await startup;
      await closing;

      expect(closeWaitedForStartup, isTrue);
      expect(publishedPhases, isNot(contains(CheckoutPhase.ready)));
      expect(audit.abandonedSessionIds, [startedSessionId]);
    },
  );

  test('storage failure can retry the same retained capture', () async {
    evidence.captureError = StateError('temporary storage failure');
    worker.nextResult = _registeredResult();
    await controller.initialize();
    await controller.scan();
    expect(controller.state.phase, CheckoutPhase.recoverableFailure);
    expect(worker.analyzeCalls, 0);

    evidence.captureError = null;
    await controller.retryFailure();

    expect(worker.analyzeCalls, 1);
    expect(audit.completedAttempts, hasLength(1));
    expect(controller.state.phase, CheckoutPhase.orderReview);
  });

  test(
    'draft persistence failure retries mapped result before releasing capture',
    () async {
      audit.draftFailuresRemaining = 1;
      worker.nextResult = _registeredResult();
      await controller.initialize();

      await controller.scan();

      expect(controller.state.phase, CheckoutPhase.recoverableFailure);
      expect(camera.releasedPaths, isEmpty);
      expect(audit.completedAttempts, hasLength(1));

      await controller.retryFailure();

      expect(controller.state.phase, CheckoutPhase.orderReview);
      expect(controller.state.lines, hasLength(1));
      expect(camera.releasedPaths, [camera.capture.path]);
      expect(audit.completedAttempts, hasLength(1));
    },
  );

  test(
    'payment failure retains frozen order and retries idempotently',
    () async {
      worker.nextResult = _registeredResult();
      audit.paymentFailuresRemaining = 1;
      await controller.initialize();
      await controller.scan();

      await controller.pay();

      expect(controller.state.phase, CheckoutPhase.recoverableFailure);
      expect(controller.state.lines, hasLength(1));
      final frozen = audit.committedOrders.single;

      await controller.retryFailure();

      expect(controller.state.phase, CheckoutPhase.paymentComplete);
      expect(audit.committedOrders, hasLength(2));
      expect(audit.committedOrders.last, same(frozen));
      expect(audit.resolutions, hasLength(1));
    },
  );

  test('automatic resolution failure retries the pre-frozen order', () async {
    worker.nextResult = _registeredResult();
    audit.resolutionFailuresRemaining = 1;
    await controller.initialize();
    await controller.scan();

    await controller.pay();

    expect(controller.state.phase, CheckoutPhase.recoverableFailure);
    expect(audit.committedOrders, isEmpty);

    await controller.retryFailure();

    expect(controller.state.phase, CheckoutPhase.paymentComplete);
    expect(audit.resolutionAttempts, 2);
    expect(audit.resolutions, hasLength(1));
    expect(audit.committedOrders, hasLength(1));
  });

  test(
    'payment draft failure retries without duplicating automatic resolution',
    () async {
      worker.nextResult = _registeredResult();
      await controller.initialize();
      await controller.scan();
      audit.draftFailuresRemaining = 1;

      await controller.pay();

      expect(controller.state.phase, CheckoutPhase.recoverableFailure);
      expect(audit.resolutions, hasLength(1));
      expect(audit.committedOrders, isEmpty);

      await controller.retryFailure();

      expect(controller.state.phase, CheckoutPhase.paymentComplete);
      expect(audit.resolutions, hasLength(1));
      expect(audit.committedOrders, hasLength(1));
    },
  );

  test('mapping and candidates use the session catalog snapshot', () async {
    final sessionCroissant = catalog.productsBySku[6]!;
    final sessionDonut = catalog.productsBySku[10]!;
    worker.nextResult = buildUiInferenceResult();
    await controller.initialize();

    catalog.productsBySku
      ..remove(10)
      ..[6] = _product('replacement-croissant', 'Replacement', 6);
    await controller.scan();

    expect(
      controller.state.objectDrafts.first.acceptedProduct,
      same(sessionCroissant),
    );
    expect(controller.productForCandidate('object-2', 10), same(sessionDonut));
    await controller.chooseTop3('object-2', 10);
    expect(audit.resolutions.single.product, same(sessionDonut));
  });

  test(
    'scan and payment commands are single flight and phase guarded',
    () async {
      await expectLater(controller.scan(), throwsStateError);
      await controller.initialize();
      worker.nextResult = _registeredResult();
      worker.analysisGate = Completer<void>();
      final scan = controller.scan();
      await worker.analysisStarted.future;
      await expectLater(controller.scan(), throwsStateError);
      worker.analysisGate!.complete();
      await scan;

      audit.paymentGate = Completer<void>();
      final payment = controller.pay();
      await audit.paymentCalled.future;
      await expectLater(controller.pay(), throwsStateError);
      audit.paymentGate!.complete();
      await payment;
    },
  );

  test('illegal transitions fail without persistence side effects', () async {
    await controller.initialize();

    await expectLater(controller.pay(), throwsStateError);
    await expectLater(controller.retake(), throwsStateError);
    await expectLater(controller.enterManualCart(), throwsStateError);
    await expectLater(
      controller.chooseCatalog('missing', 'product-donut'),
      throwsStateError,
    );

    expect(audit.resolutions, isEmpty);
    expect(audit.manualCartEntries, 0);
    expect(audit.committedOrder, isNull);
  });
}

final class _FakeAuditStore implements CheckoutAuditStore {
  _FakeAuditStore(this.events);

  final List<String> events;
  List<InterruptedCheckout> interrupted = [];
  int retryLimit = 2;
  Object? retryError;
  Completer<void>? retryLimitGate;
  Completer<void>? retryLimitBlocked;
  final List<String> begunSessionIds = [];
  int beginCalls = 0;
  Completer<void>? beginSessionGate;
  Completer<void>? beginSessionBlocked;
  int manualCartEntries = 0;
  final List<ObjectResolutionDraft> resolutions = [];
  int resolutionAttempts = 0;
  int resolutionFailuresRemaining = 0;
  final List<PersistedAttempt> completedAttempts = [];
  final List<String> abandonReasons = [];
  final List<String> abandonedSessionIds = [];
  int abandonAttempts = 0;
  int abandonFailuresRemaining = 0;
  int draftFailuresRemaining = 0;
  int paymentFailuresRemaining = 0;
  List<CheckoutLine> draftLines = [];
  FinalOrderDraft? committedOrder;
  final List<FinalOrderDraft> committedOrders = [];
  Completer<void>? completeGate;
  Completer<void>? paymentGate;
  final completeCalled = Completer<void>();
  final paymentCalled = Completer<void>();

  @override
  Future<List<InterruptedCheckout>> interruptNonterminalSessions(
    DateTime detectedAt,
  ) async {
    events.add('interrupt');
    return interrupted;
  }

  @override
  Future<String> beginSession(SessionSnapshot snapshot) async {
    events.add('begin');
    beginCalls += 1;
    final blocked = beginSessionBlocked;
    if (blocked != null && !blocked.isCompleted) {
      blocked.complete();
    }
    await beginSessionGate?.future;
    final sessionId =
        '00000000-0000-4000-8000-${(begunSessionIds.length + 1).toString().padLeft(12, '0')}';
    begunSessionIds.add(sessionId);
    return sessionId;
  }

  @override
  Future<int> retryLimitForSession(String sessionId) async {
    final blocked = retryLimitBlocked;
    if (blocked != null && !blocked.isCompleted) {
      blocked.complete();
    }
    await retryLimitGate?.future;
    final error = retryError;
    if (error != null) throw error;
    return retryLimit;
  }

  @override
  Future<CustomerCompletionPolicy> completionPolicyForSession(
    String sessionId,
  ) async => const CustomerCompletionPolicy(
    duration: Duration(seconds: 4),
    autoReset: true,
  );

  @override
  Future<void> enterManualCartMode(String sessionId, DateTime enteredAt) async {
    manualCartEntries += 1;
  }

  @override
  Future<StagedAttempt> stageAttempt({
    required String sessionId,
    required int attemptNumber,
    required CapturedAuditFile image,
  }) async {
    events.add('stage');
    return StagedAttempt(
      attemptId: 'attempt-$attemptNumber',
      sessionId: sessionId,
      attemptNumber: attemptNumber,
    );
  }

  @override
  Future<PersistedAttempt> completeAttempt({
    required StagedAttempt attempt,
    required InferenceResult result,
    required ImmutableJsonReceipt receipt,
  }) async {
    events.add('complete');
    if (!completeCalled.isCompleted) completeCalled.complete();
    await completeGate?.future;
    final persisted = PersistedAttempt(attemptId: attempt.attemptId);
    completedAttempts.add(persisted);
    return persisted;
  }

  @override
  Future<void> recordResolution(ObjectResolutionDraft resolution) async {
    resolutionAttempts += 1;
    if (resolutionFailuresRemaining > 0) {
      resolutionFailuresRemaining -= 1;
      throw StateError('temporary resolution persistence failure');
    }
    resolutions.add(resolution);
  }

  @override
  Future<void> replaceDraftOrder(
    String sessionId,
    List<CheckoutLine> lines,
  ) async {
    if (draftFailuresRemaining > 0) {
      draftFailuresRemaining -= 1;
      throw StateError('temporary draft persistence failure');
    }
    draftLines = List.of(lines);
  }

  @override
  Future<PaymentReceipt> commitSimulatedPayment(
    FinalOrderDraft order, {
    SimulatedPaymentRequest? request,
  }) async {
    committedOrder = order;
    committedOrders.add(order);
    if (!paymentCalled.isCompleted) paymentCalled.complete();
    await paymentGate?.future;
    if (paymentFailuresRemaining > 0) {
      paymentFailuresRemaining -= 1;
      throw StateError('temporary payment persistence failure');
    }
    return PaymentReceipt(
      paymentId: request?.paymentId ?? 'payment-1',
      orderId: request?.orderId ?? 'order-1',
      sessionId: order.sessionId,
      amount: order.totalPrice,
      currency: 'KRW',
      provider: 'simulated',
      status: 'approved',
      paidAt: order.createdAt,
    );
  }

  @override
  Future<void> abandonSession(String sessionId, String reason) async {
    abandonAttempts += 1;
    if (abandonFailuresRemaining > 0) {
      abandonFailuresRemaining -= 1;
      throw StateError('temporary abandonment persistence failure');
    }
    abandonedSessionIds.add(sessionId);
    abandonReasons.add(reason);
  }
}

final class _FakeEvidenceStore implements CheckoutEvidenceStore {
  _FakeEvidenceStore(this.events);

  final List<String> events;
  Object? captureError;
  Object? receiptError;

  @override
  Future<CapturedAuditFile> retainCapture({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required String sourcePath,
  }) async {
    events.add('retain_capture');
    final error = captureError;
    if (error != null) throw error;
    return CapturedAuditFile(
      fileId: 'capture-$attemptNumber',
      path: 'sessions/capture-$attemptNumber.jpg',
      sha256:
          'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    );
  }

  @override
  Future<void> retainInferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  }) async {
    events.add('retain_receipt');
    final error = receiptError;
    if (error != null) throw error;
  }
}

final class _DisplayPathResolver implements AuditDisplayPathResolver {
  const _DisplayPathResolver();

  @override
  Future<String> resolveForDisplay(String relativePath) async =>
      r'C:\audit-root\' + relativePath.replaceAll('/', r'\');
}

final class _FakeCatalog implements CatalogRepository {
  _FakeCatalog() {
    productsBySku = {
      6: _product('product-croissant', 'Croissant', 6),
      10: _product('product-donut', 'Sugar Donut', 10),
      11: _product('product-cream-donut', 'Cream Donut', 11),
    };
  }

  late Map<int, Product> productsBySku;
  String _revisionId = 'catalog-v1';

  List<Product> get products => productsBySku.values.toList(growable: false);

  @override
  Future<CatalogSnapshot> activeCatalog() async =>
      CatalogSnapshot(revision: _revision, products: products);

  void activateRevision({
    required String revisionId,
    required List<Product> products,
  }) {
    _revisionId = revisionId;
    productsBySku = {
      for (final product in products)
        if (product.recognitionSkuId != null)
          product.recognitionSkuId!: product,
    };
  }

  @override
  Future<Product?> productForRecognitionSku(int recognitionSkuId) async =>
      productsBySku[recognitionSkuId];

  @override
  Future<CustomerCatalogDiscovery> customerDiscoveryFor(
    CatalogSnapshot catalog,
  ) async => CustomerCatalogDiscovery(
    catalog: catalog,
    featuredProducts: catalog.products,
  );

  Future<List<Product>> search(String query) async => products
      .where((product) => product.displayName.contains(query))
      .toList(growable: false);

  CatalogRevision get _revision => CatalogRevision(
    revisionId: _revisionId,
    sha256: 'a' * 64,
    createdAt: DateTime.utc(2026),
  );
}

final class _FakeCamera implements CameraSession {
  _FakeCamera(this.events);

  final List<String> events;
  final _errors = StreamController<String>.broadcast(sync: true);
  final capture = const CapturedFrame(r'C:\session\capture-1.jpg');
  final releasedPaths = <String>[];
  bool initializeResult = true;
  bool _ready = false;

  @override
  Stream<String> get errors => _errors.stream;

  @override
  bool get isReady => _ready;

  @override
  String? get lastError => _ready ? null : 'camera unavailable';

  @override
  CameraController? get previewController => null;

  @override
  Future<bool> initialize() async {
    _ready = initializeResult;
    return _ready;
  }

  @override
  Future<CapturedFrame> captureStill() async {
    events.add('capture');
    return capture;
  }

  @override
  Future<void> releaseCapture(String absolutePath) async {
    events.add('release');
    releasedPaths.add(absolutePath);
  }

  @override
  Future<bool> reconnect() async => _ready;

  @override
  Future<void> close() async {
    await _errors.close();
  }
}

final class _FakeWorker implements InferenceSession {
  _FakeWorker(this.trace);

  final List<String> trace;
  final _events = StreamController<WorkerEvent>.broadcast(sync: true);
  WorkerStatus _status = WorkerStatus.notStarted;
  InferenceResult? nextResult;
  Completer<void>? analysisGate;
  Completer<void> analysisStarted = Completer<void>();
  int analyzeCalls = 0;

  @override
  WorkerStatus get status => _status;

  @override
  Stream<WorkerEvent> get events => _events.stream;

  @override
  Future<void> start() async {
    _status = WorkerStatus.ready;
    _events.add(const ReadyWorkerEvent(device: 'cpu', metrics: null));
  }

  @override
  Future<InferenceResult> analyze(String imagePath) async {
    trace.add('worker');
    analyzeCalls += 1;
    if (!analysisStarted.isCompleted) analysisStarted.complete();
    await analysisGate?.future;
    return nextResult!;
  }

  @override
  Future<void> shutdown() async {
    _status = WorkerStatus.stopped;
    await _events.close();
  }
}

Product _product(String id, String name, int sku) => Product(
  productId: id,
  displayName: name,
  unitPrice: 2800,
  recognitionSkuId: sku,
  categoryId: 'bakery',
  photoAssetPath: null,
  active: true,
  sortOrder: sku,
);

InferenceResult _registeredResult() => InferenceResult.fromJson({
  'type': 'result',
  'request_id': 'analysis-registered',
  'image': {'width': 1920, 'height': 1080},
  'device': 'cpu',
  'objects': [
    buildInferenceObjectJson(
      id: 'object-1',
      skuId: 6,
      name: 'Croissant',
      confidence: 0.92,
      decisionPath: 'repvit_direct',
      box: const [10.0, 20.0, 500.0, 500.0],
    ),
  ],
  'counts': {'6': 1},
  'unknown_count': 0,
  'presentation': buildPresentationJson(),
  'timings_ms': _timings,
});

InferenceResult _emptyResult({String requestId = 'analysis-empty'}) =>
    InferenceResult.fromJson({
      'type': 'result',
      'request_id': requestId,
      'image': {'width': 1920, 'height': 1080},
      'device': 'cpu',
      'objects': <Object?>[],
      'counts': <String, Object?>{},
      'unknown_count': 0,
      'presentation': buildPresentationJson(
        state: 'needs_retake',
        finalCountUsable: false,
        retakeScope: 'scan',
        instructionCode: 'no_bread_detected',
      ),
      'timings_ms': _timings,
    });

const _timings = {
  'decode_preprocess': 1.0,
  'detector': 2.0,
  'repvit': 3.0,
  'dinov3': 0.0,
  'postprocess': 4.0,
  'total': 10.0,
};
