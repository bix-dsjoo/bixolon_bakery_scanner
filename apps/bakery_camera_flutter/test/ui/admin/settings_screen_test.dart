import 'package:bakery_camera_prototype/src/admin/retention_service.dart';
import 'package:bakery_camera_prototype/src/admin/settings_models.dart';
import 'package:bakery_camera_prototype/src/admin/settings_service.dart';
import 'package:bakery_camera_prototype/src/ui/admin/settings_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('settings show supported Korean operational groups and preview', (
    tester,
  ) async {
    final settings = _SettingsRepository();
    final retention = _RetentionRepository();
    await _pump(tester, settings, retention);

    expect(find.text('\uACE0\uAC1D \uD654\uBA74'), findsOneWidget);
    expect(find.text('\uACC4\uC0B0 \uC644\uB8CC'), findsOneWidget);
    expect(find.text('\uAE30\uB85D \uBCF4\uC874'), findsOneWidget);
    expect(
      find.text(
        '\uC124\uC815\uC740 \uB2E4\uC74C \uACE0\uAC1D \uACC4\uC0B0\uBD80\uD130 \uC801\uC6A9\uB429\uB2C8\uB2E4.',
      ),
      findsOneWidget,
    );

    await _scrollTo(tester, find.byKey(const Key('retention-preview')));
    await tester.tap(find.byKey(const Key('retention-preview')));
    await tester.pumpAndSettle();
    expect(
      find.text('\uC0AD\uC81C\uD560 \uAE30\uB85D \uBBF8\uB9AC \uBCF4\uAE30'),
      findsNWidgets(2),
    );
  });

  testWidgets('settings saves the supported next-session values', (
    tester,
  ) async {
    final settings = _SettingsRepository();
    await _pump(tester, settings, _RetentionRepository());

    await tester.enterText(
      find.byKey(const Key('settings-kiosk-display-name')),
      'BIXOLON Seongsu',
    );
    await tester.enterText(find.byKey(const Key('settings-retry-limit')), '3');
    await tester.enterText(
      find.byKey(const Key('settings-complete-duration')),
      '6',
    );
    await tester.enterText(
      find.byKey(const Key('settings-retention-days')),
      '120',
    );
    await _scrollTo(tester, find.byKey(const Key('settings-admin-author')));
    await tester.enterText(
      find.byKey(const Key('settings-admin-author')),
      'saved-ops-admin',
    );
    await _scrollTo(tester, find.text('\uC124\uC815 \uC800\uC7A5'));
    await tester.tap(find.text('\uC124\uC815 \uC800\uC7A5'));
    await tester.pumpAndSettle();

    expect(settings.value.kioskDisplayName, 'BIXOLON Seongsu');
    expect(settings.value.retryLimit, 3);
    expect(settings.value.paymentCompleteDurationSeconds, 6);
    expect(settings.value.evidenceRetentionDays, 120);
    expect(settings.value.adminAuthorLabel, 'saved-ops-admin');
    expect(
      find.textContaining(
        '\uB2E4\uC74C \uACE0\uAC1D \uACC4\uC0B0\uBD80\uD130 \uC801\uC6A9',
      ),
      findsOneWidget,
    );
  });

  testWidgets('settings shows a save error when the supported range fails', (
    tester,
  ) async {
    final settings = _SettingsRepository()
      ..saveError = ArgumentError.value(0, 'retryLimit', 'must be 1 to 5');
    await _pump(tester, settings, _RetentionRepository());

    await _scrollTo(tester, find.text('\uC124\uC815 \uC800\uC7A5'));
    await tester.tap(find.text('\uC124\uC815 \uC800\uC7A5'));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('\uC124\uC815 \uBC94\uC704\uB97C \uD655\uC778'),
      findsOneWidget,
    );
  });

  testWidgets(
    'retention requires confirmation and executes the shown preview',
    (tester) async {
      final retention = _RetentionRepository();
      await _pump(tester, _SettingsRepository(), retention);

      await _scrollTo(tester, find.byKey(const Key('retention-preview')));
      await tester.tap(find.byKey(const Key('retention-preview')));
      await tester.pumpAndSettle();
      final execute = find.widgetWithText(
        FilledButton,
        '\uC774\uBBF8\uC9C0 \uC0AD\uC81C \uC2E4\uD589',
      );
      expect(tester.widget<FilledButton>(execute).onPressed, isNull);
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      expect(tester.widget<FilledButton>(execute).onPressed, isNotNull);
      await tester.tap(execute);
      await tester.pumpAndSettle();

      expect(retention.executedPreviewIds, ['retention-preview']);
      expect(
        find.text('\uC0AD\uC81C\uD560 \uAE30\uB85D \uBBF8\uB9AC \uBCF4\uAE30'),
        findsOneWidget,
      );
    },
  );
}

Future<void> _pump(
  WidgetTester tester,
  KioskSettingsRepository settings,
  RetentionRepository retention,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SettingsScreen(settings: settings, retention: retention),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _scrollTo(WidgetTester tester, Finder finder) async {
  final scrollable = find.byType(Scrollable).first;
  for (var attempt = 0; attempt < 8 && finder.evaluate().isEmpty; attempt++) {
    await tester.drag(scrollable, const Offset(0, -240));
    await tester.pump();
  }
  if (finder.evaluate().isEmpty) {
    throw TestFailure('target control was not built after scrolling');
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

final class _SettingsRepository implements KioskSettingsRepository {
  KioskSettings value = KioskSettings(
    revisionId: 'settings-v1',
    updatedAt: DateTime.utc(2026, 7, 31),
    kioskDisplayName: 'BIXOLON Bakery',
    retryLimit: 2,
    paymentCompleteDurationSeconds: 4,
    customerAutoReset: true,
    evidenceRetentionDays: 90,
    locale: SettingsService.koreanLocale,
    adminAuthorLabel: 'prototype-admin',
  );
  Object? saveError;

  @override
  Future<KioskSettings> current() async => value;

  @override
  Future<KioskSettings> save(KioskSettingsDraft draft) async {
    final error = saveError;
    if (error != null) throw error;
    value = KioskSettings(
      revisionId: 'settings-v2',
      updatedAt: DateTime.utc(2026, 7, 31),
      kioskDisplayName: draft.kioskDisplayName,
      retryLimit: draft.retryLimit,
      paymentCompleteDurationSeconds: draft.paymentCompleteDurationSeconds,
      customerAutoReset: draft.customerAutoReset,
      evidenceRetentionDays: draft.evidenceRetentionDays,
      locale: draft.locale,
      adminAuthorLabel: draft.adminAuthorLabel,
    );
    return value;
  }
}

final class _RetentionRepository implements RetentionRepository {
  final executedPreviewIds = <String>[];

  @override
  Future<RetentionExecutionResult> execute(String previewId) async {
    executedPreviewIds.add(previewId);
    return const RetentionExecutionResult(
      filesRemoved: 0,
      bytesRemoved: 0,
      quarantineCleanupPending: false,
    );
  }

  @override
  Future<RetentionPreview> preview(DateTime cutoff) async => RetentionPreview(
    previewId: 'retention-preview',
    cutoff: cutoff,
    files: const [],
  );
}
