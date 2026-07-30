import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/audit/audit_file_store.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_state.dart';
import 'package:bakery_camera_prototype/src/ui/customer/analyzing_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:bakery_camera_prototype/src/ui/customer/payment_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/ready_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/retake_required_view.dart';
import 'package:flutter/foundation.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'customer review passes an actual retained display path to its image provider',
    () async {
      final retainedImage = await _retainReviewJpeg();
      addTearDown(() => retainedImage.directory.delete(recursive: true));
      final displayPath = retainedImage.displayPath;
      expect(await File(displayPath).readAsBytes(), retainedImage.jpegBytes);
      final providerInputs = <String>[];
      final image = CapturedReviewImage(
        imagePath: displayPath,
        imageWidth: 1920,
        imageHeight: 1080,
        crop: Rect.fromLTWH(10, 20, 300, 400),
        imageProviderFactory: (file) {
          providerInputs.add(file.path);
          return const _TestImageProvider();
        },
      );

      expect(image.imageProviderForDisplayPath(), isA<_TestImageProvider>());
      expect(providerInputs, [displayPath]);
    },
  );

  testWidgets(
    'selected-object crop changes zoom for both box width and height',
    (tester) async {
      Future<double> zoomFor(Rect crop) async {
        await _pump(
          tester,
          CapturedReviewImage(
            imagePath: 'test/fixtures/missing-capture.jpg',
            imageWidth: 1920,
            imageHeight: 1080,
            crop: crop,
          ),
        );
        return tester
            .widget<Transform>(find.byKey(const Key('selected-object-zoom')))
            .transform
            .storage[0];
      }

      final compact = await zoomFor(const Rect.fromLTWH(700, 300, 200, 200));
      final wider = await zoomFor(const Rect.fromLTWH(550, 300, 500, 200));
      final taller = await zoomFor(const Rect.fromLTWH(700, 200, 200, 500));

      expect(wider, isNot(compact));
      expect(taller, isNot(compact));
    },
  );

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

  testWidgets('ready explains placement and exposes one scan action', (
    tester,
  ) async {
    await _pump(tester, ReadyView(onScan: () {}));

    expect(find.text('빵을 트레이에 올려주세요'), findsOneWidget);
    expect(find.text('빵 확인하기'), findsOneWidget);
    expect(find.byType(FilledButton), findsOneWidget);
    expect(find.byKey(const Key('live-tray-placement-guide')), findsOneWidget);
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
