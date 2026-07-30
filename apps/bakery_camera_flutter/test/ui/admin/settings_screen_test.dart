import 'dart:io';

import 'package:bakery_camera_prototype/src/admin/retention_service.dart';
import 'package:bakery_camera_prototype/src/admin/settings_service.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:bakery_camera_prototype/src/ui/admin/settings_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('settings show supported Korean operational groups and preview', (
    tester,
  ) async {
    final database = openInMemoryBakeryDatabase();
    final root = await Directory.systemTemp.createTemp('settings-screen-');
    addTearDown(database.close);
    addTearDown(() => root.delete(recursive: true));
    final settings = SettingsService(
      database: database,
      createId: () => 'settings-ui-v2',
      now: () => DateTime.utc(2026, 7, 31),
    );
    final retention = RetentionService(
      database: database,
      evidenceRoot: root,
      createId: () => 'retention-ui-v1',
      now: () => DateTime.utc(2026, 7, 31),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SettingsScreen(settings: settings, retention: retention),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    expect(find.text('\uACE0\uAC1D \uD654\uBA74'), findsOneWidget);
    expect(find.text('\uACC4\uC0B0 \uC644\uB8CC'), findsOneWidget);
    expect(find.text('\uAE30\uB85D \uBCF4\uC874'), findsOneWidget);
    expect(
      find.text(
        '\uC124\uC815\uC740 \uB2E4\uC74C \uACE0\uAC1D \uACC4\uC0B0\uBD80\uD130 \uC801\uC6A9\uB429\uB2C8\uB2E4.',
      ),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('retention-preview')));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(
      find.text('\uC0AD\uC81C\uD560 \uAE30\uB85D \uBBF8\uB9AC \uBCF4\uAE30'),
      findsOneWidget,
    );
  });
}
