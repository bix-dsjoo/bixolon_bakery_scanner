import 'package:bakery_camera_prototype/src/admin/settings_models.dart';
import 'package:bakery_camera_prototype/src/admin/settings_service.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late BakeryDatabase database;
  late SettingsService service;

  setUp(() {
    database = openInMemoryBakeryDatabase();
    service = SettingsService(
      database: database,
      createId: () => 'settings-v2',
      now: () => DateTime.utc(2026, 7, 31, 8),
    );
  });
  tearDown(() => database.close());

  test(
    'saves supported settings as a copy-on-write revision with audit proof',
    () async {
      final before = await service.current();

      final after = await service.save(
        const KioskSettingsDraft(
          kioskDisplayName: 'BIXOLON \uC131\uC218\uC810',
          retryLimit: 3,
          paymentCompleteDurationSeconds: 6,
          customerAutoReset: false,
          evidenceRetentionDays: 120,
          locale: 'ko-KR',
          adminAuthorLabel: '\uC131\uC218\uC810 \uAD00\uB9AC\uC790',
        ),
      );

      expect(after.revisionId, 'settings-v2');
      expect(after.revisionId, isNot(before.revisionId));
      expect(after.retryLimit, 3);
      expect((await service.current()).revisionId, 'settings-v2');
      expect((await service.revision(before.revisionId)).retryLimit, 2);
      final event =
          await (database.select(database.auditEvents)..where(
                (row) => row.eventType.equals('settings_revision_activated'),
              ))
              .getSingle();
      expect(event.detail, contains('settings-v1'));
      expect(event.detail, contains('settings-v2'));
      final entries = await (database.select(
        database.settingsRevisionEntries,
      )..where((row) => row.revisionId.equals('settings-v2'))).get();
      expect(entries, hasLength(KioskSettingKey.values.length));
      expect(
        entries
            .singleWhere(
              (row) => row.settingKey == KioskSettingKey.retryLimit.storageKey,
            )
            .valueType,
        'integer',
      );
    },
  );

  test(
    'rejects invalid ranges, non-Korean locale, and arbitrary setting keys',
    () async {
      final valid = await service.current();
      for (final draft in [
        valid.toDraft(retryLimit: 0),
        valid.toDraft(retryLimit: 6),
        valid.toDraft(paymentCompleteDurationSeconds: 1),
        valid.toDraft(paymentCompleteDurationSeconds: 11),
        valid.toDraft(evidenceRetentionDays: 6),
        valid.toDraft(evidenceRetentionDays: 3651),
        valid.toDraft(locale: 'en-US'),
        valid.toDraft(kioskDisplayName: '  '),
        valid.toDraft(adminAuthorLabel: '  '),
      ]) {
        await expectLater(() => service.save(draft), throwsArgumentError);
      }
      expect(
        () => KioskSettingKey.fromStorageKey('detector_threshold'),
        throwsArgumentError,
      );
      expect(
        () => KioskSettingKey.fromStorageKey('fusion_margin'),
        throwsArgumentError,
      );
      expect((await service.current()).revisionId, valid.revisionId);
    },
  );
}
