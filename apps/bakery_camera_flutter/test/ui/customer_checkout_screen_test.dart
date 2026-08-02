import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/audit/audit_file_store.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_state.dart';
import 'package:bakery_camera_prototype/src/ui/customer/analyzing_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/captured_review_overlay.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_presentation.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:bakery_camera_prototype/src/ui/customer/payment_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/ready_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/retake_required_view.dart';
import 'package:bakery_camera_prototype/src/ui/components/bakery_status_banner.dart';
import 'package:bakery_camera_prototype/src/ui/components/checkout_scaffold.dart';
import 'package:flutter/foundation.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/customer_checkout_journey_fixture.dart';

void main() {
  test(
    'customer review passes an actual retained display path to its image provider',
    () async {
      final retainedImage = await _retainReviewJpeg();
      addTearDown(() => retainedImage.directory.delete(recursive: true));
      final displayPath = retainedImage.displayPath;
      expect(await File(displayPath).readAsBytes(), retainedImage.jpegBytes);
      final providerInputs = <String>[];
      final image = CapturedReviewOverlay(
        imagePath: displayPath,
        imageWidth: 1920,
        imageHeight: 1080,
        objects: const [],
        selectedObjectId: null,
        onSelectObject: (_) {},
        imageProviderFactory: (file) {
          providerInputs.add(file.path);
          return const _TestImageProvider();
        },
      );

      expect(image.imageProviderForDisplayPath(), isA<_TestImageProvider>());
      expect(providerInputs, [displayPath]);
    },
  );

  test('customer review defaults production display paths to FileImage', () {
    const displayPath = r'C:\retained\session\attempt-1.jpg';
    final image = CapturedReviewOverlay(
      imagePath: displayPath,
      imageWidth: 1920,
      imageHeight: 1080,
      objects: const [],
      selectedObjectId: null,
      onSelectObject: (_) {},
    );

    final provider = image.imageProviderForDisplayPath();
    expect(provider, isA<FileImage>());
    expect((provider as FileImage).file.path, displayPath);
  });

  testWidgets('review uses the full-scene overlay instead of a selected crop', (
    tester,
  ) async {
    await _pump(
      tester,
      CapturedReviewOverlay(
        imagePath: 'test/fixtures/missing-capture.jpg',
        imageWidth: 1920,
        imageHeight: 1080,
        objects: const [
          CustomerReviewObject(
            objectId: 'object-1',
            displayNumber: 1,
            rect: Rect.fromLTWH(10, 20, 300, 400),
            state: CustomerReviewObjectState.needsChoice,
            label: 'Review product',
          ),
        ],
        selectedObjectId: 'object-1',
        onSelectObject: (_) {},
      ),
    );

    expect(find.byKey(const Key('captured-review-full-scene')), findsOneWidget);
    expect(find.byKey(const Key('selected-object-crop')), findsNothing);
    expect(find.byKey(const Key('selected-object-zoom')), findsNothing);
  });

  testWidgets(
    'catalog search keeps the retained scene visible and returns to the same exception',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 820);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final fixture = (await tester.runAsync(() async {
        final fixture = await CustomerCheckoutJourneyFixture.create();
        await fixture.controller.initialize();
        await fixture.controller.scan();
        return fixture;
      }))!;
      addTearDown(() => tester.runAsync(fixture.dispose));

      await _pump(
        tester,
        CustomerCheckoutScreen(controller: fixture.controller),
      );
      await tester.ensureVisible(find.text('다른 상품 찾기'));
      await tester.tap(find.text('다른 상품 찾기'));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('captured-review-full-scene')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('customer-catalog-close')), findsOneWidget);

      await tester.tap(find.byKey(const Key('customer-catalog-close')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('customer-review-candidate-panel-object-2')),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'order correction keeps the order visible beside the catalog panel',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 820);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final fixture = (await tester.runAsync(() async {
        final fixture = await CustomerCheckoutJourneyFixture.create();
        await fixture.controller.initialize();
        await fixture.controller.scan();
        await fixture.controller.chooseTop3('object-2', 10);
        return fixture;
      }))!;
      addTearDown(() => tester.runAsync(fixture.dispose));

      await _pump(
        tester,
        CustomerCheckoutScreen(controller: fixture.controller),
      );
      expect(find.text('주문 확인'), findsOneWidget);

      await tester.tap(find.byTooltip('인식 상품 변경').first);
      await tester.pumpAndSettle();

      expect(find.text('주문 확인'), findsOneWidget);
      expect(
        find.byKey(const Key('order-review-catalog-panel')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('order-review-scene-pane')), findsOneWidget);
      expect(find.byKey(const Key('order-review-task-pane')), findsOneWidget);
      final divider = tester.getRect(
        find.byKey(const Key('order-review-workspace-divider')),
      );
      final scene = tester.getRect(
        find.byKey(const Key('order-review-scene-pane')),
      );
      final task = tester.getRect(
        find.byKey(const Key('order-review-task-pane')),
      );
      expect(divider.width, 1);
      expect(divider.left - scene.right, closeTo(12, 1));
      expect(task.left - divider.right, closeTo(12, 1));
      final panelMaterial = tester.widget<Material>(
        find
            .descendant(
              of: find.byKey(const Key('order-review-catalog-panel')),
              matching: find.byType(Material),
            )
            .first,
      );
      expect(panelMaterial.elevation, 2);
      expect(panelMaterial.borderRadius, BorderRadius.circular(10));
      expect(find.byKey(const Key('customer-catalog-close')), findsOneWidget);

      await tester.tap(find.byKey(const Key('customer-catalog-close')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('order-review-catalog-panel')), findsNothing);
      expect(find.text('주문 확인'), findsOneWidget);
    },
  );

  testWidgets('manual catalog does not reserve an empty action rail', (
    tester,
  ) async {
    final fixture = (await tester.runAsync(() async {
      final fixture = await CustomerCheckoutJourneyFixture.create();
      await fixture.controller.initialize();
      await fixture.controller.scan();
      await fixture.controller.chooseTop3('object-2', 10);
      return fixture;
    }))!;
    addTearDown(() => tester.runAsync(fixture.dispose));

    await _pump(tester, CustomerCheckoutScreen(controller: fixture.controller));
    await tester.tap(find.text('상품 추가'));
    await tester.pumpAndSettle();

    expect(find.text('상품 찾기'), findsOneWidget);
    expect(find.byKey(const Key('customer-action-rail')), findsNothing);
  });

  testWidgets(
    'manual next customer wins the auto-reset race without surfacing StateError',
    (tester) async {
      final gate = Completer<void>();
      var starts = 0;
      await _pump(
        tester,
        PaymentCompleteView(
          state: CheckoutState(
            phase: CheckoutPhase.paymentComplete,
            objectDrafts: const [],
            lines: const [],
          ),
          policy: const CustomerCompletionPolicy(
            duration: Duration(milliseconds: 50),
            autoReset: true,
          ),
          onNext: () async {
            starts += 1;
            await gate.future;
          },
        ),
      );

      await tester.tap(find.byType(FilledButton));
      await tester.pump(const Duration(milliseconds: 50));
      expect(starts, 1);
      gate.complete();
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('payment only states that the durable save is in progress', (
    tester,
  ) async {
    await _pump(
      tester,
      PaymentView(
        state: CheckoutState(
          phase: CheckoutPhase.paying,
          objectDrafts: const [],
          lines: const [],
        ),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.text('결제를 기록하고 있어요'), findsOneWidget);
  });

  testWidgets('payment completion centers one concise receipt summary', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pump(
      tester,
      PaymentCompleteView(
        state: CheckoutState(
          phase: CheckoutPhase.paymentComplete,
          objectDrafts: const [],
          lines: const [],
          paymentReceipt: PaymentReceipt(
            paymentId: 'payment-1',
            orderId: 'order-1',
            sessionId: 'session-1',
            amount: 5000,
            currency: 'KRW',
            provider: 'simulated',
            status: 'approved',
            paidAt: DateTime.utc(2026, 7, 31),
          ),
        ),
        policy: const CustomerCompletionPolicy(
          duration: Duration(hours: 1),
          autoReset: false,
        ),
        onNext: () async {},
      ),
    );

    final summary = tester.getRect(
      find.byKey(const Key('payment-complete-summary')),
    );
    expect(summary.center.dx, closeTo(512, 1));
  });

  testWidgets('ready explains placement and exposes one scan action', (
    tester,
  ) async {
    await _pump(tester, ReadyView(onScan: () {}));

    expect(
      find.byKey(const Key('ready-placement-instruction')),
      findsOneWidget,
    );
    expect(find.text('트레이를 카메라 아래에 맞춰주세요.'), findsOneWidget);
    expect(find.text('빵을 트레이에 올려주세요'), findsNothing);
    expect(find.text('빵이 겹치지 않도록 펼쳐 놓으면 더 잘 확인할 수 있어요.'), findsNothing);
    expect(find.byType(BakeryStatusBanner), findsNothing);
    expect(find.text('빵 확인하기'), findsOneWidget);
    expect(find.byType(FilledButton), findsOneWidget);
    expect(find.byKey(const Key('live-tray-placement-guide')), findsOneWidget);
  });

  testWidgets('ready keeps the complete camera scene above the action rail', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pump(tester, ReadyView(onScan: () {}));

    final scene = tester.getRect(
      find.byKey(const Key('live-tray-placement-guide')),
    );
    final rail = tester.getRect(find.byKey(const Key('customer-action-rail')));
    expect(scene.bottom, lessThanOrEqualTo(rail.top));
    expect(scene.width / scene.height, closeTo(16 / 9, 0.02));
  });

  testWidgets('ready does not require page scrolling at kiosk height', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pump(tester, ReadyView(onScan: () {}));

    expect(find.byType(SingleChildScrollView), findsNothing);
  });

  testWidgets('analyzing and paying do not render an empty action rail', (
    tester,
  ) async {
    await _pump(tester, const AnalyzingView());
    expect(find.byKey(const Key('customer-action-rail')), findsNothing);

    await _pump(
      tester,
      PaymentView(
        state: CheckoutState(
          phase: CheckoutPhase.paying,
          objectDrafts: const [],
          lines: const [],
        ),
      ),
    );
    expect(find.byKey(const Key('customer-action-rail')), findsNothing);
  });

  testWidgets(
    'analyzing centers its factual status in the available workspace',
    (tester) async {
      tester.view.physicalSize = const Size(1024, 720);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await _pump(tester, const AnalyzingView());

      final header = tester.getRect(find.byKey(const Key('customer-header')));
      final scaffold = tester.getRect(find.byType(Scaffold).last);
      final status = tester.getRect(
        find.byKey(const ValueKey('status-message')),
      );
      expect(
        status.center.dy,
        closeTo((header.bottom + scaffold.bottom) / 2, 44),
      );
      expect(status.center.dx, closeTo(scaffold.center.dx, 1));
      expect(status.width, lessThanOrEqualTo(440));
    },
  );

  testWidgets('routine status is a compact row rather than a bordered panel', (
    tester,
  ) async {
    await _pump(
      tester,
      const BakeryStatusBanner(
        status: BakeryStatus.ready,
        title: '빵을 올려주세요',
        message: '트레이를 확인합니다.',
      ),
    );

    final row = find.byKey(const Key('routine-status-row'));
    expect(row, findsOneWidget);
    expect(
      find.descendant(of: row, matching: find.byType(DecoratedBox)),
      findsNothing,
    );
  });

  testWidgets('customer shell keeps header and action rail full width', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pump(
      tester,
      CheckoutScaffold(
        title: '셀프 계산',
        primaryAction: const SizedBox(
          key: Key('customer-shell-action'),
          height: 52,
        ),
        child: const SizedBox(),
      ),
    );

    expect(
      tester.getRect(find.byKey(const Key('customer-header'))).width,
      1024,
    );
    expect(tester.getSize(find.byKey(const Key('customer-header'))).height, 61);
    expect(
      tester.getRect(find.byKey(const Key('customer-action-rail'))).width,
      1024,
    );
  });

  testWidgets(
    'customer shell omits the action rail when no action is supplied',
    (tester) async {
      await _pump(
        tester,
        const CheckoutScaffold(title: '빵 확인', child: SizedBox()),
      );

      expect(find.byKey(const Key('customer-action-rail')), findsNothing);
    },
  );

  testWidgets('administrator entry is aligned inside the customer header', (
    tester,
  ) async {
    final fixture = (await tester.runAsync(() async {
      final fixture = await CustomerCheckoutJourneyFixture.create();
      await fixture.controller.initialize();
      return fixture;
    }))!;
    addTearDown(() => tester.runAsync(fixture.dispose));

    await _pump(
      tester,
      CustomerCheckoutScreen(
        controller: fixture.controller,
        onEnterAdmin: ({required abandonConfirmed}) async => true,
      ),
    );

    final header = tester.getRect(find.byKey(const Key('customer-header')));
    final adminAction = tester.getRect(
      find.byKey(const Key('customer-header-action')),
    );
    expect(adminAction.top, greaterThanOrEqualTo(header.top));
    expect(adminAction.bottom, lessThanOrEqualTo(header.bottom));
    expect(adminAction.center.dy, closeTo(header.center.dy, 0.1));
    expect(adminAction.right, closeTo(header.right - 24, 1));

    await tester.runAsync(fixture.controller.scan);
    await tester.pumpAndSettle();

    expect(fixture.controller.state.phase, isNot(CheckoutPhase.ready));
    expect(find.byKey(const Key('customer-header-action')), findsNothing);
    expect(find.text('愿由ъ옄'), findsNothing);
  });

  testWidgets('customer header omits redundant kiosk display name', (
    tester,
  ) async {
    await _pump(
      tester,
      KioskDisplayNameScope(
        displayName: 'BIXOLON Seongsu',
        child: const CheckoutScaffold(title: '???怨꾩궛', child: SizedBox()),
      ),
    );

    expect(find.byKey(const Key('kiosk-display-name')), findsNothing);
    expect(find.text('BIXOLON Seongsu'), findsNothing);
  });

  testWidgets('analyzing is factual and does not expose navigation', (
    tester,
  ) async {
    await _pump(tester, const AnalyzingView());

    expect(find.text('빵을 확인하고 있어요'), findsOneWidget);
    expect(find.byType(FilledButton), findsNothing);
    expect(find.byType(OutlinedButton), findsNothing);
  });

  testWidgets(
    'retake hides model evidence and only shows manual entry after retry limit',
    (tester) async {
      final state = CheckoutState(
        phase: CheckoutPhase.retakeRequired,
        objectDrafts: const [],
        lines: const [],
        failure: const CheckoutFailure(
          code: 'retake',
          message: 'retry',
          recoverable: true,
        ),
      );
      await _pump(
        tester,
        RetakeRequiredView(
          state: state,
          manualCartEligible: false,
          onRetake: () {},
          onManualEntry: () {},
        ),
      );

      expect(find.text('빵을 떨어뜨려 다시 놓아주세요'), findsOneWidget);
      expect(find.text('다시 촬영'), findsOneWidget);
      expect(find.text('직접 담기'), findsNothing);
      expect(find.textContaining('GPU'), findsNothing);
      expect(find.textContaining('%'), findsNothing);

      await _pump(
        tester,
        RetakeRequiredView(
          state: state,
          manualCartEligible: true,
          onRetake: () {},
          onManualEntry: () {},
        ),
      );
      expect(find.text('직접 담기'), findsOneWidget);
    },
  );
}

Future<void> _pump(WidgetTester tester, Widget child) => tester.pumpWidget(
  MaterialApp(
    theme: buildBakeryTheme(),
    home: Scaffold(body: child),
  ),
);

Future<_RetainedAuditImage> _retainReviewJpeg() async {
  final directory = await Directory.systemTemp.createTemp('customer-review-');
  try {
    final source = File('${directory.path}${Platform.pathSeparator}source.jpg');
    final jpegBytes = base64Decode(
      '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDvaKKK/hw/sU//2Q==',
    );
    await source.writeAsBytes(jpegBytes, flush: true);
    final store = AuditFileStore(
      Directory('${directory.path}${Platform.pathSeparator}audit'),
    );
    final stored = await store.retainCapture(
      sessionId: '00000000-0000-4000-8000-000000000001',
      attemptNumber: 1,
      capturedAtUtc: DateTime.utc(2026, 7, 30),
      sourcePath: source.path,
    );
    return _RetainedAuditImage(
      directory: directory,
      displayPath: await store.resolveForDisplay(stored.relativePath),
      jpegBytes: jpegBytes,
    );
  } catch (_) {
    await directory.delete(recursive: true);
    rethrow;
  }
}

final class _RetainedAuditImage {
  const _RetainedAuditImage({
    required this.directory,
    required this.displayPath,
    required this.jpegBytes,
  });

  final Directory directory;
  final String displayPath;
  final List<int> jpegBytes;
}

final class _TestImageProvider extends ImageProvider<_TestImageProvider> {
  const _TestImageProvider();

  @override
  Future<_TestImageProvider> obtainKey(ImageConfiguration configuration) =>
      SynchronousFuture(this);

  @override
  ImageStreamCompleter loadImage(
    _TestImageProvider key,
    ImageDecoderCallback decode,
  ) => throw UnimplementedError('image decoding is outside this contract test');
}
