import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_state.dart';
import 'package:bakery_camera_prototype/src/ui/customer/analyzing_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/payment_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/ready_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/retake_required_view.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('customer review presents retained still and a selected crop', (
    tester,
  ) async {
    await _pump(
      tester,
      const CapturedReviewImage(
        imagePath: 'test/fixtures/missing-capture.jpg',
        imageWidth: 1920,
        imageHeight: 1080,
        crop: Rect.fromLTWH(10, 20, 300, 400),
      ),
    );

    expect(find.byKey(const Key('captured-still')), findsOneWidget);
    expect(find.byKey(const Key('selected-object-crop')), findsOneWidget);
    expect(find.textContaining('confidence'), findsNothing);
    expect(find.textContaining('GPU'), findsNothing);
  });

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
